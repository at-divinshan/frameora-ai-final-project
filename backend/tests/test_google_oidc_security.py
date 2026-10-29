"""Offline ID-token cryptography checks: no Google or other network requests."""

from dataclasses import replace
import json
import secrets
import time
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
import jwt

from app.core import google_oidc


class OidcSecurityTests(unittest.TestCase):
    def test_id_token_signature_claims_and_pkce_exchange(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
        public.update(kid="isolated-key", alg="RS256", use="sig")
        now = int(time.time())
        claims = dict(iss="https://accounts.google.com", aud="isolated-client", exp=now+60,
                      iat=now, sub="isolated-subject", nonce="isolated-nonce", email="verified@example.com", email_verified=True)
        config = replace(google_oidc.settings, google_client_id="isolated-client", google_client_secret=secrets.token_urlsafe(20))
        with patch.object(google_oidc, "settings", config), patch("authlib.integrations.httpx_client.OAuth2Client") as oauth, patch("httpx.Client") as http:
            oauth_client = oauth.return_value.__enter__.return_value
            http.return_value.__enter__.return_value.get.return_value.json.return_value = {"keys": [public]}
            def exchange(payload, signing_key=key):
                oauth_client.fetch_token.return_value = {"id_token": jwt.encode(payload, signing_key, algorithm="RS256", headers={"kid": "isolated-key"})}
                return google_oidc.exchange_identity("isolated-code", "isolated-verifier", "isolated-nonce")
            self.assertEqual(exchange(claims), {"sub": "isolated-subject", "email": "verified@example.com"})
            oauth_client.fetch_token.assert_called_with(google_oidc.TOKEN_URL, code="isolated-code", code_verifier="isolated-verifier")
            for invalid in ({**claims, "iss": "https://untrusted.example"}, {**claims, "aud": "wrong-client"},
                            {**claims, "exp": now-1}, {**claims, "nonce": "wrong-nonce"},
                            {**claims, "email_verified": False}, {**claims, "email_verified": "true"},
                            {**claims, "iat": now+3600}, {**claims, "sub": ""},
                            {k:v for k,v in claims.items() if k != "nonce"},
                            {**claims, "aud": ["isolated-client", "other"]},
                            {**claims, "azp": "other"}, {**claims, "at_hash": "wrong"}):
                with self.assertRaises(HTTPException) as caught:
                    exchange(invalid)
                self.assertEqual(caught.exception.status_code, 400)
            with self.assertRaises(HTTPException):
                exchange(claims, other)
