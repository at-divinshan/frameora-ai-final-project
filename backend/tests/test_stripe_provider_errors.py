"""Sanitized provider failures; no network or database access."""
import unittest
import httpx
from fastapi import HTTPException
from app.core.stripe_test import StripeTestConfig
from app.services.stripe_test_provider import StripeTestProvider

class ProviderErrorsTests(unittest.TestCase):
    def provider(self, handler):
        return StripeTestProvider(StripeTestConfig('sk_test_fixture','whsec_fixture','http://localhost:5173'), httpx.MockTransport(handler))

    def test_http_failures_distinguish_cause_without_exposing_provider_body(self):
        for status, text in [(401,'credentials'),(403,'permissions'),(404,'not found'),(429,'rate limiting'),(400,'request log'),(500,'temporarily unavailable')]:
            with self.subTest(status=status):
                provider=self.provider(lambda request: httpx.Response(status,json={'error':{'message':'secret private provider detail'}}))
                with self.assertRaises(HTTPException) as caught:
                    provider.request('GET','prices/price_fixture')
                self.assertEqual(caught.exception.status_code,502)
                self.assertIn(text,caught.exception.detail)
                self.assertNotIn('secret',caught.exception.detail)
                self.assertNotIn('fixture',caught.exception.detail)

    def test_connectivity_failure_preserves_safe_retry(self):
        def failed(request):
            raise httpx.ConnectError('sensitive transport detail',request=request)
        with self.assertRaises(HTTPException) as caught:
            self.provider(failed).request('GET','prices/price_fixture')
        self.assertIn('same purchase',caught.exception.detail)
        self.assertNotIn('sensitive',caught.exception.detail)

    def test_invalid_json_and_live_responses_fail_closed(self):
        for response in [httpx.Response(200,text='not json'),httpx.Response(200,json={'livemode':True})]:
            with self.assertRaises(HTTPException) as caught:
                self.provider(lambda request:response).request('GET','prices/price_fixture')
            self.assertIn('verification was stopped',caught.exception.detail)
