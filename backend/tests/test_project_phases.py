"""Day 2 tests: isolated SQLite, synthetic images, no live DB/provider calls."""
import unittest
from unittest.mock import patch
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.project_generation_phase import ProjectGenerationPhase as Phase, ShareLinkPhase
from app.models.share_link import ShareLink
from app.models.ai_generation import AIGeneration
from app.models.media_asset import MediaAsset
from app.models.customer_project import CustomerProject
from app.models.user import User
from app.models.image_feedback import ImageFeedback
from app.services import project_phase_service as phases
import test_owner_credits as owner
import test_sharing as sharing


class GenerationPhaseTests(unittest.TestCase):
    auth = owner.OwnerCreditTests.auth
    activate = owner.OwnerCreditTests.activate
    generate = owner.OwnerCreditTests.generate
    generate_for_project = owner.OwnerCreditTests.generate_for_project
    ledger = owner.OwnerCreditTests.ledger
    def setUp(self):
        owner.OwnerCreditTests.setUp(self)
        ShareLink.__table__.create(self.engine)
        Phase.__table__.create(self.engine)
        ShareLinkPhase.__table__.create(self.engine)
        self.assertEqual(self.activate('trial').status_code, 200)
    tearDown = owner.OwnerCreditTests.tearDown

    def test_success_retry_failure_and_folder_counts(self):
        first = self.generate_for_project(1)
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(first.json()['phase_number'], 1)
        again = self.generate_for_project(1)
        self.assertEqual(again.json()['phase_id'], first.json()['phase_id'])
        second = self.generate_for_project(1, key='second-phase-key')
        self.assertEqual(second.json()['phase_number'], 2)
        folders = self.client.get('/ai/gallery/folders', headers=self.headers)
        self.assertEqual(folders.status_code, 200, folders.text)
        self.assertEqual(folders.json()[0]['image_count'], 16)
        contents = self.client.get('/ai/gallery/folders/1', headers=self.headers)
        self.assertEqual([g['phase_number'] for g in contents.json()['items']], [2,1])
        self.assertEqual(self.client.get('/ai/gallery/folders/1', headers=self.auth(4)).status_code,404)
        self.assertEqual(self.client.get('/ai/gallery/folders/1').status_code,401)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Phase)),2)
        from fastapi import HTTPException
        self.mock.side_effect=HTTPException(502,'mock failure')
        self.assertEqual(self.generate_for_project(1,key='failed-phase-key').status_code,503)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Phase)),2)

    def test_unassigned_and_no_schema_compatibility(self):
        ShareLinkPhase.__table__.drop(self.engine)
        Phase.__table__.drop(self.engine)
        result = self.generate()
        self.assertEqual(result.status_code,201,result.text)
        self.assertIsNone(result.json()['phase_number'])
        folders = self.client.get('/ai/gallery/folders',headers=self.headers).json()
        self.assertEqual(folders[0]['key'],'unassigned')
        self.assertEqual(folders[0]['image_count'],8)
        self.assertEqual(folders[0]['name'],'Unassigned Images')


