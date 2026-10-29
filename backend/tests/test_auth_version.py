"""Migration gate, real JWT compatibility and isolated Admin reset tests."""

from dataclasses import replace
from unittest.mock import patch
import jwt
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from urllib.parse import parse_qs, urlsplit

import stage4_support
from app.core import security
from app.models.user import User
from reset_admin_password import reset_locked_admin, ADMIN_NAME, ADMIN_EMAIL, ResetAborted
from app.services import google_auth_service
from app.core.google_oidc import digest
import time


class LegacyGateTests(stage4_support.IsolatedStage4):
    migrated = False
    enabled = False

    def test_unmigrated_database_never_reads_or_writes_new_column(self):
        statements = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)
        event.listen(self.engine, "before_cursor_execute", capture)
        try:
            for uid in (1, 2, 3):
                login = self.client.post("/auth/login", json={"email": f"account{uid}@example.com", "password": self.old_password})
                self.assertEqual(login.status_code, 200)
                token = login.json()["access_token"]
                self.assertNotIn("auth_version", security.decode_access_claims(token))
                headers = {"Authorization": "Bearer " + token}
                for path in ("/auth/me", "/users/me", "/users/me/privacy"):
                    self.assertEqual(self.client.get(path, headers=headers).status_code, 200)
                self.assertEqual(self.client.patch("/users/me", headers=headers, json={"name": "Updated Name"}).status_code, 200)
            registration = self.client.post("/auth/register", json={"name": "New Account", "email": "new@example.com",
                "password": self.old_password, "confirm_password": self.old_password, "role": "user", "accept_terms": True})
            self.assertEqual(registration.status_code, 201)
            self.assertEqual(self.change().status_code, 503)
            self.assertEqual(self.client.post("/auth/google/password-setup/start", headers={**self.headers(4), "Origin": self.settings.frontend_origin}, json={"consent": True}).status_code, 503)
            self.assertFalse(any("auth_version" in sql for sql in statements))
        finally:
            event.remove(self.engine, "before_cursor_execute", capture)

    def test_enabled_without_migration_fails_closed(self):
        with patch.object(security, "settings", replace(self.settings, auth_version_enabled=True)):
            self.assertEqual(self.client.get("/auth/me", headers=self.headers()).status_code, 503)
            self.assertEqual(self.client.post("/auth/login", json={"email": "account1@example.com", "password": self.old_password}).status_code, 503)

    def test_legacy_google_login_registration_and_pending_link(self):
        browser = "test-browser"
        with Session(self.engine) as db:
            state = parse_qs(urlsplit(google_auth_service.begin(browser, False)).query)["state"][0]
            with patch.object(google_auth_service, "exchange_identity", return_value={"sub": "google-4", "email": "account4@example.com"}):
                handle, _ = google_auth_service.callback(db, state, "test-code", None, browser)
            result, _ = google_auth_service.complete(db, handle, browser)
            self.assertNotIn("auth_version", security.decode_access_claims(result.access_token))
            # A pre-deployment linking transaction does not have auth_version.
            handle = self.store.put("authorization", browser, {"action": "link", "remember": False,
                "nonce": "test-nonce", "verifier": "test-verifier", "user_id": 1,
                "password_digest": digest(self.hash), "session_digest": digest("test-session"),
                "reauthenticated_at": time.time()}, 300)
            with patch.object(google_auth_service, "exchange_identity", return_value={"sub": "new-link", "email": "account1@example.com"}):
                proof, part = google_auth_service.callback(db, handle, "test-code", None, browser)
            self.assertEqual(part, "link")
            self.assertEqual(google_auth_service.link(db, proof, browser, db.get(User, 1), "test-session"), {"status": "linked"})
            state = parse_qs(urlsplit(google_auth_service.begin(browser, False)).query)["state"][0]
            with patch.object(google_auth_service, "exchange_identity", return_value={"sub": "new-google", "email": "newgoogle@example.com"}):
                handle, _ = google_auth_service.callback(db, state, "test-code", None, browser)
            from app.schemas.google_auth import GoogleRegistration
            result, registration = google_auth_service.complete(db, handle, browser)
            self.assertEqual(result["status"], "registration_required")
            result = google_auth_service.register(db, registration, browser, GoogleRegistration(name="New Owner", role="owner", accept_terms=True))
            self.assertEqual(result.user.role, "owner")

    def test_legacy_admin_reset_uses_only_existing_columns(self):
        with Session(self.engine) as db:
            user = db.get(User, 3); user.name = ADMIN_NAME; user.email = ADMIN_EMAIL; db.commit()
        with self.engine.begin() as connection:
            reset_locked_admin(connection, security.hash_password(self.new_password))
        with Session(self.engine) as db:
            self.assertTrue(security.verify_password(self.new_password, db.get(User, 3).password_hash))


class AuthVersionTests(stage4_support.IsolatedStage4):
    def test_disable_password_endpoints_retains_revocation_checks(self):
        self.assertEqual(self.change().status_code, 200)
        with patch.object(security, "settings", replace(self.settings, password_management_enabled=False)):
            self.assertEqual(self.change(headers=self.headers(version=1)).status_code, 503)
            self.assertEqual(self.client.get("/auth/me", headers=self.headers(version=0)).status_code, 401)
            self.assertEqual(self.client.get("/auth/me", headers=self.headers(version=1)).status_code, 200)

    def test_legacy_missing_malformed_and_expired_claims_rejected(self):
        encoded = self.headers()["Authorization"].split()[1]
        base = security.decode_access_claims(encoded)
        for value in (None, True, -1, "0", 0.0, 2**64):
            claims = {**base, "auth_version": value}
            self.assertEqual(self.client.get("/auth/me", headers={"Authorization": "Bearer " + jwt.encode(claims, self.settings.jwt_secret_key, algorithm="HS256")}).status_code, 401)
        for claims in ({k:v for k,v in base.items() if k != "auth_version"}, {**base, "exp": 1}):
            token = jwt.encode(claims, self.settings.jwt_secret_key, algorithm="HS256")
            self.assertEqual(self.client.get("/auth/me", headers={"Authorization": "Bearer " + token}).status_code, 401)
        self.assertEqual(self.client.get("/auth/me", headers=self.headers(version=1)).status_code, 401)

    def test_login_versions_and_admin_reset_revocation(self):
        self.assertNotEqual(self.headers(), self.headers())
        for uid in (1, 2, 3):
            r = self.client.post("/auth/login", json={"email": f"account{uid}@example.com", "password": self.old_password, "remember_me": True})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(security.decode_access_claims(r.json()["access_token"])["auth_version"], 0)
        headers = self.headers(3)
        with Session(self.engine) as db:
            user = db.get(User, 3); user.name = ADMIN_NAME; user.email = ADMIN_EMAIL; db.commit()
        with self.engine.begin() as connection:
            reset_locked_admin(connection, security.hash_password(self.new_password))
        self.assertEqual(self.client.get("/auth/me", headers=headers).status_code, 401)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(User.auth_version).where(User.id == 3)), 1)
            self.assertEqual(db.get(User, 3).role, "admin")

    def test_admin_reset_rejects_multiple_admins_and_rolls_back(self):
        with Session(self.engine) as db:
            db.get(User, 2).role = "admin"; db.commit()
        with self.assertRaises(ResetAborted), self.engine.begin() as connection:
            reset_locked_admin(connection, "test-only-hash")
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, 3).password_hash, self.hash)
