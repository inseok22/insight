"""Administrator hash migration against temporary SQLite, never deployment DBs."""
import base64
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pwdlib import PasswordHash
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.api.v1.endpoints import auth
from app.core.config import Settings
from app.core.security import hash_admin_password, hash_password, verify_password
from app.db.session import get_admin_db
from app.models.admin import Admin
from app.models.user import User
from app.schemas.user import UserCreate
from app.services import admin_service
from app.services.user_service import create_user


PASSWORD = "test-only-관리자-password"


def legacy_ssha(password=PASSWORD):
    salt = b"testsalt"
    digest = hashlib.sha1(password.encode("utf-8") + salt).digest()
    return "{SSHA}" + base64.b64encode(digest + salt).decode("ascii")


class AdminHashTest(unittest.TestCase):
    def test_pbkdf2_format_matches_independent_sha256_computation(self):
        encoded = hash_admin_password(PASSWORD)
        algorithm, iterations, salt, digest = encoded.split("$")
        self.assertEqual(algorithm, "pbkdf2_sha256")
        self.assertEqual(iterations, "600000")
        self.assertRegex(salt, r"^[0-9a-f]{32}$")
        decoded = base64.b64decode(digest, validate=True)
        self.assertEqual(len(decoded), 32)
        self.assertEqual(decoded, hashlib.pbkdf2_hmac("sha256", PASSWORD.encode("utf-8"),
                                                    salt.encode("utf-8"), 600000))
        self.assertLessEqual(len(encoded), 255)
        self.assertTrue(verify_password(PASSWORD, encoded))
        self.assertFalse(verify_password("incorrect-password", encoded))

    def test_same_password_gets_distinct_random_salts(self):
        first, second = hash_admin_password(PASSWORD), hash_admin_password(PASSWORD)
        self.assertNotEqual(first.split("$")[2], second.split("$")[2])
        self.assertNotEqual(first, second)

    def test_old_ssha_and_argon2_still_verify(self):
        for encoded in (legacy_ssha(), PasswordHash.recommended().hash(PASSWORD)):
            with self.subTest(scheme=encoded.partition("$")[0] or "argon2"):
                self.assertTrue(verify_password(PASSWORD, encoded))
                self.assertFalse(verify_password("incorrect-password", encoded))

    def test_malformed_hashes_fail_closed(self):
        salt = "a" * 32
        digest = base64.b64encode(b"d" * 32).decode("ascii")
        invalid = [
            "", "plain-password", "{SSHA}bad", "{SSHA}YWJj", "{SSHA256}unsupported",
            "$argon2id$malformed", "pbkdf2_sha256", "pbkdf2_sha256$600000$missing-digest",
            f"pbkdf2_sha256$0${salt}${digest}", f"pbkdf2_sha256$-1${salt}${digest}",
            f"pbkdf2_sha256$invalid${salt}${digest}",
            f"pbkdf2_sha256$10000001${salt}${digest}",
            f"pbkdf2_sha256$600000$short${digest}", f"pbkdf2_sha256$600000${'z' * 32}${digest}",
            f"pbkdf2_sha256$600000${salt}$invalid-base64",
            f"pbkdf2_sha256$600000${salt}${base64.b64encode(b'short').decode()}",
            f"pbkdf2_sha256$600000${salt}${digest}$unexpected-field",
        ]
        for index, encoded in enumerate(invalid):
            with self.subTest(case=index):
                self.assertFalse(verify_password(PASSWORD, encoded))

    def test_initial_hash_setting_accepts_new_and_existing_schemes(self):
        for encoded in (hash_admin_password(PASSWORD), legacy_ssha()):
            with self.subTest(scheme=encoded.split("$")[0]):
                settings = Settings(_env_file=None, initial_admin_password_hash=encoded)
                self.assertEqual(settings.initial_admin_password_hash, encoded)
                self.assertTrue(verify_password(PASSWORD, settings.initial_admin_password_hash))

    def test_initial_hash_setting_rejects_plaintext_and_malformed_values(self):
        for value in ("do-not-display-this-password", "{SSHA}bad", "pbkdf2_sha256$broken"):
            with self.subTest(case=value.partition("$")[0]):
                with self.assertRaises(ValidationError) as caught:
                    Settings(_env_file=None, initial_admin_password_hash=value)
                self.assertNotIn(value, str(caught.exception))

    def test_initial_hash_setting_rejects_insufficient_iteration_count(self):
        salt = "b" * 32
        digest = base64.b64encode(hashlib.pbkdf2_hmac("sha256", PASSWORD.encode(), salt.encode(), 1)).decode()
        encoded = f"pbkdf2_sha256$1${salt}${digest}"
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, initial_admin_password_hash=encoded)

    def test_desk_hash_function_preserves_ldap_ssha_format(self):
        encoded = hash_password(PASSWORD)
        self.assertTrue(encoded.startswith("{SSHA}"))
        decoded = base64.b64decode(encoded[6:], validate=True)
        self.assertEqual(len(decoded), 28)
        self.assertEqual(decoded[:20], hashlib.sha1(PASSWORD.encode("utf-8") + decoded[20:]).digest())


