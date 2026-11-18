"""Offline deployment configuration and public-role guards."""
import unittest
from unittest.mock import patch, Mock
from dataclasses import replace
from types import SimpleNamespace
from cryptography.fernet import Fernet
from fastapi import HTTPException
from app.core import google_oidc
from app.services import google_auth_service

class GoogleDeploymentTests(unittest.TestCase):
    def config(self, **overrides):
        values=dict(google_auth_enabled=True, google_client_id='synthetic-client',
                    google_client_secret='synthetic-secret',
                    google_redirect_uri='https://backend.example/auth/google/callback',
                    frontend_origin='https://frontend.example',
                    google_completion_url='https://frontend.example/auth/google/callback',
                    redis_url='redis://redis.railway.internal:6379',
                    oauth_transaction_key=Fernet.generate_key().decode(),oauth_cookie_secure=True)
        values.update(overrides)
        return replace(google_oidc.settings, **values)

    def test_private_railway_and_tls_allowed(self):
        for url in ['redis://redis.railway.internal:6379','redis://localhost:6379','redis://127.0.0.1:6379','redis://[::1]:6379','rediss://remote.example:6380']:
            with self.subTest(url=url), patch.object(google_oidc,'settings',self.config(redis_url=url)):
                google_oidc.require_configuration()

    def test_other_plaintext_hosts_rejected(self):
        for host in ['other.railway.internal','redis.railway.internal.evil.example','10.0.0.1','redis.railway.internal.']:
            with self.subTest(host=host), patch.object(google_oidc,'settings',self.config(redis_url=f'redis://{host}:6379')):
                with self.assertRaises(HTTPException): google_oidc.require_configuration()

    def test_disabled_missing_or_insecure_configuration_stays_blocked(self):
        for changes in [dict(google_auth_enabled=False),dict(google_client_id=''),dict(google_client_secret=''),dict(oauth_transaction_key=''),dict(oauth_cookie_secure=False),dict(google_redirect_uri='https://backend.example/wrong'),dict(google_completion_url='https://other.example/auth/google/callback')]:
            with self.subTest(changes=changes),patch.object(google_oidc,'settings',self.config(**changes)):
                with self.assertRaises(HTTPException): google_oidc.require_configuration()

    def test_admin_login_and_link_rejected(self):
        admin=SimpleNamespace(id=1,role='admin')
        with self.assertRaises(HTTPException): google_auth_service.public_account(admin)
        with patch.object(google_auth_service,'get_store') as store:
            with self.assertRaises(HTTPException): google_auth_service.link(Mock(),'handle','browser',admin,'synthetic-session')
            store.assert_not_called()
        for role in ['user','owner']:
            google_auth_service.public_account(SimpleNamespace(role=role))

    def test_proxy_callback_same_origin_and_no_loop(self):
        callback='https://frontend.example/oauth-api/auth/google/callback'
        with patch.object(google_oidc,'settings',self.config(google_redirect_uri=callback)):
            google_oidc.require_configuration()
        for changes in [dict(google_redirect_uri='https://evil.example/oauth-api/auth/google/callback'),
                        dict(google_redirect_uri=callback,google_completion_url=callback),
                        dict(google_redirect_uri='https://frontend.example/auth/google/callback')]:
            with self.subTest(changes=changes),patch.object(google_oidc,'settings',self.config(**changes)):
                with self.assertRaises(HTTPException): google_oidc.require_configuration()

    def test_cookie_attributes_and_origin_guard_preserved(self):
        from app.routers import google_auth
        from fastapi import Response
        with patch.object(google_auth,'settings',self.config()),patch.object(google_auth,'require_configuration'):
            response=Response()
            google_auth.set_cookie(response,'binding','synthetic',300)
            cookie=response.headers['set-cookie']
            for expected in ['__Host-frameora-google-binding=', 'HttpOnly','Secure','SameSite=lax','Path=/']:
                self.assertIn(expected,cookie)
            self.assertNotIn('Domain=',cookie)
            with self.assertRaises(HTTPException):
                google_auth.google_ready(SimpleNamespace(method='POST',headers={'origin':'https://evil.example','content-type':'application/json'}))

    def test_callback_redirects_to_fixed_spa_not_proxy_or_forwarded_host(self):
        from app.routers import google_auth
        from starlette.datastructures import QueryParams
        config=self.config(google_redirect_uri='https://frontend.example/oauth-api/auth/google/callback')
        request=SimpleNamespace(query_params=QueryParams('state=synthetic&code=synthetic'),
            cookies={'__Host-frameora-google-binding':'synthetic-binding'},
            headers={'x-forwarded-host':'evil.example','host':'evil.example'})
        with patch.object(google_auth,'settings',config),patch.object(google_auth.service,'callback',return_value=('synthetic-handle','completion')) as callback:
            response=google_auth.callback(request,db=Mock())
            self.assertEqual(response.status_code,303)
            self.assertEqual(response.headers['location'],'https://frontend.example/auth/google/callback')
            self.assertIn('__Host-frameora-google-completion=',response.headers['set-cookie'])
            callback.assert_called_once()
