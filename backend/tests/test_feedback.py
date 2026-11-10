"""Isolated SQLite only; no real storage, providers or MySQL."""
from io import BytesIO
from PIL import Image
from unittest.mock import patch
from app.services import ai_image_storage
from app.services.shared_preview import preview_bytes
from fastapi import HTTPException
from datetime import timedelta
from uuid import uuid4
from sqlalchemy.orm import Session
from app.models.image_feedback import ImageFeedback
from app.models.customer_project import CustomerProject
from app.models.photography_plan import PhotographyPlan
from app.models.ai_generation import AIGeneration
import unittest
from test_sharing import SharingTests

class FeedbackTests(unittest.TestCase):
    auth = SharingTests.auth
    activate = SharingTests.activate
    create = SharingTests.create
    _add_generations = SharingTests._add_generations
    _create_link = SharingTests._create_link
    tearDown = SharingTests.tearDown
    def setUp(self):
        SharingTests.setUp(self)
        ImageFeedback.__table__.create(self.engine)
        self.link = self._create_link().json()
        self.asset = self.asset_ids[self.generation_ids[0]][0]
        self.url = f"/sharing/{self.link['token']}/images/{self.asset}/comments"
        self.owner_url = f"/owner/projects/{self.project_id}/feedback"

    def post(self, **values):
        return self.client.post(self.url, headers=self.auth(1), json={'comment':'Brighter please', 'request_key':str(uuid4()), **values})

    def test_comments_auth_scope_validation_and_retry(self):
        self.assertEqual(self.client.post(self.url, json={'comment':'x','request_key':str(uuid4())}).status_code,401)
        key=str(uuid4()); first=self.post(request_key=key)
        self.assertEqual(first.status_code,201,first.text)
        self.assertEqual(self.post(request_key=key).json()['id'],first.json()['id'])
        self.assertEqual(self.post(request_key=key,comment='different').status_code,409)
        for comment in ['', '   ', 'x'*2001, '\x00bad']:
            self.assertEqual(self.post(comment=comment).status_code,422)
        self.assertEqual(self.post(comment='<script>alert(1)</script>').status_code,201)
        own=self.client.get(self.url,headers=self.auth(1))
        self.assertEqual(len(own.json()),2)
        self.assertNotIn('author_name',own.text)
        self.assertEqual(self.client.get(self.url,headers=self.auth(4)).json(),[])
        other=self.asset_ids[self.generation_ids[1]][0]
        self.assertEqual(self.client.post(self.url.replace(f'/images/{self.asset}/',f'/images/{other}/'),headers=self.auth(1),json={'comment':'x','request_key':str(uuid4())}).status_code,404)

    def test_deactivated_and_expired_links_block_read_and_write(self):
        self.post()
        self.client.delete(f"/owner/projects/{self.project_id}/share-links/{self.link['id']}",headers=self.owner_headers)
        self.assertEqual(self.post().status_code,404)
        self.assertEqual(self.client.get(self.url,headers=self.auth(1)).status_code,404)
        link=self._create_link(self.generation_ids[1],expires_at=self.now+timedelta(minutes=1)).json()
        self.url=f"/sharing/{link['token']}/images/{self.asset_ids[self.generation_ids[1]][0]}/comments"
        self.now+=timedelta(minutes=1)
        self.assertEqual(self.post().status_code,404)
        self.assertEqual(self.client.get(self.url,headers=self.auth(1)).status_code,404)

    def test_owner_status_and_revision_authorization(self):
        row=self.post().json(); url=f"{self.owner_url}/{row['id']}"
        self.assertEqual(self.client.get(self.owner_url,headers=self.auth(1)).status_code,403)
        self.assertEqual(self.client.get(self.owner_url,headers=self.auth(4)).status_code,404)
        self.assertEqual(self.client.patch(url,headers=self.auth(4),json={'status':'resolved'}).status_code,404)
        for status in ['in_progress','resolved','pending']:
            result=self.client.patch(url,headers=self.owner_headers,json={'status':status})
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json()[0]['status'],status)
        self.assertEqual(self.client.patch(url,headers=self.owner_headers,json={'status':'bogus'}).status_code,422)
        self.assertEqual(self.client.patch(url,headers=self.owner_headers,json={'revised_asset_id':self.asset}).status_code,404)
        revised=self.asset_ids[self.generation_ids[1]][0]
        response=self.client.patch(url,headers=self.owner_headers,json={'revised_asset_id':revised})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()[0]['revised_asset_id'],revised)
        # Move that generation into a different project: even same-owner revisions must be scoped.
        with Session(self.engine) as db:
            project=CustomerProject(studio_owner_id=2,customer_name='Other',created_at=self.now)
            db.add(project);db.flush()
            plan=PhotographyPlan(user_id=2,project_id=project.id,photography_type='Portrait',people_count=1,environment='Outdoor')
            db.add(plan);db.flush()
            db.get(AIGeneration,self.generation_ids[1]).plan_id=plan.id;db.commit()
        self.assertEqual(self.client.patch(url,headers=self.owner_headers,json={'revised_asset_id':revised}).status_code,404)
        self.assertEqual(self.client.patch(url,headers=self.owner_headers,json={'revised_asset_id':None}).status_code,200)

    def test_pending_schema_does_not_break_gallery_and_originals_remain_private(self):
        ImageFeedback.__table__.drop(self.engine)
        self.assertEqual(self.post().status_code,503)
        self.assertEqual(self.client.get(f"/sharing/{self.link['token']}",headers=self.auth(1)).status_code,200)
        self.assertEqual(self.client.get(f'/owner/ai/images/{self.asset}',headers=self.auth(1)).status_code,403)
        self.assertEqual(self.client.get(f'/ai/images/{self.asset}',headers=self.auth(1)).status_code,404)

    def test_owner_original_delivery_and_small_invalid_previews(self):
        raw=BytesIO(); Image.new('RGB',(80,60),'navy').save(raw,format='PNG')
        with patch.object(ai_image_storage,'read_image',return_value=raw.getvalue()):
            original=self.client.get(f'/owner/ai/images/{self.asset}',headers=self.owner_headers)
            self.assertEqual(original.status_code,200,original.text)
            self.assertEqual(original.content,raw.getvalue())
            preview=self.client.get(f"/sharing/{self.link['token']}/images/{self.asset}",headers=self.auth(1))
            self.assertEqual(preview.status_code,200)
            self.assertNotEqual(preview.content,raw.getvalue())
            self.assertIn('no-store',preview.headers['cache-control'])
        with self.assertRaises(HTTPException): preview_bytes(b'not an image')
