"""Mock-only Part 2 regression checks; no database or provider access."""
import hashlib
import hmac
import json
import unittest
from unittest.mock import Mock
from fastapi import HTTPException
from app.services.stripe_test_provider import verify_event
from app.services.payment_processing import process_event

class Part2Tests(unittest.TestCase):
    def test_thin_event_is_not_accepted_as_snapshot(self):
        event={'id':'evt_fixture','object':'v2.core.event','livemode':False,
               'type':'checkout.session.completed','data':{'object':{}}}
        raw=json.dumps(event).encode(); secret='whsec_fixture'
        digest=hmac.new(secret.encode(),b'1000.'+raw,hashlib.sha256).hexdigest()
        with self.assertRaises(HTTPException) as error:
            verify_event(raw,'t=1000,v1='+digest,secret,now=1000)
        self.assertEqual(error.exception.status_code,400)

    def test_invalid_checkout_metadata_never_reaches_repository(self):
        for metadata in [None,[], 'invalid', {'checkout_id':True}, {'checkout_id':'-1'}]:
            repo=Mock(); provider=Mock()
            event={'type':'checkout.session.completed','data':{'object':{'metadata':metadata}}}
            with self.assertRaises(HTTPException) as error:
                process_event(event,b'fixture',repo,provider)
            self.assertEqual(error.exception.status_code,409)
            repo.get_purchase.assert_not_called();repo.apply_event.assert_not_called()

    def test_removed_auth_routes_are_not_registered(self):
        from app.main import app
        for route in app.routes:
            path=getattr(route,'path','').lower()
            self.assertFalse(any(term in path for term in ('forgot-password','reset-password','change-email')))
