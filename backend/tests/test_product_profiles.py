"""Profile contracts and direct API access, without DB or external services."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app.core.config import Settings
from app.core.dashboard_targets import parse_dashboard_targets
from app.api.v1.endpoints import config, terminals
from app.api.admin import resource
from app.api.external import td
from app.dependencies.auth import get_current_active_admin, get_current_admin_user
from app.db.session import get_admin_db


class ProductProfilesTest(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(_env_file=None, product_profile='llm',
            vllm_url='https://example.test/llm', job_url='https://example.test/job',
            overview_url='https://example.test/unfinished', terminal_targets='master,node-a',
            k8s_url='https://example.test/k8s', snmp_url='https://example.test/network')
        self.patches = [patch(f'{module}.get_settings', return_value=self.settings) for module in (
            'app.api.v1.endpoints.config', 'app.dependencies.features',
            'app.api.v1.endpoints.terminals')]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        app = FastAPI()
        app.include_router(config.router, prefix='/api/v1')
        app.include_router(terminals.router, prefix='/api/v1')
        app.include_router(resource.router, prefix='/api')
        app.include_router(td.router, prefix='/api')
        self.app = app
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def authenticate(self):
        self.app.dependency_overrides[get_current_active_admin] = lambda: object()
        self.app.dependency_overrides[get_current_admin_user] = lambda: object()
        self.app.dependency_overrides[get_admin_db] = lambda: None

    def test_public_llm_profile_contains_no_urls_or_credentials(self):
        data = self.client.get('/api/v1/config/product').json()
        self.assertEqual(set(data), {'profile', 'product_name', 'short_name', 'home_path', 'features'})
        self.assertEqual(data['product_name'], 'T-LLM Observability')
        self.assertEqual(data['home_path'], '/ops/vllm')
        self.assertTrue({'vllm', 'vllm_observability', 'trace', 'user_trace'} <= set(data['features']))
        self.assertTrue({'gpu', 'server'} <= set(data['features']))
        self.assertTrue({'job', 'power', 'hpc_dashboard', 'kubernetes', 'network'}.isdisjoint(data['features']))

    def test_hpc_profile_and_home(self):
        self.settings.product_profile = 'hpc'
        data = self.client.get('/api/v1/config/product').json()
        self.assertEqual(data['product_name'], 'TSlurm Insight')
        self.assertEqual(data['home_path'], '/ops/k8s')
        self.assertTrue({'job', 'power', 'kubernetes', 'gpu', 'server', 'network'} <= set(data['features']))
        self.assertTrue({'vllm', 'vllm_observability', 'trace', 'user_trace', 'hpc_dashboard'}.isdisjoint(data['features']))

    def test_private_urls_require_authentication(self):
        self.assertEqual(self.client.get('/api/v1/config/frontend').status_code, 401)

    def test_disabled_dashboard_urls_are_not_disclosed(self):
        self.authenticate()
        for profile, enabled, disabled in [('llm', 'vllm_url', 'job_url'), ('hpc', 'job_url', 'vllm_url')]:
            self.settings.product_profile = profile
            data = self.client.get('/api/v1/config/frontend').json()
            self.assertIsNotNone(data['dashboards'][enabled])
            self.assertIsNone(data['dashboards'][disabled])
            self.assertIsNone(data['dashboards']['overview_url'])
            for field in ('k8s_url', 'snmp_url'):
                with self.subTest(profile=profile, field=field):
                    if profile == 'llm':
                        self.assertIsNone(data['dashboards'][field])
                    else:
                        self.assertIsNotNone(data['dashboards'][field])
            self.assertEqual([t['key'] for t in data['terminals']], ['master', 'node-a'])

    def test_target_lists_preserve_names_order_and_legacy_first_url(self):
        self.authenticate()
        expected = {}
        for field, count in [('gpu_url', 4), ('node_url', 5), ('vllm_url', 2)]:
            targets = [{'id': f'target-{n}', 'name': f'서버 {n}',
                        'url': f'https://example.test/{field}/{n}?orgId=1&from=now-15m&refresh=5s'}
                       for n in range(1, count + 1)]
            validated = Settings(_env_file=None, **{field: json.dumps(targets, ensure_ascii=False)})
            setattr(self.settings, field, getattr(validated, field))
            expected[field] = targets
        data = self.client.get('/api/v1/config/frontend').json()
        self.assertEqual(data['dashboard_targets'], expected)
        for field, targets in expected.items():
            self.assertEqual(data['dashboards'][field], targets[0]['url'])
        public = self.client.get('/api/v1/config/product').json()
        self.assertNotIn('dashboard_targets', public)
        self.assertNotIn('example.test', json.dumps(public))
        self.settings.product_profile = 'hpc'
        data = self.client.get('/api/v1/config/frontend').json()
        self.assertEqual(data['dashboard_targets']['vllm_url'], [])
        self.assertIsNone(data['dashboards']['vllm_url'])

    def test_single_url_and_empty_targets(self):
        self.authenticate()
        for value in (None, '', '  ', '[]'):
            self.settings.gpu_url = value
            with self.subTest(value=value):
                data = self.client.get('/api/v1/config/frontend').json()
                self.assertEqual(data['dashboard_targets']['gpu_url'], [])
                self.assertIsNone(data['dashboards']['gpu_url'])
        self.assertEqual(data['dashboard_targets']['vllm_url'], [
            {'id': 'default', 'name': 'vLLM', 'url': 'https://example.test/llm'}])

    def test_dotenv_json_list_with_korean_names_and_query_parameters(self):
        targets = [{'id': 'gpu-1', 'name': 'GPU 서버 1',
                    'url': 'https://example.test/d/gpu?var-host=gpu-1&from=now-15m&refresh=5s'},
                   {'id': 'gpu-2', 'name': 'GPU 서버 2', 'url': 'https://example.test/d/gpu-2'}]
        with TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            env = Path(directory) / '.env.backend'
            env.write_text("GPU_URL='" + json.dumps(targets, ensure_ascii=False) + "'\n", encoding='utf-8')
            settings = Settings(_env_file=env)
        self.assertEqual([target.model_dump() for target in parse_dashboard_targets(settings.gpu_url, 'GPU')], targets)

    def test_invalid_target_settings_fail_without_logging_values(self):
        valid = {'id': 'gpu-1', 'name': 'GPU 서버 1', 'url': 'https://example.test/gpu'}
        invalid = [
            '[broken', json.dumps([valid, valid]), json.dumps([{'id': 'gpu-1'}]),
            json.dumps([{**valid, 'name': ' '}]), json.dumps([{**valid, 'id': ''}]),
            json.dumps([None]), json.dumps(['https://example.test']),
            json.dumps([{**valid, 'url': 'javascript:alert(1)'}]),
            json.dumps([{**valid, 'url': 'https://user:secret@example.test'}]),
            json.dumps(valid), 'not-a-url',
        ]
        for field in ('gpu_url', 'node_url', 'vllm_url'):
            for value in invalid:
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValidationError) as error:
                        Settings(_env_file=None, **{field: value})
                    self.assertNotIn('input_value', str(error.exception))
                    self.assertNotIn('secret@example.test', str(error.exception))

    def test_reservation_disabled_blocks_all_admin_and_external_routes(self):
        self.authenticate()
        self.settings.resource_reservations_enabled = False
        paths = [('/api/admin/resource/reservations', 'get'),
                 ('/api/admin/resource/reservation-requests', 'get'),
                 ('/api/external/td/resource-reservation-requests', 'post')]
        paths += [(f'/api/admin/resource/reservation-requests/1/{action}', 'post')
                  for action in ('approve', 'reject', 'retry-slurm')]
        for path, method in paths:
            with self.subTest(path=path):
                self.assertEqual(getattr(self.client, method)(path).status_code, 403)

    def test_terminal_disabled_blocks_http_websocket_and_config(self):
        self.settings.terminal_enabled = False
        self.authenticate()
        self.assertEqual(self.client.get('/api/v1/terminals/targets').status_code, 403)
        with self.assertRaises(WebSocketDisconnect) as error:
            with self.client.websocket_connect('/api/v1/ws/term/master?token=unused'):
                pass
        self.assertEqual(error.exception.code, 1008)
        self.assertEqual(self.client.get('/api/v1/config/frontend').json()['terminals'], [])

    def test_unknown_profile_fails_validation(self):
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, product_profile='invalid')


if __name__ == '__main__':
    unittest.main()
