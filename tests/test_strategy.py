import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock

from katup_core.strategy import Strategy, Supervisor, validate_decision, LLMClient
from tools.import_traffic import import_traffic


class FakeClient:
    ready = True

    def __init__(self, data=None, delay=0, fail=False):
        self.data = data
        self.delay = delay
        self.fail = fail

    def public_config(self):
        return {'provider': 'test_fixture', 'model': 'fixture', 'configured': True}

    def decide(self, snapshot):
        time.sleep(self.delay)
        if self.fail:
            raise ValueError('api_unreachable_or_timeout')
        return self.data or {**{k: snapshot[k] for k in ('run_id', 'simulation_time')}, 'profile': 'spread_routes', 'route_bias': 'Selatan', 'reason': 'Sebar arus ke jalur yang tersedia'}, {'input': 10, 'output': 5}


class StrategyTest(unittest.TestCase):
    def setUp(self):
        self.snapshot = {'run_id': 'test-run', 'simulation_time': 30, 'routes': [{'name': 'Utara', 'available': False}, {'name': 'Selatan', 'available': True}]}
        self.decision = {'run_id': 'test-run', 'simulation_time': 30, 'profile': 'spread_routes', 'route_bias': 'Selatan', 'reason': 'Sebar arus'}

    def test_valid_decision(self):
        self.assertEqual(validate_decision(self.decision, self.snapshot, 40, 'test-run').route_bias, 'Selatan')

    def test_stale_wrong_session_unsafe_and_unknown_rejected(self):
        for delta, now in [({}, 90), ({'run_id': 'other'}, 31), ({'simulation_time': float('nan')}, 31), ({'profile': 'set_all_green'}, 31), ({'route_bias': 'Utara'}, 31), ({'phase': 5}, 31), ({'reason': '<' * 401}, 31)]:
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                validate_decision({**self.decision, **delta}, self.snapshot, now, 'test-run')

    def test_no_api_means_no_calls(self):
        with patch.dict(os.environ, {'KATUP_LLM_PROVIDER': 'disabled', 'KATUP_LLM_API_KEY': ''}):
            supervisor = Supervisor('test-run')
            self.assertEqual(supervisor.update(1, {}, []), Strategy())
            self.assertEqual(supervisor.telemetry()['status'], 'not_configured')
            self.assertEqual(supervisor.stats['requests'], 0)

    def test_async_does_not_block_and_expires(self):
        supervisor = Supervisor('test-run', FakeClient(delay=.12), interval=1000, max_age=45)
        start = time.monotonic()
        supervisor.update(30, {}, self.snapshot['routes'])
        self.assertLess(time.monotonic() - start, .06)
        time.sleep(.15)
        self.assertEqual(supervisor.update(35, {}, self.snapshot['routes']).profile, 'spread_routes')
        self.assertEqual(supervisor.update(76, {}, self.snapshot['routes']), Strategy())
        self.assertEqual(supervisor.stats['accepted'], 1)
        supervisor.close()

    def test_timeout_stale_and_budget(self):
        for client, rejected in [(FakeClient(fail=True), False), (FakeClient(), True)]:
            supervisor = Supervisor('test-run', client, interval=1, max_requests=1)
            supervisor.update(30, {}, self.snapshot['routes'])
            time.sleep(.03)
            self.assertEqual(supervisor.update(90, {}, self.snapshot['routes']), Strategy())
            self.assertEqual(supervisor.stats['rejected' if rejected else 'errors'], 1)
            self.assertEqual(supervisor.stats['requests'], 1)
            supervisor.close()

    def test_route_becomes_unavailable(self):
        supervisor = Supervisor('test-run', FakeClient(), interval=1000)
        supervisor.update(30, {}, self.snapshot['routes'])
        time.sleep(.02)
        supervisor.update(31, {}, [{'name': 'Selatan', 'available': False}])
        self.assertEqual(supervisor.stats['rejected'], 1)


class ProviderTest(unittest.TestCase):
    def test_provider_envelopes_and_private_key(self):
        for provider in ('deepseek', 'gemini'):
            with self.subTest(provider=provider), patch.dict(os.environ, {'KATUP_LLM_PROVIDER': provider, 'KATUP_LLM_API_KEY': 'test-private-key', 'KATUP_LLM_MODEL': 'test-model'}):
                client = LLMClient()
                decision = {'run_id': 'x', 'simulation_time': 1, 'profile': 'balanced', 'route_bias': 'auto', 'reason': 'Layanan seimbang'}
                envelope = {'choices': [{'message': {'content': json.dumps(decision)}}], 'usage': {'prompt_tokens': 11, 'completion_tokens': 6}} if provider == 'deepseek' else {'candidates': [{'content': {'parts': [{'text': json.dumps(decision)}]}}], 'usageMetadata': {'promptTokenCount': 11, 'candidatesTokenCount': 6}}
                response = MagicMock()
                response.__enter__.return_value.read.return_value = json.dumps(envelope).encode()
                with patch('katup_core.strategy.urlopen', return_value=response) as request:
                    result, usage = client.decide({'run_id': 'x', 'simulation_time': 1, 'routes': []})
                    self.assertEqual(result, decision)
                    self.assertEqual(usage, {'input': 11, 'output': 6})
                    self.assertNotIn('test-private-key', request.call_args.args[0].full_url)
                    self.assertNotIn('test-private-key', json.dumps(client.public_config()))


class DataTest(unittest.TestCase):
    def test_chronological_split_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            src = Path(directory) / 'data.csv'
            src.write_text('timestamp,road_id,direction,vehicle_count,speed_kmh\n2026-11-01T07:01:00,jalan-a,utara,20,25\n2026-11-02T07:01:00,jalan-a,utara,15,27\n')
            report = import_traffic(src, Path(directory) / 'out', 'synthetic test', 'CC0')
            self.assertEqual(report['holdout_dates'], ['2026-11-02'])
            with self.assertRaises(ValueError):
                src.write_text(src.read_text() + '2026-11-02T07:01:00,jalan-a,utara,15,27\n')
                import_traffic(src, Path(directory) / 'out', 'test', 'CC0')


if __name__ == '__main__':
    unittest.main()
