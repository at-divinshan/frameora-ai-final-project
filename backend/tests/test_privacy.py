"""Disposable SQLite privacy integration tests, with real test-signed JWTs."""

from dataclasses import replace
import secrets
import unittest
from unittest.mock import patch

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

import test_users
from app.core import security
from app.models.user import User


class PrivacyTests(unittest.TestCase):
    def setUp(self):
        test_users.ProfileTests.setUp(self)
        self.decoder.stop()
        self.key = patch.object(security, "settings", replace(security.settings, jwt_secret_key=secrets.token_urlsafe(48)))
        self.key.start()
        self.headers = self.auth(1)

    def tearDown(self):
        self.key.stop()
        test_users.ProfileTests.tearDown(self)

    def auth(self, uid):
        token, _ = security.create_access_token(str(uid), False)
        return {"Authorization": "Bearer " + token}

    def store(self, uid, value):
        with Session(self.engine) as db:
            db.get(User, uid).privacy_preferences = value
            db.commit()

    def test_defaults_and_malformed_storage_fail_closed(self):
        defaults = {"profile_visibility": "private", "photography_plans_default": "private", "ai_images_default": "private"}
        for stored in (None, {}, [], "public", {"profile_visibility": None}, {"profile_visibility": True}, {"profile_visibility": "PUBLIC"}):
            self.store(1, stored)
            r = self.client.get("/users/me/privacy", headers=self.headers)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json(), defaults)
            self.assertEqual(r.headers["cache-control"], "no-store")
            self.assertEqual(self.client.get("/users/1/public-profile").status_code, 404)
            with Session(self.engine) as db:
                self.assertEqual(db.get(User, 1).privacy_preferences, stored)

    def test_visibility_and_restricted_response_for_user_and_owner(self):
        for uid in (1, 2):
            headers = self.auth(uid)
            r = self.client.patch("/users/me/privacy", headers=headers, json={"profile_visibility": "public"})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["ai_images_default"], "private")
            r = self.client.get(f"/users/{uid}/public-profile")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json(), {"name": "Original Name", "profile_image": None})
            self.assertEqual(r.headers["cache-control"], "no-store")
            with Session(self.engine) as db:
                self.assertEqual(db.get(User, uid).privacy_preferences["profile_visibility"], "public")
            r = self.client.patch("/users/me/privacy", headers=headers, json={"profile_visibility": "private"})
            self.assertEqual(r.status_code, 200)
            private = self.client.get(f"/users/{uid}/public-profile")
            missing = self.client.get("/users/999/public-profile")
            self.assertEqual(private.status_code, 404)
            self.assertEqual(private.json(), missing.json())
            self.assertEqual(private.headers["cache-control"], "no-store")

    def test_admin_cannot_be_public_even_with_legacy_public_value(self):
        self.store(3, {"profile_visibility": "public"})
        headers = self.auth(3)
        self.assertEqual(self.client.get("/users/me/privacy", headers=headers).json()["profile_visibility"], "private")
        self.assertEqual(self.client.get("/users/3/public-profile").status_code, 404)
        self.assertEqual(self.client.patch("/users/me/privacy", headers=headers, json={"profile_visibility": "public"}).status_code, 403)
        self.assertEqual(self.client.patch("/users/me/privacy", headers=headers, json={"profile_visibility": "private"}).status_code, 200)

    def test_strict_validation_and_protected_fields(self):
        for body in ({}, {"profile_visibility": None}, {"profile_visibility": True}, {"profile_visibility": "PUBLIC"},
                     {"photography_plans_default": 1}, {"ai_images_default": []}, {"privacy_preferences": {}},
                     *({key: "blocked"} for key in ("role", "email", "is_verified", "google_sub", "password_hash", "name", "id", "unknown"))):
            r = self.client.patch("/users/me/privacy", headers=self.headers, json=body)
            self.assertEqual(r.status_code, 422)
        with Session(self.engine) as db:
            self.assertIsNone(db.get(User, 1).privacy_preferences)

    def test_authentication_and_cross_account_protection(self):
        for headers in ({}, {"Authorization": "Bearer invalid"}):
            self.assertEqual(self.client.get("/users/me/privacy", headers=headers).status_code, 401)
            self.assertEqual(self.client.patch("/users/me/privacy", headers=headers, json={"profile_visibility": "public"}).status_code, 401)
        r = self.client.patch("/users/me/privacy?user_id=2&role=admin", headers=self.headers, json={"profile_visibility": "public"})
        self.assertEqual(r.status_code, 200)
        with Session(self.engine) as db:
            self.assertIsNone(db.get(User, 2).privacy_preferences)
        self.assertEqual(self.client.patch("/users/me/privacy", headers=self.headers, json={"user_id": 2, "profile_visibility": "public"}).status_code, 422)

    def test_partial_updates_preserve_other_defaults_and_profile(self):
        self.store(1, {"profile_visibility": "public", "photography_plans_default": "private", "ai_images_default": "private"})
        r = self.client.patch("/users/me/privacy", headers=self.headers, json={"ai_images_default": "public"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"profile_visibility": "public", "photography_plans_default": "private", "ai_images_default": "public"})
        self.assertEqual(self.client.get("/auth/me", headers=self.headers).status_code, 200)
        r = self.client.patch("/users/me", headers=self.headers, json={"name": "Updated Name"})
        self.assertEqual(r.status_code, 200)
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, 1).privacy_preferences["ai_images_default"], "public")
            self.assertEqual(db.get(User, 1).name, "Updated Name")

    def test_failure_rolls_back_privacy(self):
        with patch.object(Session, "commit", side_effect=SQLAlchemyError("private details")):
            r = self.client.patch("/users/me/privacy", headers=self.headers, json={"profile_visibility": "public"})
        self.assertEqual(r.status_code, 503)
        self.assertNotIn("private details", r.text)
        with Session(self.engine) as db:
            self.assertIsNone(db.get(User, 1).privacy_preferences)
