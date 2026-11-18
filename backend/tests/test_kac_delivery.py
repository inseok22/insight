"""KAC single dashboards, configuration privacy and direct access restrictions."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app.api.router import api_router
from app.api.admin import resource
from app.api.external import td
from app.core.config import Settings
from app.dependencies.auth import get_current_active_admin
from app.services import slurm_service


class KacDeliveryTest(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(_env_file=None, monitoring_scope='kac', terminal_enabled=True,
                                 resource_reservations_enabled=True,
                                 job_url='https://excluded.test/job')
        for module in ('app.api.v1.endpoints.config', 'app.dependencies.features',
                       'app.api.v1.endpoints.terminals'):
            patcher = patch(f'{module}.get_settings', return_value=self.settings)
            patcher.start()
            self.addCleanup(patcher.stop)
        app = FastAPI()
        app.include_router(api_router, prefix='/api/v1')
        app.include_router(resource.router, prefix='/api')
        app.include_router(td.router, prefix='/api')
        self.app = app
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def authenticate(self):
        self.app.dependency_overrides[get_current_active_admin] = lambda: object()

    def test_config_is_private_and_defaults_have_no_registered_urls(self):
        public = self.client.get('/api/v1/config/product').json()
        self.assertEqual(public['features'],
                         ['vllm', 'vllm_observability', 'trace', 'user_trace', 'gpu', 'server'])
        self.assertNotIn('dashboard_targets', public)
        self.assertEqual(self.client.get('/api/v1/config/frontend').status_code, 401)
        self.authenticate()
        data = self.client.get('/api/v1/config/frontend').json()
        self.assertEqual(data['dashboard_layout'], 'single-dashboard')
        self.assertNotIn('dashboard_groups', data)
        self.assertEqual(data['terminals'], [])
        self.assertIsNone(data['dashboards']['job_url'])
        for key in ('vllm_observability_url', 'trace_url', 'user_trace_url'):
            self.assertIsNone(data['dashboards'][key])
        for key in ('gpu_url', 'node_url', 'vllm_url'):
            self.assertEqual(data['dashboard_targets'][key], [])
            self.assertIsNone(data['dashboards'][key])

    def test_each_dashboard_uses_one_complete_url_without_service_metadata(self):
        self.authenticate()
        fields = ('gpu_url', 'node_url', 'vllm_url', 'vllm_observability_url', 'trace_url', 'user_trace_url')
        for key in fields:
            setattr(self.settings, key, f'https://example.test/d/{key}?orgId=1&var-server=All&kiosk=true')
        data = self.client.get('/api/v1/config/frontend').json()
        for key in fields:
            self.assertEqual(data['dashboards'][key], getattr(self.settings, key))
        for key in ('gpu_url', 'node_url', 'vllm_url'):
            self.assertEqual(len(data['dashboard_targets'][key]), 1)
            self.assertEqual(data['dashboard_targets'][key][0]['url'], getattr(self.settings, key))
        self.assertNotIn('example.test', json.dumps(self.client.get('/api/v1/config/product').json()))
        self.settings.vllm_url = 'https://example.test/d/new-llm'
        updated = self.client.get('/api/v1/config/frontend').json()
        self.assertEqual(updated['dashboards']['vllm_url'], self.settings.vllm_url)

    def test_direct_disabled_http_and_websocket_routes(self):
        paths = [('get', '/api/admin/resource/reservations'),
                 ('get', '/api/admin/resource/reservation-requests'),
                 ('post', '/api/external/td/resource-reservation-requests'),
                 ('get', '/api/v1/terminals/targets')]
        paths += [('post', f'/api/admin/resource/reservation-requests/1/{action}')
                  for action in ('approve', 'reject', 'retry-slurm')]
        for method, path in paths:
            with self.subTest(path=path):
                self.assertEqual(getattr(self.client, method)(path).status_code, 403)
        for method, path in [('get', '/api/v1/users'), ('post', '/api/v1/auth/register')]:
            self.assertEqual(getattr(self.client, method)(path).status_code, 404)
        with self.assertRaises(WebSocketDisconnect) as error:
            with self.client.websocket_connect('/api/v1/ws/term/master?token=unused'):
                pass
        self.assertEqual(error.exception.code, 1008)

    def test_old_lists_and_invalid_urls_fail_without_exposing_values(self):
        target = {'id': 'llm-1', 'name': '공항 안내 LLM', 'url': 'https://example.test/llm'}
        invalid = ['not-a-url', '{}', '[broken', '[]', json.dumps([target]), json.dumps([target, target]),
                   'javascript:alert(1)', 'file:///private', 'https://user:private-password@example.test']
        for field in ('gpu_url', 'node_url', 'vllm_url'):
            for value in invalid:
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValidationError) as error:
                        Settings(_env_file=None, monitoring_scope='kac', **{field: value})
                    self.assertNotIn('input_value', str(error.exception))
                    self.assertNotIn('private-password', str(error.exception))
        # Other deliveries retain their named target list format.
        settings = Settings(_env_file=None, monitoring_scope='profile', vllm_url=json.dumps([target]))
        self.assertEqual(json.loads(settings.vllm_url), [target])

    def test_empty_urls_and_template_are_valid(self):
        self.authenticate()
        for value in (None, '', '  '):
            self.settings.vllm_url = Settings(_env_file=None, monitoring_scope='kac', vllm_url=value).vllm_url
            data = self.client.get('/api/v1/config/frontend').json()
            self.assertIsNone(data['dashboards']['vllm_url'])
            self.assertEqual(data['dashboard_targets']['vllm_url'], [])
        template = Path(__file__).resolve().parents[2] / 'docs/kac-dashboard-urls.env.example'
        settings = Settings(_env_file=template)
        self.assertEqual(settings.monitoring_scope, 'kac')
        self.assertEqual(settings.gpu_url, '')
        self.assertEqual(settings.node_url, '')
        self.assertEqual(settings.vllm_url, '')


class SlurmRealConnectionTest(unittest.TestCase):
    def test_missing_credentials_fail_even_if_obsolete_mock_flag_is_present(self):
        settings = Settings(_env_file=None, SLURM_RESERVATION_MOCK=True)
        with patch.object(slurm_service, 'get_settings', return_value=settings), \
             patch.object(slurm_service, 'urlopen') as request:
            for result in (slurm_service.create_or_update_slurm_reservation({}),
                           slurm_service.list_slurm_reservations()):
                self.assertFalse(result.success)
                self.assertIn('not configured', result.error)
            request.assert_not_called()

    def test_configured_reservation_uses_the_real_request_path(self):
        settings = Settings(_env_file=None, SLURM_REST_USER_NAME='test-user',
                            SLURM_REST_USER_TOKEN='test-token')
        with patch.object(slurm_service, 'get_settings', return_value=settings), \
             patch.object(slurm_service, 'urlopen') as request:
            request.return_value.__enter__.return_value.read.return_value = b'{"reservations":[]}'
            self.assertTrue(slurm_service.create_or_update_slurm_reservation({'name': 'test'}).success)
            self.assertEqual(request.call_args.args[0].method, 'POST')
            self.assertTrue(slurm_service.list_slurm_reservations().success)
            self.assertEqual(request.call_args.args[0].method, 'GET')
