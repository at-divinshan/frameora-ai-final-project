"""Share-link API tests use disposable SQLite and private-storage mocks only."""

from io import BytesIO
from PIL import Image
from datetime import timedelta
from hashlib import sha256
import unittest
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_generation import AIGeneration
from app.models.customer_project import CustomerProject
from app.models.media_asset import MediaAsset
from app.models.photography_plan import PhotographyPlan
from app.models.share_link import ShareLink
from app.services import ai_image_storage
from test_customer_projects import CustomerProjectTests


class SharingTests(unittest.TestCase):
    auth = CustomerProjectTests.auth
    activate = CustomerProjectTests.activate
    create = CustomerProjectTests.create

    def setUp(self):
        CustomerProjectTests.setUp(self)
        ShareLink.__table__.create(self.engine)
        MediaAsset.__table__.create(self.engine)
        self.assertEqual(self.activate().status_code, 200)
        self.project_id = self.create().json()["id"]
        response = self.client.post(
            f"/owner/projects/{self.project_id}/photography-plans",
            headers=self.owner_headers,
            json={
                "photography_type": "Portrait",
                "people_count": 2,
                "environment": "Outdoor",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.plan_id = response.json()["id"]
        self.generation_ids = []
        self.asset_ids = {}
        self._add_generations(self.plan_id, count=5)

    def tearDown(self):
        CustomerProjectTests.tearDown(self)

    def _add_generations(self, plan_id, *, count):
        with Session(self.engine) as db:
            for index in range(count):
                generation = AIGeneration(
                    user_id=2,
                    plan_id=plan_id,
                    quality="standard",
                    status="completed",
                    created_at=self.now + timedelta(seconds=index),
                )
                db.add(generation)
                db.flush()
                self.generation_ids.append(generation.id)
                assets = []
                for image_index in range(2):
                    asset = MediaAsset(
                        user_id=2,
                        plan_id=plan_id,
                        generation_id=generation.id,
                        asset_type="ai_generated",
                        file_url=f"image-{generation.id}-{image_index}",
                    )
                    db.add(asset)
                    db.flush()
                    assets.append(asset.id)
                self.asset_ids[generation.id] = assets
            db.commit()

    def _create_link(self, generation_id=None, *, expires_at=None):
        generation_id = generation_id or self.generation_ids[0]
        payload = {"generation_id": generation_id}
        if expires_at is not None:
            payload["expires_at"] = expires_at.isoformat()
        return self.client.post(
            f"/owner/projects/{self.project_id}/share-links",
            headers=self.owner_headers,
            json=payload,
        )

    def test_existing_eight_image_link_preserves_all_images(self):
        generation_id = self.generation_ids[0]
        with Session(self.engine) as db:
            for index in range(2, 8):
                db.add(MediaAsset(user_id=2, plan_id=self.plan_id, generation_id=generation_id,
                    asset_type='ai_generated', file_url=f'historical-{index}'))
            db.commit()
        created = self._create_link(generation_id)
        self.assertEqual(created.status_code, 201, created.text)
        token = created.json()['token']
        shared = self.client.get(f'/sharing/{token}', headers=self.auth(1))
        self.assertEqual(shared.status_code, 200, shared.text)
        self.assertEqual(len(shared.json()['images']), 8)

    def test_create_list_and_authenticated_image_access_store_only_token_hash(self):
        created = self._create_link()
        self.assertEqual(created.status_code, 201, created.text)
        body = created.json()
        token = body["token"]
        self.assertEqual(len(token), 43)
        self.assertEqual(body["generation_id"], self.generation_ids[0])

        with Session(self.engine) as db:
            link = db.get(ShareLink, body["id"])
            self.assertEqual(link.token_hash, sha256(token.encode("ascii")).hexdigest())
            self.assertNotEqual(link.token_hash, token)

        listed = self.client.get(
            f"/owner/projects/{self.project_id}/share-links",
            headers=self.owner_headers,
        )
        self.assertEqual(listed.status_code, 200)
        self.assertNotIn(token, listed.text)
        self.assertNotIn("token_hash", listed.text)
        self.assertEqual(listed.json()[0]["generation_id"], self.generation_ids[0])

        source = BytesIO()
        Image.new("RGB", (1600, 1200), "navy").save(source, format="PNG")
        with patch.object(ai_image_storage, "read_image", return_value=source.getvalue()) as read:
            shared = self.client.get(f"/sharing/{token}", headers=self.auth(1))
            self.assertEqual(shared.status_code, 200, shared.text)
            self.assertEqual(
                [image["id"] for image in shared.json()["images"]],
                self.asset_ids[self.generation_ids[0]],
            )
            image = self.client.get(
                f"/sharing/{token}/images/{self.asset_ids[self.generation_ids[0]][0]}",
                headers=self.auth(1),
            )
            self.assertEqual(image.status_code, 200)
            self.assertNotEqual(image.content, source.getvalue())
            self.assertEqual(image.headers['content-type'], 'image/jpeg')
            preview = Image.open(BytesIO(image.content))
            self.assertEqual(preview.size, (960, 720))
            self.assertGreater(len(set(preview.getdata())), 1)
            self.assertNotIn('file_url', shared.text)
            self.assertNotIn('image-', shared.text)
            self.assertEqual(read.call_args.args[0], f"image-{self.generation_ids[0]}-0")

        unauthorized = self.client.get(f"/sharing/{token}")
        self.assertEqual(unauthorized.status_code, 401)

    def test_owner_auth_project_and_generation_ownership_are_enforced(self):
        for headers, expected in ((None, 401), (self.auth(1), 403)):
            response = self.client.post(
                f"/owner/projects/{self.project_id}/share-links",
                headers=headers,
                json={"generation_id": self.generation_ids[0]},
            )
            self.assertEqual(response.status_code, expected)

        other_project = CustomerProject(
            studio_owner_id=4,
            customer_name="Other owner project",
            created_at=self.now,
        )
        with Session(self.engine) as db:
            db.add(other_project)
            db.commit()
            other_project_id = other_project.id
        self.assertEqual(
            self.client.post(
                f"/owner/projects/{other_project_id}/share-links",
                headers=self.owner_headers,
                json={"generation_id": self.generation_ids[0]},
            ).status_code,
            404,
        )

        other_generation = AIGeneration(
            user_id=4,
            plan_id=999,
            quality="standard",
            status="completed",
            created_at=self.now,
        )
        with Session(self.engine) as db:
            db.add(other_generation)
            db.commit()
            other_generation_id = other_generation.id
        self.assertEqual(self._create_link(other_generation_id).status_code, 404)
        self.assertEqual(
            self.client.get(
                f"/owner/projects/{other_project_id}/share-links",
                headers=self.owner_headers,
            ).status_code,
            404,
        )

    def test_expiry_deactivation_and_generation_scoping(self):
        self.assertEqual(
            self.client.get("/sharing/" + "a" * 43, headers=self.auth(1)).status_code,
            404,
        )
        created = self._create_link(
            self.generation_ids[0], expires_at=self.now + timedelta(minutes=1)
        )
        self.assertEqual(created.status_code, 201, created.text)
        token = created.json()["token"]
        other_image = self.asset_ids[self.generation_ids[1]][0]
        response = self.client.get(
            f"/sharing/{token}/images/{other_image}", headers=self.auth(1)
        )
        self.assertEqual(response.status_code, 404)

        self.now += timedelta(minutes=1)
        expired = self.client.get(f"/sharing/{token}", headers=self.auth(1))
        self.assertEqual(expired.status_code, 404)

        live = self._create_link(self.generation_ids[1])
        self.assertEqual(live.status_code, 201, live.text)
        link_id, live_token = live.json()["id"], live.json()["token"]
        deleted = self.client.delete(
            f"/owner/projects/{self.project_id}/share-links/{link_id}",
            headers=self.owner_headers,
        )
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(
            self.client.get(f"/sharing/{live_token}", headers=self.auth(1)).status_code,
            404,
        )

    def test_share_link_subscription_limit_is_enforced(self):
        for generation_id in self.generation_ids[:3]:
            response = self._create_link(generation_id)
            self.assertEqual(response.status_code, 201, response.text)
        denied = self._create_link(self.generation_ids[3])
        self.assertEqual(denied.status_code, 409, denied.text)

    def test_link_limit_and_downgrade_disables_excess_oldest_last(self):
        self.assertEqual(self.activate("trial").status_code, 200)
        links = []
        for generation_id in self.generation_ids[:4]:
            response = self._create_link(generation_id)
            self.assertEqual(response.status_code, 201, response.text)
            links.append(response.json())
        self.assertEqual(self._create_link(self.generation_ids[4]).status_code, 201)

        self.now = datetime_from_iso(self.client.get(
            "/owner/ai/eligibility", headers=self.owner_headers
        ).json()["subscription_end"])
        listed = self.client.get(
            f"/owner/projects/{self.project_id}/share-links",
            headers=self.owner_headers,
        )
        self.assertEqual(listed.status_code, 200, listed.text)
        by_id = {item["id"]: item["is_active"] for item in listed.json()}
        for item in links[:3]:
            self.assertTrue(by_id[item["id"]])
        self.assertFalse(by_id[links[3]["id"]])
        self.assertEqual(
            self.client.get(
                f"/sharing/{links[3]['token']}", headers=self.auth(1)
            ).status_code,
            404,
        )


def datetime_from_iso(value):
    from datetime import datetime

    return datetime.fromisoformat(value)


if __name__ == "__main__":
    unittest.main()