class PublicationTests(unittest.TestCase):
    auth=sharing.SharingTests.auth
    activate=sharing.SharingTests.activate
    create=sharing.SharingTests.create
    _add_generations=sharing.SharingTests._add_generations
    _create_link=sharing.SharingTests._create_link
    def setUp(self):
        sharing.SharingTests.setUp(self)
        Phase.__table__.create(self.engine)
        ShareLinkPhase.__table__.create(self.engine)
        ImageFeedback.__table__.create(self.engine)
        with Session(self.engine) as db:
            # These fixtures stand for newly completed batches, not historical backfill.
            for gid in self.generation_ids[:3]:
                phases.record_completed(db,db.get(AIGeneration,gid),self.now)
            db.commit()
            self.phase_ids=list(db.scalars(select(Phase.id).order_by(Phase.phase_number)))
    tearDown=sharing.SharingTests.tearDown

    def test_explicit_publication_is_idempotent_and_preserves_legacy_grant(self):
        created=self._create_link().json();token=created['token']
        url=f'/owner/projects/{self.project_id}/share-links/{created["id"]}/phases/{self.phase_ids[1]}'
        self.assertEqual(self.client.put(url,headers=self.auth(1)).status_code,403)
        self.assertEqual(self.client.put(url,headers=self.auth(4)).status_code,404)
        before=self.client.get(f'/sharing/{token}',headers=self.auth(1)).json()
        self.assertEqual(len(before['phases']),1)
        hidden=self.asset_ids[self.generation_ids[1]][0]
        self.assertEqual(self.client.get(f'/sharing/{token}/images/{hidden}',headers=self.auth(1)).status_code,404)
        for _ in range(2):
            response=self.client.put(url,headers=self.owner_headers)
            self.assertEqual(response.status_code,200,response.text)
        after=self.client.get(f'/sharing/{token}',headers=self.auth(1)).json()
        self.assertEqual([p['phase_number'] for p in after['phases']],[1,2])
        self.assertEqual(after['images'],before['images'])
        self.assertNotIn('file_url',str(after))
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ShareLinkPhase)),1)
        from test_ai import IMAGES
        with patch('app.services.ai_image_storage.read_image',return_value=IMAGES[0]):
            preview=self.client.get(f'/sharing/{token}/images/{hidden}',headers=self.auth(1))
            self.assertEqual(preview.status_code,200,preview.text[:100] if preview.status_code!=200 else '')
            self.assertEqual(preview.headers['content-type'],'image/jpeg')
            self.assertNotEqual(preview.content,IMAGES[0])
        still_hidden=self.asset_ids[self.generation_ids[2]][0]
        self.assertEqual(self.client.get(f'/sharing/{token}/images/{still_hidden}',headers=self.auth(1)).status_code,404)
        # Feedback uses the exact same published-image authorization.
        from app.services.feedback_service import shared_asset
        with Session(self.engine) as db:
            self.assertEqual(shared_asset(db,token,hidden)[2].id,hidden)
        self.client.delete(f'/owner/projects/{self.project_id}/share-links/{created["id"]}',headers=self.owner_headers)
        self.assertEqual(self.client.get(f'/sharing/{token}',headers=self.auth(1)).status_code,404)

    def test_missing_migration_keeps_original_link_and_blocks_publication(self):
        created=self._create_link().json()
        ShareLinkPhase.__table__.drop(self.engine);Phase.__table__.drop(self.engine)
        self.assertEqual(self.client.get(f'/sharing/{created["token"]}',headers=self.auth(1)).status_code,200)
        response=self.client.put(f'/owner/projects/{self.project_id}/share-links/{created["id"]}/phases/1',headers=self.owner_headers)
        self.assertEqual(response.status_code,503)


class NormalFolderTests(unittest.TestCase):
    def setUp(self):
        import test_ai
        test_ai.GenerationTests.setUp(self)
        CustomerProject.__table__.create(self.engine)
    def tearDown(self):
        import test_ai
        test_ai.GenerationTests.tearDown(self)
    auth = owner.OwnerCreditTests.auth

    def test_all_batches_counted_pagination_and_untrusted_project_links(self):
        from app.models.photography_plan import PhotographyPlan
        from datetime import datetime
        with Session(self.engine) as db:
            # A foreign project ID on a user's plan must not expose its name or cover.
            db.add(CustomerProject(id=30,studio_owner_id=2,customer_name='Private customer',project_title='Secret project'))
            db.flush()
            db.get(PhotographyPlan,1).project_id=30
            for index in range(22):
                row=AIGeneration(user_id=1,plan_id=1,quality='standard',status='completed',created_at=datetime(2026,1,1))
                db.add(row);db.flush()
                db.add(MediaAsset(user_id=1,plan_id=1,generation_id=row.id,asset_type='ai_generated',file_url='mock-only'))
            db.commit()
        response=self.client.get('/ai/gallery/folders',headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()[0]['image_count'],22)
        self.assertEqual(response.json()[0]['key'],'unassigned')
        self.assertNotIn('Secret',response.text)
        first=self.client.get('/ai/gallery/folders/unassigned',headers=self.headers).json()
        second=self.client.get('/ai/gallery/folders/unassigned',params={'before':first['next_before']},headers=self.headers).json()
        self.assertEqual(len(first['items']),20)
        self.assertEqual(len(second['items']),2)
        self.assertIsNone(second['next_before'])
        self.assertEqual(self.client.get('/ai/gallery/folders/30',headers=self.headers).status_code,404)
        self.assertEqual(self.client.get('/ai/gallery/folders',headers=self.auth(3)).status_code,403)
        self.assertEqual(self.client.get('/ai/gallery/folders',headers=self.auth(4)).json(),[])
