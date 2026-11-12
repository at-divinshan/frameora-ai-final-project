"""Deactivation fences for shared links and in-flight mocked generation."""
import unittest
from sqlalchemy.orm import Session
from sqlalchemy import select,func
from app.models.account_status import AccountStatus, AccountStatusAudit
from app.models.media_asset import MediaAsset
from app.models.free_generation_allowance import FreeGenerationAllowance
from app.models.user import User
from app.services import admin_users_service
from app.schemas.admin_users import StatusChange
import test_sharing as sharing
import test_ai as normal
import test_owner_credits as owner


def install_status(test):
    AccountStatus.__table__.create(test.engine)
    AccountStatusAudit.__table__.create(test.engine)

def deactivate(test,uid):
    with Session(test.engine) as db:
        admin_users_service.change(db,db.get(User,3),uid,StatusChange(is_active=False,expected_version=0))

class SharingStatusTests(unittest.TestCase):
    setUp=sharing.SharingTests.setUp
    tearDown=sharing.SharingTests.tearDown
    auth=sharing.SharingTests.auth
    activate=sharing.SharingTests.activate
    create=sharing.SharingTests.create
    _add_generations=sharing.SharingTests._add_generations
    _create_link=sharing.SharingTests._create_link
    def test_owner_deactivation_blocks_existing_customer_link(self):
        install_status(self)
        token=self._create_link().json()['token']
        self.assertEqual(self.client.get(f'/sharing/{token}',headers=self.auth(1)).status_code,200)
        deactivate(self,2)
        self.assertEqual(self.client.get(f'/sharing/{token}',headers=self.auth(1)).status_code,404)
        asset=self.asset_ids[self.generation_ids[0]][0]
        self.assertEqual(self.client.get(f'/sharing/{token}/images/{asset}',headers=self.auth(1)).status_code,404)

class NormalGenerationStatusTests(unittest.TestCase):
    setUp=normal.GenerationTests.setUp
    tearDown=normal.GenerationTests.tearDown
    auth=normal.GenerationTests.auth
    generate=normal.GenerationTests.generate
    def test_deactivation_during_provider_blocks_images_and_releases_allowance(self):
        install_status(self)
        def provider(*args,**kwargs):
            deactivate(self,1);return normal.IMAGES
        self.mock_provider.side_effect=provider
        result=self.generate()
        self.assertIn(result.status_code,(401,503))
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(MediaAsset)),0)
            self.assertEqual(db.get(FreeGenerationAllowance,1).state,'available')

class OwnerGenerationStatusTests(unittest.TestCase):
    setUp=owner.OwnerCreditTests.setUp
    tearDown=owner.OwnerCreditTests.tearDown
    auth=owner.OwnerCreditTests.auth
    activate=owner.OwnerCreditTests.activate
    generate=owner.OwnerCreditTests.generate
    ledger=owner.OwnerCreditTests.ledger
    def test_deactivation_during_provider_refunds_original_reservation(self):
        install_status(self);self.assertEqual(self.activate('basic').status_code,200)
        def provider(*args,**kwargs):
            deactivate(self,2);return owner.OWNER_IMAGES
        self.mock.side_effect=provider
        result=self.generate()
        self.assertEqual(result.status_code,503,result.text)
        self.assertEqual([row[:2] for row in self.ledger()],[('grant',10),('spend',-8),('refund',8)])
        with Session(self.engine) as db:self.assertEqual(db.scalar(select(func.count()).select_from(MediaAsset)),0)