class AdminMigrationTest(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.engine = create_engine(f"sqlite:///{Path(directory.name) / 'accounts.sqlite'}",
                                    connect_args={"check_same_thread": False})
        self.addCleanup(self.engine.dispose)
        Admin.__table__.create(self.engine)
        User.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.db.close)
        signing_settings = patch("app.core.security.settings", Settings(
            _env_file=None, secret_key="unit-test-signing-key-that-is-at-least-32-bytes"))
        signing_settings.start()
        self.addCleanup(signing_settings.stop)

    def seed_admin(self, encoded, *, username="test-admin", active=True):
        admin = Admin(username=username, password_hash=encoded, full_name="Test Administrator", is_active=active)
        self.db.add(admin)
        self.db.commit()
        return admin

    def persisted_admin(self, admin_id):
        with Session(self.engine) as fresh:
            admin = fresh.get(Admin, admin_id)
            fresh.expunge(admin)
            return admin

    def test_successful_ssha_login_commits_upgrade_and_preserves_account_identity(self):
        before = legacy_ssha()
        admin = self.seed_admin(before)
        admin_id = admin.id
        result = admin_service.authenticate_admin(self.db, admin.username, PASSWORD)
        self.assertEqual(result.id, admin_id)
        stored = self.persisted_admin(admin_id)
        self.assertTrue(stored.password_hash.startswith("pbkdf2_sha256$600000$"))
        self.assertNotEqual(stored.password_hash, before)
        self.assertTrue(verify_password(PASSWORD, stored.password_hash))
        self.assertEqual(stored.username, "test-admin")
        self.assertEqual(stored.full_name, "Test Administrator")
        self.assertTrue(stored.is_active)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Admin)), 1)

    def test_successful_legacy_argon2_login_commits_upgrade(self):
        admin = self.seed_admin(PasswordHash.recommended().hash(PASSWORD))
        admin_service.authenticate_admin(self.db, admin.username, PASSWORD)
        stored = self.persisted_admin(admin.id)
        self.assertTrue(stored.password_hash.startswith("pbkdf2_sha256$600000$"))
        self.assertTrue(verify_password(PASSWORD, stored.password_hash))

    def test_wrong_password_and_missing_account_do_not_write(self):
        before = legacy_ssha()
        admin = self.seed_admin(before)
        with patch.object(self.db, "commit", wraps=self.db.commit) as commit:
            self.assertIsNone(admin_service.authenticate_admin(self.db, admin.username, "incorrect-password"))
            self.assertIsNone(admin_service.authenticate_admin(self.db, "missing-admin", PASSWORD))
            commit.assert_not_called()
        self.assertEqual(self.persisted_admin(admin.id).password_hash, before)

    def test_inactive_admin_is_not_rehashed(self):
        before = legacy_ssha()
        admin = self.seed_admin(before, active=False)
        with patch.object(self.db, "commit", wraps=self.db.commit) as commit:
            admin_service.authenticate_admin(self.db, admin.username, PASSWORD)
            commit.assert_not_called()
        self.assertEqual(self.persisted_admin(admin.id).password_hash, before)

    def test_current_pbkdf2_login_does_not_rehash_or_commit(self):
        before = hash_admin_password(PASSWORD)
        admin = self.seed_admin(before)
        with patch.object(self.db, "commit", wraps=self.db.commit) as commit:
            result = admin_service.authenticate_admin(self.db, admin.username, PASSWORD)
            self.assertEqual(result.id, admin.id)
            commit.assert_not_called()
        self.assertEqual(self.persisted_admin(admin.id).password_hash, before)

    def test_malformed_stored_hash_returns_authentication_failure(self):
        admin = self.seed_admin("unrecognized-hash")
        with patch.object(self.db, "commit", wraps=self.db.commit) as commit:
            self.assertIsNone(admin_service.authenticate_admin(self.db, admin.username, PASSWORD))
            commit.assert_not_called()

    def test_stale_login_cannot_overwrite_a_concurrent_password_change(self):
        before = legacy_ssha()
        admin = self.seed_admin(before)
        admin_id = admin.id
        replacement = hash_admin_password("replacement-test-password")
        with Session(self.engine) as another:
            another.get(Admin, admin_id).password_hash = replacement
            another.commit()
        self.assertEqual(admin.password_hash, before)

        self.assertIsNone(admin_service.authenticate_admin(self.db, admin.username, PASSWORD))
        self.assertEqual(self.persisted_admin(admin_id).password_hash, replacement)

    def test_stale_login_accepts_another_logins_completed_migration_without_overwriting_it(self):
        before = legacy_ssha()
        admin = self.seed_admin(before)
        admin_id = admin.id
        replacement = hash_admin_password(PASSWORD)
        with Session(self.engine) as another:
            another.get(Admin, admin_id).password_hash = replacement
            another.commit()
        self.assertEqual(admin.password_hash, before)

        result = admin_service.authenticate_admin(self.db, admin.username, PASSWORD)
        self.assertEqual(result.id, admin_id)
        self.assertEqual(self.persisted_admin(admin_id).password_hash, replacement)

    def test_password_reset_after_migration_commit_prevents_old_password_login(self):
        admin = self.seed_admin(legacy_ssha())
        admin_id, username = admin.id, admin.username
        replacement = hash_admin_password("reset-after-migration-test-password")
        commit = self.db.commit

        def commit_then_reset():
            commit()
            with Session(self.engine) as another:
                another.get(Admin, admin_id).password_hash = replacement
                another.commit()

        with patch.object(self.db, "commit", side_effect=commit_then_reset):
            result = admin_service.authenticate_admin(self.db, username, PASSWORD)
        self.assertIsNone(result)
        self.assertEqual(self.persisted_admin(admin_id).password_hash, replacement)

    def test_account_deleted_after_migration_commit_returns_authentication_failure(self):
        admin = self.seed_admin(legacy_ssha())
        admin_id, username = admin.id, admin.username
        commit = self.db.commit

        def commit_then_delete():
            commit()
            with Session(self.engine) as another:
                another.delete(another.get(Admin, admin_id))
                another.commit()

        with patch.object(self.db, "commit", side_effect=commit_then_delete):
            result = admin_service.authenticate_admin(self.db, username, PASSWORD)
        self.assertIsNone(result)
        with Session(self.engine) as fresh:
            self.assertIsNone(fresh.get(Admin, admin_id))

    def test_initial_admin_from_password_uses_pbkdf2(self):
        settings = Settings(_env_file=None, initial_admin_username="new-admin", initial_admin_password=PASSWORD)
        with patch.object(admin_service, "settings", settings):
            admin_service.ensure_initial_admin(self.db)
        admin = self.db.scalar(select(Admin).where(Admin.username == "new-admin"))
        self.assertTrue(admin.password_hash.startswith("pbkdf2_sha256$600000$"))
        self.assertTrue(verify_password(PASSWORD, admin.password_hash))

    def test_initial_admin_accepts_prehashed_configuration_without_changing_it(self):
        for index, encoded in enumerate((hash_admin_password(PASSWORD), legacy_ssha())):
            with self.subTest(case=index):
                settings = Settings(_env_file=None, initial_admin_username=f"prehashed-{index}",
                                    initial_admin_password_hash=encoded)
                with patch.object(admin_service, "settings", settings):
                    admin_service.ensure_initial_admin(self.db)
                admin = self.db.scalar(select(Admin).where(Admin.username == settings.initial_admin_username))
                self.assertEqual(admin.password_hash, encoded)

    def test_initial_settings_do_not_overwrite_existing_account(self):
        before = legacy_ssha()
        admin = self.seed_admin(before)
        settings = Settings(_env_file=None, initial_admin_username=admin.username,
                            initial_admin_password="different-test-password",
                            initial_admin_password_hash=hash_admin_password("another-test-password"))
        with patch.object(admin_service, "settings", settings), \
             patch.object(self.db, "commit", wraps=self.db.commit) as commit:
            admin_service.ensure_initial_admin(self.db)
            commit.assert_not_called()
        self.assertEqual(self.persisted_admin(admin.id).password_hash, before)

    def test_desk_user_creation_still_stores_ssha(self):
        user = create_user(self.db, UserCreate(username="desk-user", password=PASSWORD,
                                              surname="테스트", given_name="사용자"))
        with Session(self.engine) as fresh:
            stored = fresh.get(User, user.id)
            self.assertTrue(stored.password_hash.startswith("{SSHA}"))
            self.assertTrue(verify_password(PASSWORD, stored.password_hash))

    def test_both_login_endpoints_upgrade_without_exposing_password_hash(self):
        app = FastAPI()
        app.include_router(auth.router, prefix="/api/v1")

        def temporary_db():
            with Session(self.engine) as db:
                yield db

        app.dependency_overrides[get_admin_db] = temporary_db
        with TestClient(app) as client:
            for endpoint in ("login", "token"):
                with self.subTest(endpoint=endpoint):
                    admin = self.seed_admin(legacy_ssha(), username=f"test-{endpoint}")
                    payload = {"username": admin.username, "password": PASSWORD}
                    response = client.post(f"/api/v1/auth/{endpoint}",
                                           **({"json": payload} if endpoint == "login" else {"data": payload}))
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json()["user"]["id"], admin.id)
                    self.assertNotIn("password_hash", response.text)
                    self.assertNotIn(PASSWORD, response.text)
                    self.assertTrue(self.persisted_admin(admin.id).password_hash.startswith("pbkdf2_sha256$600000$"))

    def test_inactive_login_endpoints_remain_forbidden_and_leave_hash_unchanged(self):
        app = FastAPI()
        app.include_router(auth.router, prefix="/api/v1")

        def temporary_db():
            with Session(self.engine) as db:
                yield db

        app.dependency_overrides[get_admin_db] = temporary_db
        before = legacy_ssha()
        admin = self.seed_admin(before, active=False)
        payload = {"username": admin.username, "password": PASSWORD}
        with TestClient(app) as client:
            for endpoint in ("login", "token"):
                with self.subTest(endpoint=endpoint):
                    response = client.post(f"/api/v1/auth/{endpoint}",
                                           **({"json": payload} if endpoint == "login" else {"data": payload}))
                    self.assertEqual(response.status_code, 403, response.text)
                    self.assertNotIn("password_hash", response.text)
                    self.assertEqual(self.persisted_admin(admin.id).password_hash, before)


if __name__ == "__main__":
    unittest.main()
