"""Isolated role-conversion and owner-history tests; no production DB or provider calls."""

from dataclasses import replace
import secrets
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.mysql import VARBINARY
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import test_users
from app.core import security
from app.database.connection import engine as production_engine, get_db
from app.main import app
from app.models.ai_generation import AIGeneration
from app.models.media_asset import MediaAsset
from app.models.photography_plan import PhotographyPlan
from app.models.profile import UserProfile
from app.models.user import User


@compiles(VARBINARY, "sqlite")
def sqlite_binary(type_, compiler, **kwargs):
    return "BLOB"


class OwnerUpgradeTests(unittest.TestCase):
    def setUp(self):
        test_users.ProfileTests.setUp(self)
        self.decoder.stop()
        self.key = patch.object(
            security,
            "settings",
            replace(security.settings, jwt_secret_key=secrets.token_urlsafe(48)),
        )
        self.key.start()
        UserProfile.__table__.create(self.engine)
        with Session(self.engine) as db:
            db.add(User(
                id=4, name="Unrelated Normal User", email="unrelated@example.invalid",
                role="user", password_hash="unrelated-fixture",
            ))
            user = db.get(User, 1)
            user.google_sub = b"linked-normal-user"
            user.phone = "+94771234567"
            user.profile_image = "a" * 64 + ".png"
            db.commit()

    def tearDown(self):
        self.key.stop()
        test_users.ProfileTests.tearDown(self)

    def auth(self, uid, version=0):
        token, _ = security.create_access_token(str(uid), False, version)
        return {"Authorization": f"Bearer {token}"}

    def upgrade(self, uid=1, *, version=0, remember_me=False, headers=None):
        return self.client.post(
            "/users/me/upgrade-to-owner",
            headers=headers or self.auth(uid, version),
            json={"remember_me": remember_me},
        )

    def test_converts_same_identity_and_repeated_call_preserves_onboarding(self):
        with Session(self.engine) as db:
            original = db.get(User, 1)
            identity = (original.id, original.email, original.password_hash,
                        original.google_sub, original.phone, original.profile_image)
        response = self.upgrade(remember_me=True)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["user"]["role"], "owner")
        self.assertEqual(response.json()["user"]["id"], "1")
        self.assertGreater(response.json()["expires_in"], 0)
        with Session(self.engine) as db:
            upgraded = db.get(User, 1)
            self.assertEqual(
                (upgraded.id, upgraded.email, upgraded.password_hash, upgraded.google_sub,
                 upgraded.phone, upgraded.profile_image),
                identity,
            )
            profile = db.get(UserProfile, 1)
            self.assertIsNotNone(profile)
            self.assertEqual(profile.onboarding_status, "pending_studio")
            profile.onboarding_status = "pending_plan"
            db.commit()

        repeated = self.upgrade(headers={"Authorization": "Bearer " + response.json()["access_token"]})
        self.assertEqual(repeated.status_code, 200, repeated.text)
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, 1).role, "owner")
            self.assertEqual(db.get(UserProfile, 1).onboarding_status, "pending_plan")

    def test_auth_version_rotation_invalidates_old_token_and_new_token_works(self):
        self.key.stop()
        self.key = patch.object(
            security,
            "settings",
            replace(security.settings, auth_version_enabled=True),
        )
        self.key.start()
        old_headers = self.auth(1, version=0)
        response = self.upgrade(headers=old_headers)
        self.assertEqual(response.status_code, 200, response.text)
        new_headers = {"Authorization": "Bearer " + response.json()["access_token"]}
        self.assertEqual(security.decode_access_claims(response.json()["access_token"])["auth_version"], 1)
        self.assertEqual(self.client.get("/auth/me", headers=new_headers).json()["role"], "owner")
        self.assertEqual(self.client.get("/auth/me", headers=old_headers).status_code, 401)

    def test_admin_and_other_accounts_cannot_be_converted(self):
        self.assertEqual(self.upgrade(uid=2).status_code, 200)
        self.assertEqual(self.upgrade(uid=3).status_code, 403)
        self.assertEqual(self.client.get("/owner/onboarding", headers=self.auth(3)).status_code, 403)
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, 2).role, "owner")
            self.assertEqual(db.get(User, 3).role, "admin")

    def test_owner_history_is_owner_only_read_only_and_preserves_user_records(self):
        PhotographyPlan.__table__.create(self.engine)
        AIGeneration.__table__.create(self.engine)
        MediaAsset.__table__.create(self.engine)
        with Session(self.engine) as db:
            plan = PhotographyPlan(
                user_id=1, photography_type="Portrait", people_count=2, environment="indoor",
            )
            db.add(plan)
            db.flush()
            generation = AIGeneration(
                user_id=1, plan_id=plan.id, quality="standard", status="completed",
            )
            db.add(generation)
            db.flush()
            db.add(MediaAsset(
                user_id=1, plan_id=plan.id, generation_id=generation.id,
                asset_type="ai_generated", file_url="private-test.png",
            ))
            db.commit()

        upgraded = self.upgrade()
        self.assertEqual(upgraded.status_code, 200, upgraded.text)
        owner_headers = {"Authorization": "Bearer " + upgraded.json()["access_token"]}
        plans = self.client.get("/owner/account-history/photography-plans", headers=owner_headers)
        gallery = self.client.get("/owner/account-history/generations", headers=owner_headers)
        next_gallery_page = self.client.get(
            "/owner/account-history/generations?before=1", headers=owner_headers,
        )
        self.assertEqual(plans.status_code, 200, plans.text)
        self.assertEqual(gallery.status_code, 200, gallery.text)
        self.assertEqual(next_gallery_page.status_code, 200, next_gallery_page.text)
        self.assertEqual(next_gallery_page.json(), [])
        self.assertEqual(len(plans.json()), 1)
        self.assertEqual(gallery.json()[0]["images"][0]["id"], 1)
        self.assertEqual(
            self.client.get("/owner/account-history/generations", headers=self.auth(4)).status_code,
            403,
        )
        self.assertEqual(
            self.client.post("/plans", headers=owner_headers, json={
                "photography_type": "Portrait", "people_count": 1, "environment": "indoor",
            }).status_code,
            403,
        )

        from app.services import ai_image_storage
        with patch.object(ai_image_storage, "read_image", return_value=b"previous-image"):
            image = self.client.get("/owner/account-history/images/1", headers=owner_headers)
        self.assertEqual(image.status_code, 200, image.text)
        self.assertEqual(image.content, b"previous-image")
        other_owner = self.upgrade(uid=2)
        other_owner_headers = {"Authorization": "Bearer " + other_owner.json()["access_token"]}
        self.assertEqual(
            self.client.get("/owner/account-history/images/1", headers=other_owner_headers).status_code,
            404,
        )
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, 1).role, "owner")
            self.assertEqual(db.get(PhotographyPlan, 1).user_id, 1)
            self.assertEqual(db.get(AIGeneration, 1).user_id, 1)

    def test_conversion_validation_and_missing_auth(self):
        self.assertEqual(self.client.post("/users/me/upgrade-to-owner").status_code, 401)
        self.assertEqual(
            self.client.post("/users/me/upgrade-to-owner", headers=self.auth(1), json={"role": "admin"}).status_code,
            422,
        )
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, 1).role, "user")
            self.assertIsNone(db.get(UserProfile, 1))

    def test_concurrent_conversion_requests_converge_on_same_owner_account(self):
        with TemporaryDirectory(prefix="frameora-owner-upgrade-") as folder:
            engine = create_engine(
                "sqlite:///" + str(Path(folder) / "isolated.sqlite"),
                connect_args={"check_same_thread": False, "timeout": 10},
            )

            @event.listens_for(engine, "connect")
            def sqlite_transaction_mode(connection, _):
                connection.isolation_level = None

            @event.listens_for(engine, "begin")
            def sqlite_begin(connection):
                connection.exec_driver_sql("BEGIN IMMEDIATE")

            User.__table__.create(engine)
            UserProfile.__table__.create(engine)
            with Session(engine) as db:
                db.add(User(
                    id=1, name="Concurrent User", email="concurrent@example.invalid",
                    role="user", password_hash="test-fixture",
                ))
                db.add(User(
                    id=2, name="Only Admin", email="admin@example.invalid",
                    role="admin",
                ))
                db.commit()

            def isolated_db():
                with Session(engine, expire_on_commit=False) as db:
                    yield db

            previous_override = app.dependency_overrides[get_db]
            app.dependency_overrides[get_db] = isolated_db
            client = TestClient(app)
            headers = self.auth(1)
            try:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    responses = list(pool.map(
                        lambda _: client.post(
                            "/users/me/upgrade-to-owner",
                            headers=headers,
                            json={"remember_me": False},
                        ),
                        range(2),
                    ))
                self.assertEqual([response.status_code for response in responses], [200, 200])
                self.assertEqual(
                    [response.json()["user"]["id"] for response in responses],
                    ["1", "1"],
                )
                with Session(engine) as db:
                    self.assertEqual(db.get(User, 1).role, "owner")
                    self.assertEqual(db.query(UserProfile).count(), 1)
                    self.assertEqual(db.get(UserProfile, 1).onboarding_status, "pending_studio")
            finally:
                client.close()
                app.dependency_overrides[get_db] = previous_override
                engine.dispose()
