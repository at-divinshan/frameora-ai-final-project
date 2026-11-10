"""Complete revision path with SQLite, temporary images and mocked generation."""
import unittest
from unittest.mock import patch
from uuid import uuid4
from app.models.image_feedback import ImageFeedback
from app.models.share_link import ShareLink
from app.services import owner_entitlement_service as entitlements
import test_owner_credits as fixture

class FeedbackRevisionTests(unittest.TestCase):
    auth = fixture.OwnerCreditTests.auth
    activate = fixture.OwnerCreditTests.activate
    generate_for_project = fixture.OwnerCreditTests.generate_for_project
    eligibility = fixture.OwnerCreditTests.eligibility
    ledger = fixture.OwnerCreditTests.ledger
    setUp = fixture.OwnerCreditTests.setUp
    tearDown = fixture.OwnerCreditTests.tearDown

    def test_comment_revision_credit_replay_link_and_reshare(self):
        ShareLink.__table__.create(self.engine)
        ImageFeedback.__table__.create(self.engine)
        self.assertEqual(self.activate('trial').status_code,200)
        with patch.object(entitlements,'BATCH_COST',2), patch('app.services.generation_planning.BATCH_SIZE',2):
            self.mock.return_value=fixture.OWNER_IMAGES[:2]
            original=self.generate_for_project(1,key='feedback-original-0001')
            self.assertEqual(original.status_code,201,original.text)
            original=original.json()
            def share(generation):
                response=self.client.post('/owner/projects/1/share-links',headers=self.headers,json={'generation_id':generation['id']})
                self.assertEqual(response.status_code,201,response.text)
                return response.json()['token']
            token=share(original)
            before=self.eligibility().json()['remaining_credits']
            feedback=self.client.post(f"/sharing/{token}/images/{original['images'][0]['id']}/comments",headers=self.auth(1),json={'request_key':str(uuid4()),'comment':'Make the lighting brighter'})
            self.assertEqual(feedback.status_code,201,feedback.text)
            self.assertEqual(self.mock.call_count,1)
            self.assertEqual(self.eligibility().json()['remaining_credits'],before)
            revised=self.generate_for_project(1,key='feedback-revised-0001',data={'description':feedback.json()['comment']})
            self.assertEqual(revised.status_code,201,revised.text)
            revised=revised.json()
            self.assertEqual(self.eligibility().json()['remaining_credits'],before-2)
            self.assertIn('Make the lighting brighter',str(self.mock.call_args))
            replay=self.generate_for_project(1,key='feedback-revised-0001',data={'description':feedback.json()['comment']})
            self.assertTrue(replay.json()['replayed'])
            self.assertEqual(self.mock.call_count,2)
            self.assertEqual(self.eligibility().json()['remaining_credits'],before-2)
            linked=self.client.patch(f"/owner/projects/1/feedback/{feedback.json()['id']}",headers=self.headers,json={'revised_asset_id':revised['images'][0]['id'],'status':'resolved'})
            self.assertEqual(linked.status_code,200,linked.text)
            new_token=share(revised)
            gallery=self.client.get(f'/sharing/{new_token}',headers=self.auth(1))
            self.assertEqual([im['id'] for im in gallery.json()['images']],[im['id'] for im in revised['images']])
            self.assertEqual(self.client.get(f"/sharing/{token}/images/{revised['images'][0]['id']}",headers=self.auth(1)).status_code,404)
            self.assertEqual(self.client.get(f"/owner/ai/images/{original['images'][0]['id']}",headers=self.headers).status_code,200)
