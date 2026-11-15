"""Owner management uses isolated SQLite fixtures, never the real MySQL database."""
import unittest
from datetime import timedelta
from hashlib import sha256
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import test_sharing as sharing
from app.models.share_link import ShareLink
from app.models.ai_generation import AIGeneration
from app.models.project_generation_phase import ProjectGenerationPhase as Phase, ShareLinkPhase
from app.services.project_phase_service import record_completed

class ManagementTests(unittest.TestCase):
    auth=sharing.SharingTests.auth
    activate=sharing.SharingTests.activate
    create=sharing.SharingTests.create
    _add_generations=sharing.SharingTests._add_generations
    _create_link=sharing.SharingTests._create_link
    tearDown=sharing.SharingTests.tearDown
    def setUp(self):
        sharing.SharingTests.setUp(self)
        Phase.__table__.create(self.engine);ShareLinkPhase.__table__.create(self.engine)
        with Session(self.engine) as db:
            for gid in self.generation_ids[:2]:record_completed(db,db.get(AIGeneration,gid),self.now)
            db.commit()
            self.phase_id=db.scalar(select(Phase.id).where(Phase.phase_number==2))
    def test_owner_scope_filter_and_phase_publication(self):
        link=self._create_link().json()
        self.assertEqual(self.client.get('/owner/share-links').status_code,401)
        for query in ('user_id=2','before=-1','project_id=1&project_id=2'):
            self.assertEqual(self.client.get('/owner/share-links?'+query,headers=self.owner_headers).status_code,422)
        self.assertEqual(self.client.get('/owner/share-links',headers=self.auth(1)).status_code,403)
        self.assertEqual(self.client.get('/owner/share-links',headers=self.auth(3)).status_code,403)
        self.assertEqual(self.activate(owner_headers=self.second_owner_headers).status_code,200)
        self.assertEqual(self.client.get('/owner/share-links',headers=self.second_owner_headers).json()['items'],[])
        self.assertEqual(self.client.get('/owner/share-links',params={'project_id':self.project_id},headers=self.second_owner_headers).status_code,404)
        response=self.client.get('/owner/share-links',params={'project_id':self.project_id},headers=self.owner_headers)
        self.assertEqual(response.status_code,200,response.text)
        row=response.json()['items'][0]
        self.assertIsNone(row['url']);self.assertNotIn('token_hash',response.text);self.assertNotIn(link['token'],response.text)
        self.assertEqual([p['number'] for p in row['published_phases']],[1])
        self.assertEqual([p['number'] for p in row['unpublished_phases']],[2])
        url=f'/owner/projects/{self.project_id}/share-links/{link["id"]}/phases/{self.phase_id}'
        for _ in range(2):self.assertEqual(self.client.put(url,headers=self.owner_headers).status_code,200)
        row=self.client.get('/owner/share-links',headers=self.owner_headers).json()['items'][0]
        self.assertEqual(row['unpublished_phases'],[])
        self.assertEqual([p['number'] for p in row['published_phases']],[1,2])
        with Session(self.engine) as db:self.assertEqual(db.scalar(select(func.count()).select_from(ShareLinkPhase)),1)
    def test_reactivation_keeps_token_and_publications_and_enforces_limits(self):
        link=self._create_link().json();url=f'/owner/projects/{self.project_id}/share-links/{link["id"]}'
        publish=f'{url}/phases/{self.phase_id}'
        self.assertEqual(self.client.put(publish,headers=self.owner_headers).status_code,200)
        self.assertEqual(self.client.patch(url,headers=self.owner_headers,json={'is_active':False}).status_code,200)
        self.assertEqual(self.client.get(f'/sharing/{link["token"]}',headers=self.auth(1)).status_code,404)
        for _ in range(2):self.assertEqual(self.client.patch(url,headers=self.owner_headers,json={'is_active':True}).status_code,200)
        shared=self.client.get(f'/sharing/{link["token"]}',headers=self.auth(1))
        self.assertEqual(shared.status_code,200,shared.text);self.assertEqual(len(shared.json()['phases']),2)
        with Session(self.engine) as db:self.assertEqual(db.get(ShareLink,link['id']).token_hash,sha256(link['token'].encode()).hexdigest())
        self.client.patch(url,headers=self.owner_headers,json={'is_active':False})
        for gid in self.generation_ids[1:4]:self.assertEqual(self._create_link(gid).status_code,201)
        self.assertEqual(self.client.patch(url,headers=self.owner_headers,json={'is_active':True}).status_code,409)
        with Session(self.engine) as db:self.assertFalse(db.get(ShareLink,link['id']).is_active)
    def test_expiry_wrong_project_and_strict_status(self):
        link=self._create_link(expires_at=self.now+timedelta(minutes=1)).json()
        url=f'/owner/projects/{self.project_id}/share-links/{link["id"]}'
        self.assertEqual(self.client.patch(url,headers=self.auth(1),json={'is_active':False}).status_code,403)
        self.assertEqual(self.client.patch(url,headers=self.second_owner_headers,json={'is_active':False}).status_code,404)
        self.assertEqual(self.client.patch(url,headers=self.owner_headers,json={'is_active':'true'}).status_code,422)
        self.assertEqual(self.client.patch(url,headers=self.owner_headers,json={'is_active':True,'project_id':2}).status_code,422)
        other=self.create().json()['id']
        self.assertEqual(self.client.patch(url.replace(f'/projects/{self.project_id}/',f'/projects/{other}/'),headers=self.owner_headers,json={'is_active':True}).status_code,404)
        self.now+=timedelta(minutes=2)
        self.assertEqual(self.client.patch(url,headers=self.owner_headers,json={'is_active':True}).status_code,409)
    def test_unassigned_legacy_links_are_listed_without_invented_project(self):
        with Session(self.engine) as db:
            db.add(ShareLink(project_id=None,generation_id=self.generation_ids[0],token_hash='legacy-only',is_active=False))
            db.commit()
        response=self.client.get('/owner/share-links',headers=self.owner_headers)
        self.assertEqual(response.status_code,200,response.text)
        row=response.json()['items'][0]
        self.assertIsNone(row['project_id']);self.assertFalse(row['manageable'])
        self.assertEqual(row['unpublished_phases'],[])

    def test_existing_project_pagination_query_is_accepted(self):
        response=self.client.get(f'/owner/projects/{self.project_id}/ai/generations',params={'before':999},headers=self.owner_headers)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.get(f'/owner/projects/{self.project_id}/ai/generations',params={'before':-1},headers=self.owner_headers).status_code,422)
        self.assertEqual(self.client.get(f'/owner/projects/{self.project_id}/ai/generations',params={'user_id':2},headers=self.owner_headers).status_code,422)

    def test_history_pagination_and_missing_phase_schema(self):
        with Session(self.engine) as db:
            for index in range(53):db.add(ShareLink(project_id=self.project_id,generation_id=self.generation_ids[0],token_hash=sha256(str(index).encode()).hexdigest(),is_active=False))
            db.commit()
        ShareLinkPhase.__table__.drop(self.engine);Phase.__table__.drop(self.engine)
        first=self.client.get('/owner/share-links',headers=self.owner_headers).json()
        self.assertFalse(first['phase_publication_available']);self.assertEqual(len(first['items']),50)
        second=self.client.get('/owner/share-links',params={'before':first['next_before']},headers=self.owner_headers).json()
        self.assertEqual(len(second['items']),3);self.assertIsNone(second['next_before'])
