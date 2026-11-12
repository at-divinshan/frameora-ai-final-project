"""Offline OAuth flow and diagnostic checks with disposable SQLite/private Redis."""

from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch
import unittest

from app.core import oauth_diagnostics, google_oidc
from app.services import google_auth_service as service
from stage4_support import IsolatedStage4


class GoogleFlowTests(IsolatedStage4):
    enabled = False

    def test_inactive_callback_returns_safe_explicit_error(self):
        from sqlalchemy.orm import Session
        from app.models.account_status import AccountStatus, AccountStatusAudit
        from app.models.user import User
        from app.services.admin_users_service import change
        from app.schemas.admin_users import StatusChange
        for model in (AccountStatus, AccountStatusAudit):
            model.__table__.create(self.engine)
        query = self.start()
        with Session(self.engine) as db:
            change(db, db.get(User, 3), 4, StatusChange(is_active=False, expected_version=0))
        response = self.callback(query)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers['location'], self.settings.google_completion_url + '#google-inactive')

    def start(self):
        response = self.client.post('/auth/google/start', json={'remember_me': False},
                                    headers={'Origin': self.settings.frontend_origin})
        self.assertEqual(response.status_code, 200)
        query = parse_qs(urlsplit(response.json()['authorization_url']).query)
        self.assertEqual(query['prompt'], ['select_account'])
        self.assertEqual(query['code_challenge_method'], ['S256'])
        return query

    def callback(self, query, subject='google-4', email='account4@example.com'):
        with patch.object(service, 'exchange_identity', return_value={'sub': subject, 'email': email}):
            return self.client.get('/auth/google/callback', params={'state': query['state'][0], 'code': 'test-code'}, follow_redirects=False)

    def test_existing_login_completion_jwt_and_role(self):
        for uid, role in ((4, 'user'), (5, 'owner')):
            result = self.callback(self.start(), f'google-{uid}', f'account{uid}@example.com')
            self.assertEqual(result.status_code, 303)
            self.assertEqual(result.headers['location'], self.settings.google_completion_url)
            completed = self.client.post('/auth/google/complete', json={}, headers={'Origin': self.settings.frontend_origin})
            self.assertEqual(completed.status_code, 200, completed.text)
            self.assertEqual(completed.json()['user']['role'], role)
            auth = {'Authorization': 'Bearer ' + completed.json()['access_token']}
            self.assertEqual(self.client.get('/auth/me', headers=auth).status_code, 200)

    def test_registration_handoff_preserved(self):
        result = self.callback(self.start(), 'new-subject', 'new@example.com')
        self.assertEqual(result.headers['location'], self.settings.google_completion_url)
        response = self.client.post('/auth/google/complete', json={}, headers={'Origin': self.settings.frontend_origin})
        self.assertEqual(response.json(), {'status': 'registration_required'})
        registered = self.client.post('/auth/google/register', json={'name':'Test Person', 'role':'user', 'accept_terms':True},
                                      headers={'Origin':self.settings.frontend_origin})
        self.assertEqual(registered.status_code, 200)
        self.assertEqual(registered.json()['user']['role'], 'user')

    def test_explicit_link_and_password_login_preserved(self):
        login = self.client.post('/auth/login', json={'email':'account1@example.com', 'password':self.old_password})
        self.assertEqual(login.status_code, 200)
        headers = {'Origin':self.settings.frontend_origin, 'Authorization':'Bearer ' + login.json()['access_token']}
        started = self.client.post('/auth/google/link/start', headers=headers,
                                   json={'password':self.old_password, 'consent':True})
        self.assertEqual(started.status_code, 200)
        query = parse_qs(urlsplit(started.json()['authorization_url']).query)
        result = self.callback(query, 'linked-subject', 'account1@example.com')
        self.assertEqual(result.headers['location'], self.settings.google_completion_url)
        linked = self.client.post('/auth/google/link/complete', headers=headers, json={'consent':True})
        self.assertEqual(linked.json(), {'status':'linked'})
        login = self.client.post('/auth/login', json={'email':'account1@example.com', 'password':self.old_password})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()['user']['role'], 'user')

    def test_missing_browser_cookie_logs_only_fixed_stage(self):
        query = self.start()
        self.client.cookies.clear()
        with self.assertLogs(oauth_diagnostics.logger, level='WARNING') as logs:
            response = self.callback(query)
        self.assertTrue(response.headers['location'].endswith('#google-error'))
        self.assertTrue(any('stage=browser_binding' in line for line in logs.output))
        self.assertFalse(any(query['state'][0] in line or 'test-code' in line for line in logs.output))

    def test_missing_transaction_and_replay_fail_closed(self):
        query = self.start()
        self.callback(query)
        with self.assertLogs(oauth_diagnostics.logger, level='WARNING') as logs:
            response = self.callback(query)
        self.assertTrue(response.headers['location'].endswith('#google-error'))
        self.assertTrue(any('stage=transaction_no_match' in line for line in logs.output))

    def test_old_origin_rejected(self):
        with self.assertLogs(oauth_diagnostics.logger, level='WARNING') as logs:
            response = self.client.post('/auth/google/start', json={'remember_me':False}, headers={'Origin':'http://127.0.0.1:5173'})
        self.assertEqual(response.status_code, 403)
        self.assertTrue(any('stage=origin' in line for line in logs.output))


class DiagnosticSanitizationTests(unittest.TestCase):
    def test_unknown_event_and_exception_contents_never_logged(self):
        with self.assertLogs(oauth_diagnostics.logger, level='WARNING') as logs:
            oauth_diagnostics.failure('sensitive-marker')
            with patch('authlib.integrations.httpx_client.OAuth2Client', side_effect=RuntimeError('sensitive-marker')):
                with self.assertRaises(Exception):
                    google_oidc.exchange_identity('sensitive-code', 'sensitive-verifier', 'sensitive-nonce')
        self.assertTrue(any('stage=token_exchange' in line for line in logs.output))
        self.assertNotIn('sensitive', '\n'.join(logs.output))
