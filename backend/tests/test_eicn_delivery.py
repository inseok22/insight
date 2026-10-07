"""EICN delivery restrictions must also hold for direct API requests."""
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import api_router
from app.api.admin import resource
from app.api.external import td
from app.core.config import Settings
from app.core.product import product_config


class EicnDeliveryTest(unittest.TestCase):
    def test_reservations_stay_disabled_even_with_environment_flag_enabled(self):
        for profile in ("hpc", "llm"):
            settings = Settings(_env_file=None, product_profile=profile, resource_reservations_enabled=True)
            self.assertNotIn("resource_reservations", product_config(settings)["features"])
            app = FastAPI()
            app.include_router(resource.router, prefix="/api")
            app.include_router(td.router, prefix="/api")
            paths = [("get", "/api/admin/resource/reservations"),
                     ("get", "/api/admin/resource/reservation-requests"),
                     ("post", "/api/external/td/resource-reservation-requests")]
            paths += [("post", f"/api/admin/resource/reservation-requests/1/{action}")
                      for action in ("approve", "reject", "retry-slurm")]
            with patch("app.dependencies.features.get_settings", return_value=settings), TestClient(app) as client:
                for method, path in paths:
                    with self.subTest(profile=profile, path=path):
                        self.assertEqual(getattr(client, method)(path).status_code, 403)

    def test_approval_management_and_public_registration_unmounted(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api/v1")
        with TestClient(app) as client:
            for method, path in (("get", "/api/v1/users"), ("get", "/api/v1/users/1"),
                                 ("patch", "/api/v1/users/1/approval"), ("post", "/api/v1/users"),
                                 ("post", "/api/v1/auth/register")):
                with self.subTest(path=path, method=method):
                    self.assertEqual(getattr(client, method)(path).status_code, 404)
        for path in ("/api/v1/auth/login", "/api/v1/auth/token"):
            self.assertTrue(any(route.path == path and "POST" in route.methods
                                for route in app.routes))
