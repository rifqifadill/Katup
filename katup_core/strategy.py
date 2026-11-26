from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
from queue import Empty, Queue
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Strategy:
    profile: str = 'balanced'
    route_bias: str = 'auto'
    reason: str = 'Tiga agen mengikuti pengamatan antrean dan kapasitas jalur'


PROFILES = {
    'balanced': {'green_limit': 30, 'reroute_delta': 0.0},
    'protect_downstream': {'green_limit': 20, 'reroute_delta': 0.05},
    'relieve_upstream': {'green_limit': 35, 'reroute_delta': 0.0},
    'spread_routes': {'green_limit': 30, 'reroute_delta': 0.03},
}


class LLMClient:
    def __init__(self):
        self.provider = os.getenv('KATUP_LLM_PROVIDER', 'disabled')
        self.model = os.getenv('KATUP_LLM_MODEL', 'deepseek-flash' if self.provider == 'deepseek' else 'gemini-3.8-flash')
        self.key = os.getenv('KATUP_LLM_API_KEY', '')
        self.timeout = min(15, max(1, float(os.getenv('KATUP_LLM_TIMEOUT', '6'))))

    @property
    def ready(self):
        return self.provider in ('deepseek', 'gemini') and bool(self.key)

    def public_config(self):
        return {'provider': self.provider, 'model': self.model if self.ready else None, 'configured': self.ready}

    def decide(self, snapshot):
        instruction = ('Pilih strategi lalu lintas dari data SUMO, balas JSON tanpa markdown dengan field run_id, '
                       'simulation_time, profile, route_bias, reason, salin run_id dan simulation_time dari input, '
                       'profile hanya balanced, protect_downstream, relieve_upstream, spread_routes, '
                       'route_bias harus auto atau salah satu nama routes pada input, reason bahasa Indonesia singkat, '
                       'jangan mengarang metrik atau mengganti fase lampu langsung, gunakan antrean silang dan kapasitas bypass')
        message = json.dumps(snapshot, separators=(',', ':'))
        if self.provider == 'deepseek':
            endpoint = 'https://api.deepseek.com/chat/completions'
            payload = {'model': self.model, 'messages': [{'role': 'system', 'content': instruction}, {'role': 'user', 'content': message}], 'response_format': {'type': 'json_object'}, 'max_tokens': 320, 'temperature': 0, 'thinking': {'type': 'disabled'}}
            headers = {'Authorization': f'Bearer {self.key}', 'Content-Type': 'application/json'}
        elif self.provider == 'gemini':
            endpoint = f'https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent'
            payload = {'systemInstruction': {'parts': [{'text': instruction}]}, 'contents': [{'role': 'user', 'parts': [{'text': message}]}], 'generationConfig': {'responseMimeType': 'application/json', 'temperature': 0, 'maxOutputTokens': 320}}
            headers = {'x-goog-api-key': self.key, 'Content-Type': 'application/json'}
        else:
            raise ValueError('provider_disabled')
        try:
            with urlopen(Request(endpoint, data=json.dumps(payload).encode(), headers=headers), timeout=self.timeout) as response:
                data = json.loads(response.read(131072))
        except HTTPError as exc:
            raise ValueError(f'api_http_{exc.code}') from None
        except (URLError, TimeoutError, OSError):
            raise ValueError('api_unreachable_or_timeout') from None
        if self.provider == 'deepseek':
            result = data['choices'][0]['message']['content']
            usage = data.get('usage', {})
            tokens = {'input': usage.get('prompt_tokens', 0), 'output': usage.get('completion_tokens', 0)}
        else:
            result = ''.join(part.get('text', '') for part in data['candidates'][0]['content']['parts'] if not part.get('thought'))
            usage = data.get('usageMetadata', {})
            tokens = {'input': usage.get('promptTokenCount', 0), 'output': usage.get('candidatesTokenCount', 0)}
        return json.loads(result), tokens


def validate_decision(data, snapshot, now, run_id, max_age=45):
    if not isinstance(data, dict) or set(data) != {'run_id', 'simulation_time', 'profile', 'route_bias', 'reason'}:
        raise ValueError('invalid_schema')
    stamp = data['simulation_time']
    if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or not math.isfinite(stamp):
        raise ValueError('invalid_time')
    if data['run_id'] != run_id or stamp != snapshot['simulation_time'] or now < stamp or now - stamp > max_age:
        raise ValueError('stale_or_wrong_session')
    if not isinstance(data['profile'], str) or data['profile'] not in PROFILES:
        raise ValueError('unknown_profile')
    routes = {route['name']: route for route in snapshot['routes']}
    bias = data['route_bias']
    if not isinstance(bias, str) or bias not in {'auto', *routes}:
        raise ValueError('unknown_route')
    if bias != 'auto' and not routes[bias]['available']:
        raise ValueError('route_unavailable')
    reason = data['reason']
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 400 or any(ord(c) < 32 for c in reason):
        raise ValueError('invalid_reason')
    return Strategy(data['profile'], bias, reason.strip())


