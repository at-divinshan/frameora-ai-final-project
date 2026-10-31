"""Disposable SQLite and real test-signed JWTs; no live MySQL connections.
SQLite does not prove MySQL row-lock/concurrency behavior.
"""
from datetime import datetime
from unittest.mock import MagicMock, patch
import unittest
from sqlalchemy import event, func, select
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
import test_privacy
from app.models.profile import UserProfile
from app.models.user import User
from app.repositories.profile_repository import find_owner_profile
from app.services import onboarding_service


class OnboardingTests(unittest.TestCase):
    auth = test_privacy.PrivacyTests.auth

    def setUp(self):
        test_privacy.PrivacyTests.setUp(self)
        UserProfile.__table__.create(self.engine)
        with Session(self.engine) as db:
            db.add(User(id=4, name="Other Owner", email="other@example.invalid", role="owner", password_hash="fixture"))
            db.commit()
        self.headers = self.auth(2)
        self.body = {"studio_name": " Studio Name ", "studio_phone": "+94 (77) 123-4567",
                     "studio_address": " 12 Test Street ", "studio_city": " Jaffna "}

    def tearDown(self):
        test_privacy.PrivacyTests.tearDown(self)

    def put(self, body=None, headers=None, path="/owner/studio"):
        return self.client.put(path, headers=self.headers if headers is None else headers,
                               json=self.body if body is None else body)

    def test_get_missing_is_read_only(self):
        statements = []
        def capture(conn, cursor, statement, parameters, context, many):
            statements.append(statement)
        event.listen(self.engine, "before_cursor_execute", capture)
        try:
            r = self.client.get("/owner/onboarding", headers=self.headers)
        finally:
            event.remove(self.engine, "before_cursor_execute", capture)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"onboarding_status": "pending_studio", "onboarding_completed_at": None,
                                   "next_step": "studio_setup", "studio": None})
        self.assertEqual(r.headers["cache-control"], "no-store")
        self.assertFalse(any(s.lstrip().split()[0].upper() in ("INSERT", "UPDATE", "DELETE") for s in statements))
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(UserProfile)), 0)

    def test_create_repeat_update_both_auth_methods(self):
        for uid in (2, 4):
            for _ in range(2):
                r = self.put(headers=self.auth(uid))
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.json()["onboarding_status"], "pending_plan")
                self.assertEqual(r.json()["next_step"], "subscription_selection")
                self.assertEqual(r.json()["studio"]["studio_name"], "Studio Name")
                self.assertIsNone(r.json()["onboarding_completed_at"])
            self.assertEqual(self.client.get("/owner/onboarding", headers=self.auth(uid)).json(), r.json())
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(UserProfile)), 2)
            self.assertEqual(db.get(User, 2).role, "owner")
            self.assertIsNone(db.get(User, 2).password_hash)
            self.assertEqual(db.get(User, 2).google_sub, b"test-subject")

    def test_completed_and_other_account_preserved(self):
        completed = datetime(2026, 1, 15, 12)
        with Session(self.engine) as db:
            db.add(UserProfile(user_id=2, onboarding_status="completed", onboarding_completed_at=completed))
            db.add(UserProfile(user_id=4, studio_name="Untouched", onboarding_status="pending_studio"))
            db.commit()
        r = self.put({**self.body, "studio_description": "A studio\nSecond line"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["onboarding_status"], "completed")
        self.assertEqual(r.json()["next_step"], "dashboard")
        with Session(self.engine) as db:
            self.assertEqual(find_owner_profile(db, 2).onboarding_completed_at, completed)
            self.assertEqual(find_owner_profile(db, 4).studio_name, "Untouched")

    def test_roles_and_real_jwt_validation(self):
        for headers, status in (({}, 401), ({"Authorization": "Bearer invalid"}, 401),
                                (self.auth(1), 403), (self.auth(3), 403)):
            self.assertEqual(self.client.get("/owner/onboarding", headers=headers).status_code, status)
            self.assertEqual(self.put(headers=headers).status_code, status)

    def test_required_fields_types_lengths_and_phone(self):
        for field in self.body:
            for value in (None, "", " ", 123, True, [], "a\x00b"):
                with self.subTest(field=field, value_type=type(value).__name__):
                    self.assertEqual(self.put({**self.body, field: value}).status_code, 422)
            self.assertEqual(self.put({k: v for k, v in self.body.items() if k != field}).status_code, 422)
        for field, length in (("studio_name", 151), ("studio_address", 256), ("studio_city", 101), ("studio_description", 2001)):
            self.assertEqual(self.put({**self.body, field: "a" * length}).status_code, 422)
        for phone in ("123", "１２３４５６７８", "1234567890123456", "123abc4567", "++94123456789"):
            self.assertEqual(self.put({**self.body, "studio_phone": phone}).status_code, 422)

    def test_protected_fields_and_cross_account_attempts(self):
        for key in ("role", "user_id", "id", "onboarding_status", "onboarding_completed_at", "credits",
                    "subscription", "plan_id", "email", "google_sub", "unknown"):
            self.assertEqual(self.put({**self.body, key: "blocked"}).status_code, 422)
        self.assertEqual(self.put(path="/owner/studio?user_id=4").status_code, 422)
        self.assertEqual(self.client.get("/owner/onboarding?user_id=4", headers=self.headers).status_code, 422)
        self.assertEqual(self.put(path="/owner/4/studio").status_code, 404)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(UserProfile)), 0)

    def test_description_clear(self):
        self.assertEqual(self.put({**self.body, "studio_description": "Description"}).status_code, 200)
        r = self.put({**self.body, "studio_description": "  "})
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()["studio"]["studio_description"])

    def test_failures_rollback_and_hide_details(self):
        for failure, expected in ((SQLAlchemyError("private details"), 503),
                                  (IntegrityError("private query", {}, Exception("private details")), 409)):
            with patch.object(Session, "commit", side_effect=failure):
                r = self.put()
            self.assertEqual(r.status_code, expected)
            self.assertNotIn("private", r.text)
            with Session(self.engine) as db:
                self.assertEqual(db.scalar(select(func.count()).select_from(UserProfile)), 0)

    def test_unknown_state_fails_closed(self):
        with Session(self.engine) as db:
            db.add(UserProfile(user_id=2, onboarding_status="unknown", studio_name="Unchanged"))
            db.commit()
        self.assertEqual(self.put().status_code, 503)
        self.assertEqual(self.client.get("/owner/onboarding", headers=self.headers).status_code, 503)
        with Session(self.engine) as db:
            self.assertEqual(find_owner_profile(db, 2).studio_name, "Unchanged")

    def test_mysql_current_read_and_lock_order(self):
        db = MagicMock()
        find_owner_profile(db, 2, lock=True)
        query = db.scalar.call_args.args[0]
        self.assertIn("FOR UPDATE", str(query.compile(dialect=mysql.dialect())))
        self.assertTrue(query.get_execution_options()["populate_existing"])
        calls = []
        original_lock = onboarding_service.lock_profile
        original_find = onboarding_service.find_owner_profile
        def locked(*args, **kwargs):
            calls.append("parent")
            return original_lock(*args, **kwargs)
        def found(*args, **kwargs):
            calls.append("profile")
            self.assertTrue(kwargs["lock"])
            return original_find(*args, **kwargs)
        with patch.object(onboarding_service, "lock_profile", side_effect=locked), patch.object(onboarding_service, "find_owner_profile", side_effect=found):
            self.assertEqual(self.put().status_code, 200)
        self.assertEqual(calls, ["parent", "profile"])

    def test_role_rechecked_after_parent_lock(self):
        with patch.object(onboarding_service, "lock_profile", return_value=User(id=2, role="user")):
            self.assertEqual(self.put().status_code, 403)

    def test_public_personal_auth_and_cors_regressions(self):
        self.assertEqual(self.put().status_code, 200)
        for path in ("/auth/me", "/users/me"):
            response = self.client.get(path, headers=self.headers)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("studio_name", response.text)
        self.client.patch("/users/me/privacy", headers=self.headers, json={"profile_visibility": "public"})
        self.assertEqual(set(self.client.get("/users/2/public-profile").json()), {"name", "profile_image"})
        from app.core.config import settings
        response = self.client.options("/owner/studio", headers={"Origin": settings.cors_origins[0],
            "Access-Control-Request-Method": "PUT", "Access-Control-Request-Headers": "Authorization,Content-Type"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("PUT", response.headers["access-control-allow-methods"])

    def test_concurrent_requests_with_sqlite_serialization(self):
        # SQLite BEGIN IMMEDIATE emulates serialization for this API convergence
        # test; it does NOT establish InnoDB SELECT FOR UPDATE behavior.
        from concurrent.futures import ThreadPoolExecutor
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from sqlalchemy import create_engine
        from app.database.connection import get_db
        from app.main import app
        with TemporaryDirectory(prefix="frameora-onboarding-") as folder:
            engine = create_engine("sqlite:///" + str(Path(folder) / "isolated.sqlite"),
                                   connect_args={"check_same_thread": False, "timeout": 10})
            @event.listens_for(engine, "connect")
            def connect(connection, record):
                connection.isolation_level = None
            @event.listens_for(engine, "begin")
            def begin(connection):
                connection.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                User.__table__.create(engine)
                UserProfile.__table__.create(engine)
                with Session(engine) as db:
                    db.add(User(id=2, name="Disposable", email="concurrent@example.invalid", role="owner"))
                    db.commit()
                def isolated_db():
                    with Session(engine, expire_on_commit=False) as db:
                        yield db
                app.dependency_overrides[get_db] = isolated_db
                with ThreadPoolExecutor(max_workers=4) as pool:
                    results = list(pool.map(lambda _: self.put().status_code, range(4)))
                self.assertEqual(results, [200] * 4)
                with Session(engine) as db:
                    self.assertEqual(db.scalar(select(func.count()).select_from(UserProfile)), 1)
                    self.assertEqual(find_owner_profile(db, 2).onboarding_status, "pending_plan")
            finally:
                engine.dispose()
