"""Isolated SQLite and real test-signed JWTs; no live DB or provider calls."""
import unittest
from unittest.mock import patch, Mock
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from fastapi import HTTPException
import test_privacy
from app.models.user import User
from app.models.profile import UserProfile
from app.models.account_status import AccountStatus, AccountStatusAudit
from app.services import admin_users_service, auth_service
from app.schemas.admin_users import StatusChange
from app.repositories.user_repository import lock_profile
from app.core.account_state import require_active

class AdminUserTests(unittest.TestCase):
    auth=test_privacy.PrivacyTests.auth
    def setUp(self):
        test_privacy.PrivacyTests.setUp(self)
        for model in (UserProfile,AccountStatus,AccountStatusAudit):model.__table__.create(self.engine)
        self.admin=self.auth(3);self.customer=self.auth(1);self.owner=self.auth(2)
        with Session(self.engine) as db:
            db.get(User,1).email='role1@example.com'
            db.add(UserProfile(user_id=2,studio_name='Test Studio',studio_phone='0771234567',studio_address='Private studio road',studio_city='Jaffna',onboarding_status='completed'))
            db.commit()
    tearDown=test_privacy.PrivacyTests.tearDown
    def change(self,uid,active,version=0):
        return self.client.patch(f'/admin/users/{uid}/status',headers=self.admin,json={'is_active':active,'expected_version':version})

    def test_authorization_listing_details_filters_and_secret_allowlist(self):
        for headers,code in (({},401),(self.customer,403),(self.owner,403)):
            for url in ('/admin/users','/admin/users/1'):
                self.assertEqual(self.client.get(url,headers=headers).status_code,code)
            self.assertEqual(self.client.patch('/admin/users/1/status',headers=headers,json={'is_active':False,'expected_version':0}).status_code,code)
        listing=self.client.get('/admin/users',headers=self.admin)
        self.assertEqual(listing.status_code,200,listing.text)
        self.assertEqual(listing.json()['total'],2)
        self.assertEqual(self.client.get('/admin/users?role=owner',headers=self.admin).json()['total'],1)
        self.assertEqual(self.client.get('/admin/users?q=role1',headers=self.admin).json()['total'],1)
        self.assertEqual(self.client.get('/admin/users?q=%25',headers=self.admin).json()['total'],0)
        detail=self.client.get('/admin/users/2',headers=self.admin)
        self.assertEqual(detail.json()['studio']['studio_name'],'Test Studio')
        for secret in ('password_hash','google_sub','auth_version','access_token','privacy_preferences'):
            self.assertNotIn(secret,detail.text);self.assertNotIn(secret,listing.text)
        self.assertEqual(self.change(3,False).status_code,403)
        self.assertEqual(self.client.get('/admin/users/3',headers=self.admin).status_code,404)
        self.assertEqual(self.change(999,False).status_code,404)
        self.assertEqual(self.client.patch('/admin/users/1/status',headers=self.admin,json={'is_active':False,'expected_version':0,'role':'admin'}).status_code,422)

    def test_deactivate_login_old_tokens_reactivation_and_audit(self):
        self.assertEqual(self.client.get('/auth/me',headers=self.customer).status_code,200)
        result=self.change(1,False);self.assertEqual(result.status_code,200,result.text)
        self.assertFalse(result.json()['is_active'])
        self.assertEqual(self.client.get('/auth/me',headers=self.customer).status_code,401)
        self.assertEqual(self.client.get('/admin/users?status=inactive',headers=self.admin).json()['total'],1)
        with patch.object(auth_service,'verify_password',return_value=True):
            self.assertEqual(self.client.post('/auth/login',json={'email':'role1@example.com','password':'TestPassword123!'}).status_code,401)
            self.assertEqual(self.change(1,False).status_code,200)
            self.assertEqual(self.change(1,True,0).status_code,409)
            self.assertEqual(self.change(1,True,1).status_code,200)
            self.assertEqual(self.client.get('/auth/me',headers=self.customer).status_code,401)
            login=self.client.post('/auth/login',json={'email':'role1@example.com','password':'TestPassword123!'})
            self.assertEqual(login.status_code,200,login.text)
            self.assertEqual(self.client.get('/auth/me',headers={'Authorization':'Bearer '+login.json()['access_token']}).status_code,200)
        with Session(self.engine) as db:
            rows=list(db.scalars(select(AccountStatusAudit).order_by(AccountStatusAudit.id)))
            self.assertEqual([(r.actor_id,r.old_active,r.new_active,r.version) for r in rows],[(3,True,False,1),(3,False,True,2)])
            self.assertEqual(db.get(User,1).password_hash,'test-only-not-a-real-hash')

    def test_atomic_audit_failure_and_locked_work_revalidation(self):
        with Session(self.engine) as db:
            user=db.get(User,1);user._account_version=0
            self.assertEqual(self.change(1,False).status_code,200)
            with self.assertRaises(HTTPException):lock_profile(db,1)
            db.rollback()
        with Session(self.engine) as db:
            admin=db.get(User,3)
            with patch.object(db,'flush',side_effect=RuntimeError('audit write failure')):
                with self.assertRaises(RuntimeError):admin_users_service.change(db,admin,2,StatusChange(is_active=False,expected_version=0))
        with Session(self.engine) as db:
            self.assertIsNone(db.get(AccountStatus,2))
            self.assertEqual(db.scalar(select(func.count()).select_from(AccountStatusAudit)),1)

    def test_password_login_with_real_hash_and_committed_status(self):
        from app.core.security import hash_password
        password='IsolatedPassword123!'
        with Session(self.engine) as db:
            db.get(User,1).password_hash=hash_password(password)
            db.commit()
        body={'email':'role1@example.com','password':password}
        self.assertEqual(self.client.post('/auth/login',json=body).status_code,200)
        self.assertEqual(self.change(1,False).status_code,200)
        with Session(self.engine) as db:
            self.assertFalse(db.get(AccountStatus,1).is_active)
            self.assertEqual(db.scalar(select(func.count()).select_from(AccountStatusAudit)),1)
        rejected=self.client.post('/auth/login',json=body)
        self.assertEqual(rejected.status_code,401)
        self.assertIn('deactivated',rejected.json()['detail'])
        self.assertNotIn('access_token',rejected.json())
        self.assertEqual(self.change(1,True,1).status_code,200)
        self.assertEqual(self.client.get('/auth/me',headers=self.customer).status_code,401)
        self.assertEqual(self.client.post('/auth/login',json=body).status_code,200)

    def test_google_callback_completion_and_reactivation_reject_stale_proof(self):
        from app.services import google_auth_service as google
        from app.core.security import auth_versions_enabled
        store=Mock()
        identity={'sub':'test-subject','email':'role2@example.invalid'}
        def proof():
            store.consume.return_value={'action':'login','nonce':'nonce','verifier':'verifier',
                                        'remember':False,'versioned':auth_versions_enabled()}
            with Session(self.engine) as db:
                google.callback(db,'state','mock-code',None,'browser')
            return dict(store.put.call_args.args[2])
        def complete(data):
            store.consume.return_value=data
            with Session(self.engine) as db:
                return google.complete(db,'handle','browser')[0]
        with patch.object(google,'get_store',return_value=store), patch.object(google,'exchange_identity',return_value=identity):
            original=proof()
            token=complete(original).access_token
            self.assertEqual(original['account_version'],0)
            self.assertEqual(self.change(2,False).status_code,200)
            for action in (proof,lambda:complete(original)):
                with self.assertRaises(HTTPException) as caught:action()
                self.assertEqual(caught.exception.status_code,401)
                self.assertIn('deactivated',caught.exception.detail)
            self.assertEqual(self.client.get('/auth/me',headers={'Authorization':'Bearer '+token}).status_code,401)
            self.assertEqual(self.change(2,True,1).status_code,200)
            with self.assertRaises(HTTPException):complete(original)
            self.assertEqual(self.client.get('/auth/me',headers={'Authorization':'Bearer '+token}).status_code,401)
            fresh=proof()
            self.assertEqual(fresh['account_version'],2)
            token=complete(fresh).access_token
            self.assertEqual(self.client.get('/auth/me',headers={'Authorization':'Bearer '+token}).status_code,200)

    def test_missing_migration_preserves_login_but_management_is_unavailable(self):
        AccountStatusAudit.__table__.drop(self.engine);AccountStatus.__table__.drop(self.engine)
        response=self.client.get('/admin/users',headers=self.admin)
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json()['detail']['code'],'ADMIN_USERS_SCHEMA_UNAVAILABLE')
        self.assertEqual(self.client.get('/auth/me',headers=self.customer).status_code,200)

    def test_listing_without_optional_auth_version_column(self):
        # Reproduce the deployed legacy User schema, in disposable SQLite only.
        from sqlalchemy import text
        with self.engine.begin() as connection:
            connection.execute(text('ALTER TABLE "User" DROP COLUMN auth_version'))
        for query,total in (('',2),('?status=active',2),('?status=inactive',0),
                            ('?role=owner',1),('?q=role1',1),
                            ('?page=2&page_size=1',2)):
            response=self.client.get('/admin/users'+query,headers=self.admin)
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['total'],total)
            for user in response.json()['items']:
                self.assertTrue(user['is_active'])
                self.assertEqual(user['status_version'],0)
        page=self.client.get('/admin/users?page=2&page_size=1',headers=self.admin).json()
        self.assertEqual(len(page['items']),1)
        self.assertEqual(page['items'][0]['id'],1)
        self.assertEqual(self.client.get('/admin/users/2',headers=self.admin).status_code,200)
        self.assertEqual(self.change(1,False).status_code,200)
        inactive=self.client.get('/admin/users?status=inactive',headers=self.admin).json()
        self.assertEqual(inactive['total'],1)
        self.assertEqual(inactive['items'][0]['id'],1)