class Supervisor:
    def __init__(self, run_id, client=None, interval=30, max_age=45, max_requests=80, audit_path=None):
        self.run_id = run_id
        self.client = client or LLMClient()
        self.interval = interval
        self.max_age = max_age
        self.max_requests = max_requests
        self.audit_path = Path(audit_path) if audit_path else None
        self.results = Queue(maxsize=1)
        self.pending = False
        self.closed = False
        self.next_request = 1
        self.applied_at = None
        self.source_time = None
        self.strategy = Strategy()
        self.stats = {'requests': 0, 'accepted': 0, 'rejected': 0, 'errors': 0, 'input_tokens': 0, 'output_tokens': 0, 'last_latency_ms': None}
        self.status = 'waiting' if self.client.ready else 'not_configured'
        self.reason = 'API LLM belum dihubungkan, kendali memakai heuristik' if not self.client.ready else 'Menunggu ringkasan kondisi pertama'
        self.history = []

    def _record(self, entry):
        entry = {'run_id': self.run_id, **self.client.public_config(), **entry}
        self.history.append(entry)
        self.history = self.history[-12:]
        if self.audit_path:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self.audit_path.open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def _request(self, snapshot):
        started = time.monotonic()
        try:
            data, usage = self.client.decide(snapshot)
            if not isinstance(usage, dict) or any(isinstance(usage.get(key, 0), bool) or not isinstance(usage.get(key, 0), int) or not 0 <= usage.get(key, 0) <= 100000000 for key in ('input', 'output')):
                raise ValueError('invalid_token_usage')
            result = (snapshot, data, usage, None, round((time.monotonic() - started) * 1000))
        except Exception as exc:
            reason = str(exc) if isinstance(exc, ValueError) and str(exc).startswith(('api_', 'provider_')) else 'invalid_api_response'
            result = (snapshot, None, {}, reason, round((time.monotonic() - started) * 1000))
        if not self.closed:
            self.results.put_nowait(result)

    def update(self, now, metrics, routes):
        try:
            snapshot, data, usage, error, latency = self.results.get_nowait()
        except Empty:
            pass
        else:
            self.pending = False
            self.stats['last_latency_ms'] = latency
            for key in ('input', 'output'):
                self.stats[key + '_tokens'] += max(0, int(usage.get(key, 0)))
            if error:
                self.stats['errors'] += 1
                self.strategy = Strategy()
                self.applied_at = None
                self.status = 'fallback'
                self.reason = 'API tidak tersedia, tiga agen kembali ke heuristik'
                self._record({'time': now, 'status': 'fallback', 'error': error, 'latency_ms': latency, 'snapshot': snapshot})
            else:
                try:
                    decision = validate_decision(data, snapshot, now, self.run_id, self.max_age)
                    current = {route['name']: route for route in routes}
                    if decision.route_bias != 'auto' and not current.get(decision.route_bias, {}).get('available'):
                        raise ValueError('route_no_longer_available')
                except ValueError as exc:
                    self.stats['rejected'] += 1
                    self.strategy = Strategy()
                    self.applied_at = None
                    self.status = 'fallback'
                    self.reason = 'Saran tidak berlaku untuk kondisi sekarang, memakai heuristik'
                    self._record({'time': now, 'status': 'rejected', 'error': str(exc), 'latency_ms': latency, 'snapshot': snapshot})
                else:
                    self.stats['accepted'] += 1
                    self.strategy = decision
                    self.applied_at = now
                    self.source_time = snapshot['simulation_time']
                    self.status = 'active'
                    self.reason = decision.reason
                    self._record({'time': now, 'source_time': snapshot['simulation_time'], 'status': 'accepted', 'profile': decision.profile, 'route_bias': decision.route_bias, 'reason': decision.reason, 'latency_ms': latency, 'snapshot': snapshot, 'tokens': usage})
        if self.applied_at is not None and now - self.source_time > self.max_age:
            self.strategy = Strategy()
            self.applied_at = None
            self.status = 'fallback'
            self.reason = 'Masa berlaku strategi habis, tiga agen memakai heuristik'
        if self.client.ready and not self.pending and now >= self.next_request and self.stats['requests'] < self.max_requests:
            snapshot = {'run_id': self.run_id, 'simulation_time': now, 'metrics': metrics, 'routes': routes}
            self.stats['requests'] += 1
            self.pending = True
            self.next_request = now + self.interval
            if self.applied_at is None:
                self.status = 'waiting'
            threading.Thread(target=self._request, args=(snapshot,), daemon=True).start()
        return self.strategy

    def telemetry(self):
        return {**self.client.public_config(), **self.stats, 'status': self.status, 'reason': self.reason, 'profile': self.strategy.profile, 'route_bias': self.strategy.route_bias, 'pending': self.pending, 'applied_at': self.applied_at, 'history': self.history, 'external_decisions': self.stats['accepted'] > 0}

    def close(self):
        self.closed = True
