import importlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient


class BackendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.environment = patch.dict(os.environ, {'KATUP_STATE': cls.directory.name, 'KATUP_STANDALONE': '1', 'KATUP_PUBLIC_MODE': '1', 'KATUP_FRONTEND_ORIGINS': 'https://katup.pages.dev', 'KATUP_LLM_PROVIDER': 'disabled'})
        cls.environment.start()
        cls.server = importlib.import_module('deploy.server')

    @classmethod
    def tearDownClass(cls):
        cls.environment.stop()
        cls.directory.cleanup()

    def test_catalog_network_and_api_key_not_exposed(self):
        with TestClient(self.server.app) as client:
            data = client.get('/api/catalog').json()
            self.assertEqual(set(data['modes']), {'baseline', 'katup', 'hybrid'})
            self.assertFalse(data['llm']['configured'])
            self.assertNotIn('key', data['llm'])
            for corridor in data['corridors']:
                network = client.get('/api/network', params={'corridor': corridor['id']}).json()
                self.assertGreater(len(network['edges']), 30)
                self.assertIn(network['case']['profile']['pre'], {e['id'] for e in network['edges']})
            self.assertEqual(client.get('/api/network?corridor=wrong').status_code, 400)

    def test_origins_and_options(self):
        with TestClient(self.server.app) as client:
            response = client.options('/api/start/hybrid', headers={'Origin': 'https://katup.pages.dev', 'Access-Control-Request-Method': 'POST'})
            self.assertEqual(response.status_code, 204)
            self.assertEqual(response.content, b'')
            self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'https://katup.pages.dev')
            self.assertEqual(client.post('/api/stop', headers={'Origin': 'https://wrong.example'}).status_code, 403)
            self.assertEqual(client.post('/api/start/not-a-mode', headers={'Origin': 'https://katup.pages.dev'}).status_code, 400)
            self.assertEqual(client.post('/api/start/hybrid?corridor=bad', headers={'Origin': 'https://katup.pages.dev'}).status_code, 400)
            self.assertEqual(client.get('/api/desktop').status_code, 403)

    def test_websocket_observes_and_denies_other_origins(self):
        with TestClient(self.server.app) as client:
            with client.websocket_connect('/api/stream', headers={'Origin': 'https://katup.pages.dev'}) as ws:
                data = ws.receive_json()
                self.assertIn('hybrid', data['comparison'])
                self.assertFalse(data['telemetry']['running'])
            from starlette.websockets import WebSocketDisconnect
            with self.assertRaises(WebSocketDisconnect):
                with client.websocket_connect('/api/stream', headers={'Origin': 'https://wrong.example'}):
                    pass


if __name__ == '__main__':
    unittest.main()
