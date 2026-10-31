"""Read-only Admin APIs on disposable SQLite; production connections blocked."""
import unittest
from unittest.mock import patch
from sqlalchemy import event
from sqlalchemy.orm import Session
import test_privacy
import test_owner_subscriptions
from app.models.profile import UserProfile
from app.models.user import User

class AdminTests(unittest.TestCase):
    auth = test_privacy.PrivacyTests.auth
    def setUp(self):
        test_privacy.PrivacyTests.setUp(self)
        UserProfile.__table__.create(self.engine)
        self.headers = self.auth(3)
        with Session(self.engine) as db:
            db.add(User(id=4,name='Second Owner',email='second@example.invalid',role='owner'))
            db.add(UserProfile(user_id=2,studio_name='North Studio',studio_phone='0771234567',studio_address='10 Road',studio_city='Jaffna',studio_description='Private studio description',onboarding_status='pending_plan'))
            db.commit()
    def tearDown(self):
        test_privacy.PrivacyTests.tearDown(self)
    def test_permissions(self):
        for path in ('/admin/summary','/admin/owners','/admin/owners/2','/admin/owners/2/photo'):
            for headers,expected in (({},401),(self.auth(1),403),(self.auth(2),403)):
                self.assertEqual(self.client.get(path,headers=headers).status_code,expected)
    def test_counts_and_safe_mapping(self):
        r=self.client.get('/admin/summary',headers=self.headers)
        self.assertEqual(r.json(),{'normal_users':1,'studio_owners':2})
        result=self.client.get('/admin/owners',headers=self.headers)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.headers['cache-control'],'no-store')
        self.assertEqual(result.json()['total'],2)
        records={r['id']:r for r in result.json()['items']}
        self.assertEqual(records[4]['onboarding_status'],'pending_studio')
        self.assertIsNone(records[4]['studio'])
        self.assertEqual(records[2]['studio']['studio_name'],'North Studio')
        for secret in ('password_hash','google_sub','privacy_preferences','auth_version'):
            self.assertNotIn(secret,result.text)
    def test_search_pagination_and_validation(self):
        for query,expected in [('q=Jaffna',1),('q=second',1),('q=%25',0),('onboarding=pending_studio',1),('onboarding=completed',0)]:
            r=self.client.get('/admin/owners?'+query,headers=self.headers)
            self.assertEqual(r.status_code,200,r.text); self.assertEqual(r.json()['total'],expected)
        first=self.client.get('/admin/owners?page_size=1',headers=self.headers).json()
        second=self.client.get('/admin/owners?page_size=1&page=2',headers=self.headers).json()
        self.assertNotEqual(first['items'][0]['id'],second['items'][0]['id'])
        for query in ('page=0','page_size=51','onboarding=admin','role=user','q='+'x'*101):
            self.assertEqual(self.client.get('/admin/owners?'+query,headers=self.headers).status_code,422)
    def test_missing_migrations_and_no_writes(self):
        with self.engine.begin() as connection:
            connection.exec_driver_sql('ALTER TABLE UserProfile DROP COLUMN studio_photo')
        statements=[]
        def capture(conn,cursor,sql,params,context,many): statements.append(sql)
        event.listen(self.engine,'before_cursor_execute',capture)
        try:
            r=self.client.get('/admin/owners/2',headers=self.headers)
            self.assertEqual(r.status_code,200,r.text)
            self.assertFalse(r.json()['photo_available'])
            self.assertEqual(r.json()['subscription_status'],'unavailable')
            self.assertIsNone(r.json()['subscription'])
            self.assertEqual(self.client.get('/admin/owners/4',headers=self.headers).status_code,200)
        finally: event.remove(self.engine,'before_cursor_execute',capture)
        self.assertFalse(any(s.lstrip().split()[0].upper() in ('INSERT','UPDATE','DELETE','ALTER','CREATE') for s in statements))
    def test_owner_targets_and_no_actions(self):
        for id in (1,3,999): self.assertEqual(self.client.get(f'/admin/owners/{id}',headers=self.headers).status_code,404)
        self.assertEqual(self.client.delete('/admin/owners/2',headers=self.headers).status_code,405)
        self.assertEqual(self.client.get('/admin/owners/2/photo',headers=self.headers).status_code,404)
    def test_admin_private_photo_access(self):
        import io
        from tempfile import TemporaryDirectory
        from types import SimpleNamespace
        from PIL import Image
        from app.services import profile_image_storage as storage
        with TemporaryDirectory() as folder, patch.object(storage,'settings',SimpleNamespace(profile_image_dir=folder)):
            data=io.BytesIO(); Image.new('RGB',(20,20),'blue').save(data,format='PNG')
            key=storage.write_image(storage.normalize_image(data.getvalue()))
            from sqlalchemy import select
            with Session(self.engine) as db:
                db.scalar(select(UserProfile).where(UserProfile.user_id==2)).studio_photo=key; db.commit()
            result=self.client.get('/admin/owners/2/photo',headers=self.headers)
            self.assertEqual(result.status_code,200)
            self.assertEqual(result.headers['content-type'],'image/png')
            self.assertEqual(result.headers['cache-control'],'no-store')
            self.assertEqual(result.headers['x-content-type-options'],'nosniff')
            self.assertTrue(self.client.get('/admin/owners/2',headers=self.headers).json()['has_photo'])
            self.assertEqual(self.client.get('/admin/owners/4/photo',headers=self.headers).status_code,409)
    def test_single_admin_policy_preserved(self):
        with Session(self.engine) as db:
            db.add(User(id=5,name='Other Admin',email='otheradmin@example.invalid',role='admin')); db.commit()
        self.assertNotEqual(self.client.get('/admin/owners',headers=self.headers).status_code,200)

class AdminSubscriptionTests(unittest.TestCase):
    auth = test_owner_subscriptions.OwnerSubscriptionTests.auth
    setUp = test_owner_subscriptions.OwnerSubscriptionTests.setUp
    tearDown = test_owner_subscriptions.OwnerSubscriptionTests.tearDown
    activate = test_owner_subscriptions.OwnerSubscriptionTests.activate
    def test_shared_entitlements_read_only(self):
        self.assertEqual(self.activate('basic').status_code,200)
        r=self.client.get('/admin/owners/2',headers=self.auth(3))
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['subscription']['remaining_credits'],10)
        self.assertEqual(r.json()['subscription_status'],'active')
