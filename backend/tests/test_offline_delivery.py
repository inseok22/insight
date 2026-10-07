import base64
import hashlib
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app.core.config import Settings
from app.core.product import product_config
from app.core.security import verify_password
from app.api.v1.endpoints import config, terminals
from app.dependencies.auth import get_current_active_admin


class OfflineDeliveryTest(unittest.TestCase):
    def test_scope_limits_config_http_and_websocket_even_if_terminal_flag_true(self):
        settings = Settings(_env_file=None, monitoring_scope='gpu_llm', terminal_enabled=True,
                            node_url='https://excluded.test/server', vllm_url='https://example.test/llm')
        self.assertEqual(product_config(settings)['features'], ['gpu', 'vllm'])
        app = FastAPI()
        app.include_router(config.router, prefix='/api/v1')
        app.include_router(terminals.router, prefix='/api/v1')
        app.dependency_overrides[get_current_active_admin] = lambda: object()
        with patch('app.api.v1.endpoints.config.get_settings', return_value=settings), \
             patch('app.dependencies.features.get_settings', return_value=settings), \
             patch('app.api.v1.endpoints.terminals.get_settings', return_value=settings), TestClient(app) as client:
            data = client.get('/api/v1/config/frontend').json()
            self.assertEqual(data['dashboard_layout'], 'single-server')
            self.assertIsNone(data['dashboards']['node_url'])
            self.assertEqual(data['terminals'], [])
            self.assertEqual(client.get('/api/v1/terminals/targets').status_code, 403)
            with self.assertRaises(WebSocketDisconnect):
                with client.websocket_connect('/api/v1/ws/term/master'):
                    pass

    def test_initial_hash_is_validated_and_verifies_without_plaintext_config(self):
        salt = b'12345678'
        hashed = '{SSHA}' + base64.b64encode(hashlib.sha1(b'test-password' + salt).digest() + salt).decode()
        settings = Settings(_env_file=None, initial_admin_password_hash=hashed)
        self.assertTrue(verify_password('test-password', settings.initial_admin_password_hash))
        for value in ('plain-password', '{SSHA}bad', '{SSHA}YWJj'):
            with self.assertRaises(ValidationError):
                Settings(_env_file=None, initial_admin_password_hash=value)
