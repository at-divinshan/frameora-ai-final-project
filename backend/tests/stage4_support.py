"""Isolated Stage 4 fixtures: private Redis socket, disposable SQLite, ephemeral keys.

Never connect to the configured MySQL or Redis services. No live Google requests.
"""

from dataclasses import replace
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.orm import Session

import test_users  # SQLite compiler for the existing MySQL VARBINARY mapping.
from app.main import app
from app.database.connection import engine as production_engine, get_db
from app.core import security, google_oidc
from app.models.user import User
from app.routers import google_auth
from app.services import oauth_transaction_store, rate_limit_service, google_auth_service


class IsolatedStage4(unittest.TestCase):
    migrated = True
    enabled = True

    @classmethod
    def setUpClass(cls):
        if not shutil.which("redis-server"):
            raise unittest.SkipTest("redis-server unavailable; no external Redis fallback")
        cls.redis_dir = tempfile.TemporaryDirectory(prefix="frameora-test-redis-")
        socket = str(Path(cls.redis_dir.name) / "redis.sock")
        cls.process = subprocess.Popen([
            "redis-server", "--port", "0", "--unixsocket", socket,
            "--unixsocketperm", "700", "--save", "", "--appendonly", "no",
            "--dir", cls.redis_dir.name,
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.redis = Redis(unix_socket_path=socket, decode_responses=True, socket_timeout=2)
        for _ in range(100):
            try:
                cls.redis.ping()
                return
            except Exception:
                time.sleep(0.02)
        cls.tearDownClass()
        raise RuntimeError("Isolated Redis failed to start")

    @classmethod
    def tearDownClass(cls):
        cls.redis.close()
        cls.process.terminate()
        cls.process.wait(timeout=5)
        cls.redis_dir.cleanup()

    def setUp(self):
        self.redis.flushdb()  # Only the process started above, private socket, no persistence.
        self.guard = patch.object(production_engine, "connect", side_effect=AssertionError("Live database forbidden"))
        self.guard.start()
        self.addCleanup(self.guard.stop)
        self.folder = tempfile.TemporaryDirectory(prefix="frameora-test-db-")
        self.addCleanup(self.folder.cleanup)
        self.engine = create_engine("sqlite:///" + str(Path(self.folder.name) / "test.sqlite"),
                                    connect_args={"check_same_thread": False, "timeout": 10})
        self.addCleanup(self.engine.dispose)
        if self.migrated:
            User.__table__.create(self.engine)
        else:
            # Actually absent column, not a mocked version read.
            metadata = MetaData()
            Table("User", metadata, *(c._copy() for c in User.__table__.c if c.name != "auth_version")).create(self.engine)
        self.settings = replace(security.settings, auth_version_enabled=self.enabled, password_management_enabled=self.enabled,
            jwt_secret_key=secrets.token_urlsafe(48), google_auth_enabled=True,
            google_client_id="isolated-client", google_client_secret=secrets.token_urlsafe(20),
            google_redirect_uri="http://localhost/auth/google/callback", frontend_origin="http://localhost:5173",
            google_completion_url="http://localhost:5173/auth/google/callback", oauth_cookie_secure=False,
            redis_url="redis://localhost:1", oauth_transaction_key=Fernet.generate_key().decode())
        for module in (security, google_oidc, google_auth):
            patcher = patch.object(module, "settings", self.settings)
            patcher.start(); self.addCleanup(patcher.stop)
        self.store = oauth_transaction_store.TransactionStore.__new__(oauth_transaction_store.TransactionStore)
        self.store.client = self.redis
        self.store.cipher = Fernet(self.settings.oauth_transaction_key.encode())
        for module in (google_auth, google_auth_service):
            patcher = patch.object(module, "get_store", return_value=self.store)
            patcher.start(); self.addCleanup(patcher.stop)
        self.rate_patch = patch.object(rate_limit_service, "client", return_value=self.redis)
        self.rate_patch.start(); self.addCleanup(self.rate_patch.stop)
        self.old_password = "Original-Test-Password"
        self.new_password = "Replacement-Test-Password"
        self.hash = security.hash_password(self.old_password)
        with Session(self.engine) as db:
            for uid, role in enumerate(("user", "owner", "admin", "user", "owner"), 1):
                db.add(User(id=uid, name="Disposable Account", email=f"account{uid}@example.com", role=role,
                    password_hash=self.hash if uid <= 3 else None,
                    google_sub=f"google-{uid}".encode() if uid > 3 else None))
            db.commit()
        def test_db():
            with Session(self.engine, expire_on_commit=False) as db:
                yield db
        app.dependency_overrides[get_db] = test_db
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def headers(self, uid=1, version=0, remember=False):
        token, _ = security.create_access_token(str(uid), remember, version)
        return {"Authorization": "Bearer " + token}

    def password_body(self, **overrides):
        return {"current_password": self.old_password, "new_password": self.new_password,
                "confirm_password": self.new_password, **overrides}

    def change(self, uid=1, headers=None, **overrides):
        return self.client.post("/auth/password/change", headers=headers or self.headers(uid), json=self.password_body(**overrides))
