"""Notification tests use isolated SQLite and existing provider-free fixtures."""
import unittest
from datetime import timedelta
from types import SimpleNamespace
from sqlalchemy.orm import Session
from app.models.app_notification import AppNotification
from app.models.user import User
from app.services import notification_service as service
import test_feedback as fixtures

class NotificationTests(unittest.TestCase):
    auth=fixtures.FeedbackTests.auth
    activate=fixtures.FeedbackTests.activate
    create=fixtures.FeedbackTests.create
    _add_generations=fixtures.FeedbackTests._add_generations
    _create_link=fixtures.FeedbackTests._create_link
    post=fixtures.FeedbackTests.post
    tearDown=fixtures.FeedbackTests.tearDown
    def setUp(self):
        fixtures.FeedbackTests.setUp(self)
        AppNotification.__table__.create(self.engine)

    def inbox(self, uid=1):
        response=self.client.get('/notifications',headers=self.auth(uid))
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def test_comment_status_replay_recipient_and_read_state(self):
        from uuid import uuid4
        key=str(uuid4());row=self.post(request_key=key).json()
        self.post(request_key=key)
        owner=self.inbox(2)
        self.assertEqual(owner['unread_count'],1)
        self.assertIn(f"#feedback-{row['id']}",owner['items'][0]['href'])
        self.assertEqual(self.inbox()['items'],[])
        url=f"{self.owner_url}/{row['id']}"
        for status in ['in_progress','resolved','pending']:
            self.assertEqual(self.client.patch(url,headers=self.owner_headers,json={'status':status}).status_code,200)
            self.client.patch(url,headers=self.owner_headers,json={'status':status})
        customer=self.inbox();self.assertEqual(customer['unread_count'],3)
        identifier=customer['items'][0]['id']
        self.assertEqual(self.client.patch(f'/notifications/{identifier}',headers=self.auth(4),json={'is_read':True}).status_code,404)
        self.assertEqual(self.client.patch(f'/notifications/{identifier}',headers=self.auth(1),json={'is_read':True}).status_code,200)
        self.assertEqual(self.inbox()['unread_count'],2)
        self.client.patch(f'/notifications/{identifier}',headers=self.auth(1),json={'is_read':False})
        self.assertEqual(self.inbox()['unread_count'],3)
        self.assertEqual(self.client.get('/notifications').status_code,401)
        self.assertEqual(self.client.get('/notifications',headers=self.auth(3)).status_code,403)
        page=self.client.get('/notifications?limit=1',headers=self.auth(1)).json()
        older=self.client.get(f"/notifications?limit=1&before={page['next_before']}",headers=self.auth(1)).json()
        self.assertNotEqual(page['items'][0]['id'],older['items'][0]['id'])

    def test_revision_link_and_share_no_new_access_grant(self):
        row=self.post().json();revised=self.asset_ids[self.generation_ids[1]][0]
        url=f"{self.owner_url}/{row['id']}"
        for _ in range(2):self.client.patch(url,headers=self.owner_headers,json={'revised_asset_id':revised})
        self.assertEqual(self.inbox()['unread_count'],1)
        self._create_link(self.generation_ids[1])
        self.assertEqual(self.inbox()['unread_count'],2)
        self.assertEqual(self.client.get(f"/sharing/{self.link['token']}/images/{revised}",headers=self.auth(1)).status_code,404)
        self.assertNotIn('token',str(self.inbox()))

    def test_threshold_expiry_dedupe_and_missing_migration(self):
        with Session(self.engine) as db:
            owner=db.get(User,2)
            state=dict(status='active',remaining_credits=2,batch_cost=2,subscription_id=1,period_start=self.now)
            sub=SimpleNamespace(id=9,plan_kind='trial',status='active',end_date=self.now+timedelta(days=1))
            for _ in range(2): service.owner_state(db,owner,state,[sub])
            state['remaining_credits']=0
            service.owner_state(db,owner,state,[sub])
            sub.end_date=self.now-timedelta(seconds=1)
            service.owner_state(db,owner,state,[sub])
            db.commit()
        self.assertEqual(self.inbox(2)['unread_count'],4)
        AppNotification.__table__.drop(self.engine)
        self.assertEqual(self.client.get('/notifications',headers=self.auth(1)).status_code,503)
        self.assertEqual(self.post().status_code,201)

    def test_invalid_link_never_creates_notification(self):
        self.client.delete(f"/owner/projects/{self.project_id}/share-links/{self.link['id']}",headers=self.owner_headers)
        self.assertEqual(self.post().status_code,404)
        self.assertEqual(self.inbox(2)['unread_count'],0)

    def test_project_and_share_limits_are_notified_once(self):
        self.assertEqual(self.create().status_code,201)
        self._create_link(self.generation_ids[1])
        self._create_link(self.generation_ids[2])
        first=self.inbox(2)
        self.assertEqual(first['unread_count'],2)
        self.assertEqual(self.inbox(2)['unread_count'],2)
        messages=' '.join(row['message'] for row in first['items'])
        self.assertIn('projects limit',messages)
        self.assertIn('share links limit',messages)

    def test_read_items_hidden_after_refresh_for_both_roles_without_deletion(self):
        for uid in (1,2):
            with Session(self.engine) as db:
                service.emit(db,uid,f'unread-only:{uid}','Unread test',f'/{"owner" if uid==2 else "user"}/notifications')
                db.commit()
            initial=self.inbox(uid)
            identifier=initial['items'][0]['id']
            for _ in range(2):
                response=self.client.patch(f'/notifications/{identifier}',headers=self.auth(uid),json={'is_read':True})
                self.assertEqual(response.status_code,200)
            for _ in range(2):
                refreshed=self.inbox(uid)
                self.assertEqual(refreshed['items'],[])
                self.assertEqual(refreshed['unread_count'],0)
                self.assertIsNone(refreshed['next_before'])
            with Session(self.engine) as db:
                stored=db.get(AppNotification,identifier)
                self.assertIsNotNone(stored)
                self.assertTrue(stored.is_read)
                self.assertEqual(stored.user_id,uid)
