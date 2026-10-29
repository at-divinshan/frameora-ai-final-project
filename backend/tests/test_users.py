"""Isolated profile API tests: SQLite only; production connections are forbidden."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.mysql import VARBINARY
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.connection import engine as production_engine, get_db
from app.main import app
from app.models.user import User


@compiles(VARBINARY, "sqlite")
def sqlite_binary(type_, compiler, **kwargs):
    return "BLOB"


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.guard = patch.object(production_engine, "connect", side_effect=AssertionError("Live database forbidden"))
        self.guard.start()
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        User.__table__.create(self.engine)
        with Session(self.engine) as db:
            for uid, role in enumerate(("user", "owner", "admin"), 1):
                db.add(User(id=uid, name="Original Name", email=f"role{uid}@example.invalid",
                            role=role, password_hash="test-only-not-a-real-hash" if uid != 2 else None,
                            google_sub=b"test-subject" if uid == 2 else None))
            db.commit()

        def isolated_db():
            with Session(self.engine, expire_on_commit=False) as db:
                yield db

        app.dependency_overrides[get_db] = isolated_db
        self.client = TestClient(app)
        # Exercise real bearer parsing, account lookup and Admin checks without generating JWTs.
        self.decoder = patch("app.core.dependencies.decode_access_token", return_value="1")
        self.decode = self.decoder.start()
        self.headers = {"Authorization": "Bearer test-only-placeholder"}

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.decoder.stop()
        self.engine.dispose()
        self.guard.stop()

    def test_all_roles_read_and_update_self_without_secrets(self):
        for uid in (1, 2, 3):
            with self.subTest(uid=uid):
                self.decode.return_value = str(uid)
                response = self.client.get("/users/me", headers=self.headers)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["cache-control"], "no-store")
                body = response.json()
                self.assertEqual(body["id"], str(uid))
                self.assertEqual(set(body), {"id", "name", "phone", "email", "role", "is_verified",
                                             "created_at", "profile_image", "has_password", "google_linked"})
                self.assertEqual(body["has_password"], uid != 2)
                self.assertEqual(body["google_linked"], uid == 2)
                response = self.client.patch("/users/me", headers=self.headers,
                                             json={"name": "  Updated Name  ", "phone": "+94 77 123 4567"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["name"], "Updated Name")
                with Session(self.engine) as db:
                    user = db.get(User, uid)
                    self.assertEqual(user.phone, "+94 77 123 4567")
                    self.assertEqual(user.email, body["email"])
                    self.assertEqual(user.role, body["role"])

    def test_missing_auth_and_missing_account(self):
        for method in ("get", "patch"):
            args = {"json": {"name": "New Name"}} if method == "patch" else {}
            self.assertEqual(getattr(self.client, method)("/users/me", **args).status_code, 401)
        self.decode.return_value = "999"
        self.assertEqual(self.client.get("/users/me", headers=self.headers).status_code, 401)

    def test_protected_and_unknown_fields_rejected(self):
        for field in ("id", "user_id", "email", "role", "is_verified", "google_sub", "password_hash",
                      "profile_image", "created_at", "has_password", "google_linked", "privacy_preferences", "unknown"):
            with self.subTest(field=field):
                response = self.client.patch("/users/me", headers=self.headers,
                                             json={"name": "Changed", field: "private-input-marker"})
                self.assertEqual(response.status_code, 422)
                self.assertNotIn("private-input-marker", response.text)
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, 1).name, "Original Name")

    def test_input_validation(self):
        for payload in ({}, {"name": None}, {"name": " "}, {"name": "x"}, {"name": "x" * 101},
                        {"name": 123}, {"name": "A\nB"}, {"phone": 1234567}, {"phone": "bad-number"},
                        {"phone": "123"}, {"phone": "1" * 16}, {"phone": " " * 21}):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.patch("/users/me", headers=self.headers, json=payload).status_code, 422)

    def test_partial_update_clear_phone_and_no_cross_account_target(self):
        response = self.client.patch("/users/me?user_id=2&role=admin", headers=self.headers,
                                     json={"phone": "1234567"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "1")
        with Session(self.engine) as db:
            self.assertIsNone(db.get(User, 2).phone)
            self.assertEqual(db.get(User, 1).name, "Original Name")
        for value in (None, ""):
            response = self.client.patch("/users/me", headers=self.headers, json={"phone": value})
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.json()["phone"])

    def test_database_failure_is_sanitized_and_rolled_back(self):
        from sqlalchemy.exc import SQLAlchemyError
        with patch.object(Session, "commit", side_effect=SQLAlchemyError("private database details")):
            response = self.client.patch("/users/me", headers=self.headers, json={"name": "Changed"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private database details", response.text)
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, 1).name, "Original Name")

    def test_authentication_rejection_and_single_admin_policy(self):
        from fastapi import HTTPException
        self.decode.side_effect = HTTPException(status_code=401, detail="Invalid session")
        self.assertEqual(self.client.patch("/users/me", headers=self.headers,
                                          json={"name": "Changed"}).status_code, 401)
        self.decode.side_effect = None
        self.decode.return_value = "3"
        with Session(self.engine) as db:
            db.add(User(name="Second Admin", email="second@example.invalid", role="admin"))
            db.commit()
        self.assertEqual(self.client.get("/users/me", headers=self.headers).status_code, 403)

    def test_patch_cors_preflight(self):
        response = self.client.options("/users/me", headers={"Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PATCH", "Access-Control-Request-Headers": "authorization,content-type"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("PATCH", response.headers["access-control-allow-methods"])
