"""Approved catalogue and activation gates; isolated SQLite, no payment/provider calls."""
import unittest
from app.services.user_subscription_catalogue import catalogue
import test_users

class UserSubscriptionCatalogueTests(unittest.TestCase):
    setUp = test_users.ProfileTests.setUp
    tearDown = test_users.ProfileTests.tearDown

    def test_approved_catalogue_and_no_grants(self):
        result=self.client.get('/user/subscription/plans',headers=self.headers)
        self.assertEqual(result.status_code,200,result.text)
        body=result.json()
        self.assertEqual([(p['code'],p['name'],p['currency'],p['price'],p['credits']) for p in body['plans']],
            [('free','Free','LKR',0,10),('starter','Starter','LKR',490,40),('pro','Pro','LKR',990,100)])
        self.assertFalse(body['monthly_credits_active'])
        self.assertEqual(body['generation_policy'],'one_time_free_request')
        self.assertTrue(all(not p['activation_available'] for p in body['plans']))
        self.assertEqual(body,catalogue())
        for code in ('free','starter','pro'):
            result=self.client.post(f'/user/subscription/{code}',headers=self.headers,json={'paid':True})
            self.assertEqual(result.status_code,404)
        self.assertEqual(self.client.post('/user/subscription/plans',headers=self.headers).status_code,405)

    def test_catalogue_requires_authenticated_normal_user(self):
        self.assertEqual(self.client.get('/user/subscription/plans').status_code,401)
        for identity in ('2','3'):
            self.decode.return_value=identity
            self.assertEqual(self.client.get('/user/subscription/plans',headers=self.headers).status_code,403)
