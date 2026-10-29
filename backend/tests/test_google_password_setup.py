"""Google flow integration using real Redis transactions, simulated provider responses."""

import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

import stage4_support
from app.core import security
from app.core.google_oidc import digest
from app.models.user import User
from app.services import google_auth_service as service
from app.services.oauth_transaction_store import PREFIX


class GoogleSetupTests(stage4_support.IsolatedStage4):
    def start(self, uid=4):
        headers = {**self.headers(uid), "Origin": self.settings.frontend_origin}
        r = self.client.post("/auth/google/password-setup/start", headers=headers, json={"consent": True})
        self.assertEqual(r.status_code, 200)
        query = parse_qs(urlsplit(r.json()["authorization_url"]).query)
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["prompt"], ["select_account"])
        return query, headers

    def callback(self, query, subject="google-4"):
        with patch.object(service, "exchange_identity", return_value={"sub": subject, "email": "verified@example.com"}) as exchange:
            r = self.client.get("/auth/google/callback", params={"state": query["state"][0], "code": "isolated-code"}, follow_redirects=False)
        if exchange.called:
            _, verifier, nonce = exchange.call_args.args
            expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            self.assertEqual(query["code_challenge"], [expected])
            self.assertEqual(query["nonce"], [nonce])
        return r

    def complete(self, headers):
        return self.client.post("/auth/google/password-setup/complete", headers=headers,
            json={"new_password": self.new_password, "confirm_password": self.new_password})

    def test_user_owner_setup_and_revocation(self):
        for uid in (4, 5):
            query, headers = self.start(uid)
            r = self.callback(query, f"google-{uid}")
            self.assertEqual(r.status_code, 303)
            self.assertTrue(r.headers["location"].endswith("#google-password-setup"))
            self.assertEqual(self.complete(headers).status_code, 200)
            self.assertEqual(self.client.get("/auth/me", headers=headers).status_code, 401)
            with Session(self.engine) as db:
                user = db.get(User, uid)
                self.assertTrue(security.verify_password(self.new_password, user.password_hash))
                self.assertEqual(user.google_sub, f"google-{uid}".encode())
                self.assertEqual(db.scalar(select(User.auth_version).where(User.id == uid)), 1)
            self.assertEqual(self.client.post("/auth/login", json={"email": f"account{uid}@example.com", "password": self.new_password}).status_code, 200)
            # Existing Google login remains usable and issues the new version.
            browser = "returning-browser"
            with Session(self.engine) as db:
                state = parse_qs(urlsplit(service.begin(browser, False)).query)["state"][0]
                with patch.object(service, "exchange_identity", return_value={"sub": f"google-{uid}", "email": f"account{uid}@example.com"}):
                    proof, _ = service.callback(db, state, "isolated-code", None, browser)
                session, _ = service.complete(db, proof, browser)
                self.assertEqual(security.decode_access_claims(session.access_token)["auth_version"], 1)

    def test_admin_existing_password_consent_origin_and_missing_auth(self):
        path = "/auth/google/password-setup/start"
        for uid in (1, 2, 3):
            self.assertEqual(self.client.post(path, headers={**self.headers(uid), "Origin": self.settings.frontend_origin}, json={"consent": True}).status_code, 400)
        for consent in (False, "true", 1, None):
            self.assertEqual(self.client.post(path, headers={**self.headers(4), "Origin": self.settings.frontend_origin}, json={"consent": consent}).status_code, 422)
        self.assertEqual(self.client.post(path, headers={"Origin": self.settings.frontend_origin}, json={"consent": True}).status_code, 401)
        self.assertEqual(self.client.post(path, headers={**self.headers(4), "Origin": "https://wrong.example"}, json={"consent": True}).status_code, 403)

    def test_wrong_subject_and_cancellation_do_not_create_password(self):
        query, headers = self.start()
        r = self.callback(query, "wrong-subject")
        self.assertTrue(r.headers["location"].endswith("#google-error"))
        self.assertEqual(self.complete(headers).status_code, 400)
        query, _ = self.start()
        r = self.client.get("/auth/google/callback", params={"state": query["state"][0], "error": "access_denied"}, follow_redirects=False)
        self.assertTrue(r.headers["location"].endswith("#google-cancelled"))
        with Session(self.engine) as db:
            self.assertIsNone(db.get(User, 4).password_hash)

    def test_replay_browser_and_session_bindings(self):
        query, headers = self.start()
        state = query["state"][0]
        self.assertGreater(self.redis.ttl(PREFIX + digest(state)), 0)
        self.assertEqual(self.callback(query).status_code, 303)
        proof = self.client.cookies.get("frameora-google-password-setup")
        self.assertLessEqual(self.redis.ttl(PREFIX + digest(proof)), 60)
        # Different valid JWT for the same account (remembered session) cannot use proof.
        wrong = {**self.headers(4, remember=True), "Origin": self.settings.frontend_origin}
        self.assertEqual(self.complete(wrong).status_code, 400)
        self.assertEqual(self.complete(headers).status_code, 400)  # proof burned once
        self.assertTrue(self.callback(query).headers["location"].endswith("#google-error"))
        query, headers = self.start()
        self.client.cookies.clear()
        self.assertTrue(self.callback(query).headers["location"].endswith("#google-error"))

    def test_expiry_and_revocation_between_start_callback_and_complete(self):
        query, headers = self.start()
        self.redis.pexpire(PREFIX + digest(query["state"][0]), 0)
        self.assertTrue(self.callback(query).headers["location"].endswith("#google-error"))
        query, headers = self.start()
        self.callback(query)
        proof = self.client.cookies.get("frameora-google-password-setup")
        self.redis.pexpire(PREFIX + digest(proof), 0)
        self.assertEqual(self.complete(headers).status_code, 400)
        query, headers = self.start()
        self.callback(query)
        with Session(self.engine) as db:
            db.execute(update(User).where(User.id == 4).values(auth_version=1)); db.commit()
        self.assertEqual(self.complete(headers).status_code, 401)

    def test_transaction_wrong_purpose_and_atomic_single_use(self):
        handle = self.store.put("password-setup-completion", "browser", {"test": True}, 60)
        for purpose, browser in (("completion", "browser"), ("password-setup-completion", "wrong")):
            with self.assertRaises(HTTPException):
                self.store.consume(handle, browser, purpose)
        def consume(_):
            try:
                self.store.consume(handle, "browser", "password-setup-completion")
                return 200
            except HTTPException as error:
                return error.status_code
        with ThreadPoolExecutor(max_workers=8) as pool:
            statuses = list(pool.map(consume, range(8)))
        self.assertEqual(statuses.count(200), 1)
        self.assertEqual(statuses.count(400), 7)

    def test_changed_subject_version_and_redis_outage_fail_closed(self):
        query, headers = self.start()
        with Session(self.engine) as db:
            db.get(User, 4).google_sub = b"changed-subject"; db.commit()
        self.assertTrue(self.callback(query, "changed-subject").headers["location"].endswith("#google-error"))
        with Session(self.engine) as db:
            db.get(User, 4).google_sub = b"google-4"; db.commit()
        query, headers = self.start()
        self.callback(query)
        with patch.object(self.store.client, "eval", side_effect=ConnectionError("isolated outage")):
            r = self.complete(headers)
        self.assertEqual(r.status_code, 503)
        self.assertNotIn("isolated outage", r.text)
        with Session(self.engine) as db:
            self.assertIsNone(db.get(User, 4).password_hash)
        query, headers = self.start()
        with Session(self.engine) as db:
            db.execute(update(User).where(User.id == 4).values(auth_version=1)); db.commit()
        self.assertTrue(self.callback(query).headers["location"].endswith("#google-error"))

    def test_stale_google_login_and_link_proofs_rejected(self):
        browser = "isolated-browser"
        with Session(self.engine) as db:
            handle = self.store.put("completion", browser, {"action": "login", "identity": {"sub": "google-4"}, "user_id": 4, "auth_version": 0, "remember": False}, 60)
            db.execute(update(User).where(User.id == 4).values(auth_version=1)); db.commit()
            with self.assertRaises(HTTPException) as caught:
                service.complete(db, handle, browser)
            self.assertEqual(caught.exception.status_code, 401)
        auth = self.headers()["Authorization"]
        handle = self.store.put("link-completion", browser, {"user_id": 1, "auth_version": 0,
            "password_digest": digest(self.hash), "session_digest": digest(auth), "reauthenticated_at": time.time(), "identity": {"sub": "linked-subject"}}, 60)
        with Session(self.engine) as db:
            db.execute(update(User).where(User.id == 1).values(auth_version=1)); db.commit()
            user = db.get(User, 1)
            with self.assertRaises(HTTPException) as caught:
                service.link(db, handle, browser, user, auth)
            self.assertEqual(caught.exception.status_code, 401)
            self.assertIsNone(user.google_sub)
