"""Optional image-bundled demo accounts, exercised only with temporary SQLite."""
import base64
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.security import hash_admin_password, verify_password
from app.db import init_db as db_initialization
from app.models.admin import Admin
from app.services import admin_service, demo_accounts


SEED_FILE = Path(__file__).resolve().parents[1] / "app" / "seed" / "demo_accounts.json"


class DemoAccountsTest(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.engine = create_engine(f"sqlite:///{Path(directory.name) / 'demo-accounts.sqlite'}")
        self.addCleanup(self.engine.dispose)
        Admin.__table__.create(self.engine)
        self.settings = Settings(_env_file=None, seed_demo_accounts=True)
        seed_settings = patch.object(demo_accounts, "settings", self.settings)
        seed_settings.start()
        self.addCleanup(seed_settings.stop)

    def seed(self):
        with Session(self.engine) as db:
            demo_accounts.ensure_demo_accounts(db)

    def accounts(self):
        with Session(self.engine) as db:
            return {admin.username: (admin.id, admin.password_hash, admin.is_active, admin.full_name)
                    for admin in db.scalars(select(Admin)).all()}

    def startup(self):
        initial = Settings(_env_file=None, initial_admin_username="test-initial-admin",
                           initial_admin_password_hash=hash_admin_password("test-only-initial-password"))
        with patch.object(db_initialization, "admin_engine", self.engine), \
             patch.object(db_initialization, "user_engine", self.engine), \
             patch.object(db_initialization, "AdminSessionLocal", sessionmaker(bind=self.engine)), \
             patch.object(admin_service, "settings", initial):
            db_initialization.init_db()

    def test_seed_contains_only_expected_accounts_and_salted_pbkdf2_hashes(self):
        records = json.loads(SEED_FILE.read_text(encoding="utf-8"))
        self.assertEqual({record["username"] for record in records}, {"user1", "user2"})
        self.assertEqual(len(records), 2)
        salts = set()
        for record in records:
            with self.subTest(username=record["username"]):
                self.assertEqual(set(record), {"username", "full_name", "password_hash"})
                algorithm, iterations, salt, digest = record["password_hash"].split("$")
                self.assertEqual(algorithm, "pbkdf2_sha256")
                self.assertEqual(iterations, "600000")
                self.assertRegex(salt, r"^[0-9a-f]{32}$")
                self.assertEqual(len(base64.b64decode(digest, validate=True)), 32)
                self.assertTrue(verify_password(record["username"], record["password_hash"]))
                salts.add(salt)
        self.assertEqual(len(salts), 2)

    def test_disabled_flag_does_not_create_accounts(self):
        self.settings.seed_demo_accounts = False
        self.seed()
        self.assertEqual(self.accounts(), {})

    def test_seed_is_idempotent_and_gives_each_account_its_own_id(self):
        self.seed()
        first = self.accounts()
        self.assertEqual(set(first), {"user1", "user2"})
        self.assertNotEqual(first["user1"][0], first["user2"][0])
        self.assertTrue(all(values[2] for values in first.values()))
        self.seed()
        self.assertTrue(self.accounts() == first, "Repeated seeding changed existing account records")

    def test_existing_named_accounts_keep_ids_passwords_and_active_status(self):
        with Session(self.engine) as db:
            db.add_all([
                Admin(id=40, username="user1", full_name="Existing active user",
                      password_hash=hash_admin_password("different-existing-password-one"), is_active=True),
                Admin(id=50, username="user2", full_name="Existing disabled user",
                      password_hash=hash_admin_password("different-existing-password-two"), is_active=False),
            ])
            db.commit()
        before = self.accounts()
        self.seed()
        self.assertTrue(self.accounts() == before, "Seeding overwrote an existing named account")

    def test_only_missing_account_is_added(self):
        with Session(self.engine) as db:
            db.add(Admin(id=70, username="user1", full_name="Existing user",
                         password_hash=hash_admin_password("existing-test-password"), is_active=False))
            db.commit()
        before = self.accounts()["user1"]
        self.seed()
        after = self.accounts()
        self.assertEqual(set(after), {"user1", "user2"})
        self.assertTrue(after["user1"] == before, "Partial seeding changed the existing account")
        self.assertTrue(after["user2"][2])
        self.assertNotEqual(after["user2"][0], before[0])

    def test_seeded_accounts_authenticate_with_requested_passwords(self):
        self.seed()
        before = self.accounts()
        with Session(self.engine) as db:
            for username in ("user1", "user2"):
                with self.subTest(username=username):
                    admin = admin_service.authenticate_admin(db, username, username)
                    self.assertIsNotNone(admin)
                    self.assertTrue(admin.is_active)
                    self.assertEqual(admin.id, before[username][0])
                    self.assertIsNone(admin_service.authenticate_admin(db, username, "wrong-test-password"))
        self.assertTrue(self.accounts() == before, "A current PBKDF2 demo hash changed on login")

    def test_startup_ignores_legacy_demo_flag_and_creates_only_initial_admin(self):
        self.startup()
        first = self.accounts()
        self.assertEqual(set(first), {"test-initial-admin"})
        self.startup()
        self.assertTrue(self.accounts() == first, "Repeated startup changed account identity or credentials")

    def test_startup_with_seed_disabled_only_creates_initial_admin(self):
        self.settings.seed_demo_accounts = False
        self.startup()
        self.assertEqual(set(self.accounts()), {"test-initial-admin"})

    def test_default_startup_has_only_admin_and_admin_password(self):
        initial = Settings(_env_file=None)
        with patch.object(db_initialization, "admin_engine", self.engine), \
             patch.object(db_initialization, "user_engine", self.engine), \
             patch.object(db_initialization, "AdminSessionLocal", sessionmaker(bind=self.engine)), \
             patch.object(admin_service, "settings", initial):
            db_initialization.init_db()
        self.assertEqual(set(self.accounts()), {"admin"})
        with Session(self.engine) as db:
            self.assertIsNotNone(admin_service.authenticate_admin(db, "admin", "admin"))

    def test_startup_preserves_existing_accounts_without_recreating_missing_demo_user(self):
        with Session(self.engine) as db:
            db.add(Admin(username="user1", password_hash=hash_admin_password("existing-only-password"),
                         full_name="Existing user", is_active=False))
            db.commit()
        before = self.accounts()["user1"]
        self.startup()
        after = self.accounts()
        self.assertEqual(set(after), {"user1", "test-initial-admin"})
        self.assertEqual(after["user1"], before)


if __name__ == "__main__":
    unittest.main()
