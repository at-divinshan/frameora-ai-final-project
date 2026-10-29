"""Password management tests with real Argon2/JWTs and isolated Redis/SQLite."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
import time

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import stage4_support
from app.core import security
from app.models.user import User
from app.schemas.user import ProfileUpdate
from app.services import password_service, rate_limit_service, user_service


class PasswordTests(stage4_support.IsolatedStage4):
    def test_all_password_roles_change_and_revoke_all_sessions(self):
        for uid in (1, 2, 3):
            old = self.headers(uid)
            remembered = self.headers(uid, remember=True)
            r = self.change(uid)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json(), {"status": "password_updated", "reauthentication_required": True})
            for headers in (old, remembered):
                self.assertEqual(self.client.get("/auth/me", headers=headers).status_code, 401)
                self.assertEqual(self.client.patch("/users/me", headers=headers, json={"name": "Blocked"}).status_code, 401)
            with Session(self.engine) as db:
                user = db.get(User, uid)
                self.assertTrue(security.verify_password(self.new_password, user.password_hash))
                self.assertEqual(db.scalar(select(User.auth_version).where(User.id == uid)), 1)
                self.assertEqual(user.email, f"account{uid}@example.com")
            self.assertEqual(self.client.post("/auth/login", json={"email": f"account{uid}@example.com", "password": self.old_password}).status_code, 401)
            r = self.client.post("/auth/login", json={"email": f"account{uid}@example.com", "password": self.new_password})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(security.decode_access_claims(r.json()["access_token"])["auth_version"], 1)

    def test_bad_password_policy_and_unknown_fields_no_writes(self):
        self.assertEqual(self.client.post("/auth/password/change", json=self.password_body()).status_code, 401)
        for kwargs in ({"new_password": "short", "confirm_password": "short"},
                       {"new_password": "lowercaseonly", "confirm_password": "lowercaseonly"},
                       {"confirm_password": "Mismatch-Value"}, {"role": "admin"}, {"user_id": 2},
                       {"auth_version": 1}, {"new_password": "x" * 129}):
            self.assertEqual(self.change(**kwargs).status_code, 422)
        self.assertEqual(self.change(current_password="Wrong-password").status_code, 400)
        self.assertEqual(self.change(4).status_code, 400)
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, 1).password_hash, self.hash)
            self.assertIsNone(db.get(User, 4).password_hash)

    def test_rate_limit_before_hashing_and_redis_failure_closed(self):
        for _ in range(5):
            self.assertEqual(self.change(current_password="Wrong-password").status_code, 400)
        with patch.object(password_service, "verify_password", side_effect=AssertionError("must rate-limit first")):
            r = self.change()
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.headers["retry-after"], "300")
        self.assertTrue(all(0 < self.redis.ttl(k) <= 300 for k in self.redis.keys("frameora:password-rate:*")))
        with patch.object(rate_limit_service, "client", side_effect=ConnectionError("private details")):
            r = self.change(2)
        self.assertEqual(r.status_code, 503)
        self.assertNotIn("private details", r.text)
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, 2).password_hash, self.hash)

    def test_commit_failure_rolls_back_hash_and_version(self):
        with patch.object(Session, "commit", side_effect=SQLAlchemyError("private details")):
            r = self.change()
        self.assertEqual(r.status_code, 503)
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, 1).password_hash, self.hash)
            self.assertEqual(db.scalar(select(User.auth_version).where(User.id == 1)), 0)
        self.assertEqual(self.client.get("/auth/me", headers=self.headers()).status_code, 200)

    def test_concurrent_compare_and_swap_allows_one_writer(self):
        barrier = Barrier(2)
        def attempt(number):
            with Session(self.engine) as db:
                # Both requests have the same already-verified version/hash snapshot.
                user = User(id=1, password_hash=self.hash)
                barrier.wait(timeout=5)
                try:
                    password_service.write_password(db, user, 0, "isolated-hash-" + str(number))
                    return 200
                except HTTPException as error:
                    db.rollback()
                    return error.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, (1, 2)))
        self.assertEqual(sorted(results), [200, 401])
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(User.auth_version).where(User.id == 1)), 1)

    def test_stale_inflight_profile_mutation_rejected(self):
        with Session(self.engine, expire_on_commit=False) as stale:
            user = stale.get(User, 1)
            user._authenticated_version = 0
            stale.commit()
            self.assertEqual(self.change().status_code, 200)
            with self.assertRaises(HTTPException) as caught:
                user_service.update_profile(stale, user, ProfileUpdate(name="Stale update"))
            self.assertEqual(caught.exception.status_code, 401)
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, 1).name, "Disposable Account")

    def test_ip_limit_spans_accounts_and_actions(self):
        for uid in range(30):
            rate_limit_service.limit_password_attempt("setup-start", 1000 + uid, "isolated-peer")
        with self.assertRaises(HTTPException) as caught:
            rate_limit_service.limit_password_attempt("change", 2000, "isolated-peer")
        self.assertEqual(caught.exception.status_code, 429)
