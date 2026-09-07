"""Profile contracts and direct API access, without DB or external services."""
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app.core.config import Settings
from app.api.v1.endpoints import config, terminals
from app.api.admin import resource
from app.api.external import td
from app.dependencies.auth import get_current_active_admin, get_current_admin_user
from app.db.session import get_admin_db


class ProductProfilesTest(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(_env_file=None, product_profile='llm',
            vllm_url='https://example.test/llm', job_url='https://example.test/job',
            overview_url='https://example.test/unfinished', terminal_targets='master,node-a')
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
        self.assertTrue({'job', 'power', 'hpc_dashboard'}.isdisjoint(data['features']))

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
            self.assertEqual([t['key'] for t in data['terminals']], ['master', 'node-a'])

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
