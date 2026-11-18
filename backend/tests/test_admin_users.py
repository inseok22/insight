"""Account creation and real login against isolated SQLite; no deployment DBs."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.api.router import api_router
from app.core.config import Settings
from app.core.security import create_access_token, hash_admin_password, verify_password
from app.db.session import get_admin_db
from app.models.admin import Admin


PASSWORD = "test-only-new-account-password"


class AdminUsersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin_hash = hash_admin_password("test-only-operator-password")

    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.engine = create_engine(f"sqlite:///{Path(directory.name) / 'admins.sqlite'}",
                                    connect_args={"check_same_thread": False})
        self.addCleanup(self.engine.dispose)
        Admin.__table__.create(self.engine)
        with Session(self.engine) as db:
            db.add(Admin(username="operator", password_hash=self.admin_hash, is_active=True))
            db.add(Admin(username="disabled", password_hash=self.admin_hash, is_active=False))
            db.commit()
        signing = patch("app.core.security.settings", Settings(
            _env_file=None, secret_key="test-only-signing-key-at-least-32-bytes"))
        signing.start()
        self.addCleanup(signing.stop)

        def database():
            with Session(self.engine) as db:
                yield db

        app = FastAPI()
        app.include_router(api_router, prefix="/api/v1")
        app.dependency_overrides[get_admin_db] = database
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.headers = {"Authorization": f"Bearer {create_access_token('operator')}"}

    def create(self, **changes):
        return self.client.post("/api/v1/admin/users", headers=self.headers, json={
            "username": "new-user", "full_name": "새 사용자", "password": PASSWORD, **changes})

    def test_create_then_login_and_me_use_new_username_without_exposing_password(self):
        response = self.create()
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["username"], "new-user")
        self.assertEqual(response.json()["role"], "admin")
        self.assertTrue(response.json()["is_active"])
        self.assertNotIn("password", response.text)
        self.assertNotIn(PASSWORD, response.text)
        with Session(self.engine) as db:
            saved = db.scalar(select(Admin).where(Admin.username == "new-user"))
            self.assertEqual(saved.full_name, "새 사용자")
            self.assertTrue(saved.password_hash.startswith("pbkdf2_sha256$"))
            self.assertTrue(verify_password(PASSWORD, saved.password_hash))
        login = self.client.post("/api/v1/auth/login", json={"username": "new-user", "password": PASSWORD})
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(login.json()["user"]["username"], "new-user")
        me = self.client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {login.json()['access_token']}"})
        self.assertEqual(me.json()["user"]["id"], response.json()["id"])
        wrong = self.client.post("/api/v1/auth/login", json={"username": "new-user", "password": "wrong"})
        self.assertEqual(wrong.status_code, 401)

    def test_missing_invalid_deleted_and_inactive_auth_cannot_create(self):
        for headers, status in [({}, 401), ({"Authorization": "Bearer invalid"}, 401),
                                ({"Authorization": f"Bearer {create_access_token('missing')}"}, 401),
                                ({"Authorization": f"Bearer {create_access_token('disabled')}"}, 403)]:
            with self.subTest(status=status, kind=bool(headers)):
                self.headers = headers
                self.assertEqual(self.create().status_code, status)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Admin)), 2)

    def test_duplicate_does_not_replace_existing_credentials(self):
        self.assertEqual(self.create(username="operator").status_code, 409)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(Admin).where(Admin.username == "operator")).password_hash,
                             self.admin_hash)

    def test_duplicate_race_is_conflict_and_rolls_back(self):
        with patch("app.services.admin_service.get_admin_by_username", side_effect=[None, object()]):
            self.assertEqual(self.create(username="operator").status_code, 409)
        self.assertEqual(self.create().status_code, 201)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Admin)), 3)

    def test_invalid_input_never_returns_submitted_passwords(self):
        cases = [
            {"username": ""}, {"username": " "}, {"username": "a" * 51},
            {"username": "has spaces"}, {"username": "<script>"}, {"full_name": "a" * 101},
            {"password": "short!"}, {"password": "secret" * 22},
            {"password": {"value": PASSWORD}}, {"role": "admin"}, {"is_active": True},
            {"password_confirm": PASSWORD},
        ]
        for values in cases:
            with self.subTest(fields=list(values)):
                response = self.create(**values)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertNotIn(PASSWORD, response.text)
                self.assertNotIn("short!", response.text)
                self.assertNotIn("secret", response.text)
                self.assertNotIn('"input"', response.text)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Admin)), 2)

    def test_malformed_json_does_not_echo_password(self):
        response = self.client.post("/api/v1/admin/users", headers={
            **self.headers, "Content-Type": "application/json"}, content='{"password":"' + PASSWORD)
        self.assertEqual(response.status_code, 422)
        self.assertNotIn(PASSWORD, response.text)

    def test_trimmed_identity_and_optional_name(self):
        response = self.create(username=" new-user ", full_name=" ")
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["username"], "new-user")
        self.assertIsNone(response.json()["full_name"])


if __name__ == "__main__":
    unittest.main()
