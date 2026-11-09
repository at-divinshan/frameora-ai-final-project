"""Owner batch tests: disposable SQLite, mocked providers, live database guard."""
from datetime import datetime, timedelta
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import test_owner_subscriptions
from test_ai import IMAGES, png
from app.models.ai_generation import AIGeneration
from app.models.ai_result import AIResult
from app.models.customer_project import CustomerProject
from app.models.media_asset import MediaAsset
from app.models.photography_plan import PhotographyPlan
from app.models.credit_transaction import CreditTransaction
from app.models.subscription import Subscription
from app.models.user import User
from app.services import owner_generation_service as service, owner_entitlement_service as entitlements
from app.services import pollinations_service as provider, ai_image_storage as storage

OWNER_IMAGES = [*IMAGES, *(png(color) for color in (
    'purple', 'orange', 'cyan', 'magenta',
))]


class OwnerCreditTests(unittest.TestCase):
    auth = test_owner_subscriptions.OwnerSubscriptionTests.auth
    activate = test_owner_subscriptions.OwnerSubscriptionTests.activate

    def setUp(self):
        for target in ("app.services.owner_entitlement_service.BATCH_COST", "app.services.generation_planning.BATCH_SIZE"):
            patcher = patch(target, 8)
            patcher.start(); self.addCleanup(patcher.stop)
        test_owner_subscriptions.OwnerSubscriptionTests.setUp(self)
        CustomerProject.__table__.create(self.engine)
        PhotographyPlan.__table__.create(self.engine)
        AIResult.__table__.create(self.engine)
        MediaAsset.__table__.create(self.engine)
        with Session(self.engine) as db:
            db.add(User(id=4, role='owner', name='Other Owner', email='other-owner@example.invalid'))
            db.add_all([
                CustomerProject(id=1, studio_owner_id=2, customer_name='Owner Customer',
                    created_at=datetime(2026, 1, 1)),
                CustomerProject(id=2, studio_owner_id=4, customer_name='Other Customer',
                    created_at=datetime(2026, 1, 1)),
                PhotographyPlan(id=1, user_id=2, photography_type='Portrait', people_count=1,
                environment='Outdoor', location='Garden', preferences={'clothing_style':'Formal',
                    'extra_instructions':'Show accessories', 'camera_angle_preference':'Low Angle'}),
                PhotographyPlan(id=2, user_id=4, project_id=2, photography_type='Other',
                    people_count=1, environment='Indoor'),
                PhotographyPlan(id=3, user_id=2, project_id=1, photography_type='Portrait',
                    people_count=1, environment='Outdoor', location='Project Garden'),
            ])
            db.commit()
        self.temp = tempfile.TemporaryDirectory(prefix='frameora-owner-credit-files-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for module, changes in ((storage, {'ai_image_dir': str(self.root)}),
                                (provider, {'pollinations_enabled':True, 'pollinations_api_key':'test-only'})):
            patcher = patch.object(module, 'settings', replace(module.settings, **changes))
            patcher.start(); self.addCleanup(patcher.stop)
        self.mock = patch.object(provider, 'generate_images', return_value=OWNER_IMAGES).start()
        self.addCleanup(patch.stopall)

    def tearDown(self):
        test_owner_subscriptions.OwnerSubscriptionTests.tearDown(self)

    def generate(self, key='generation-key-0001', **overrides):
        data = {'plan_id': '1', 'idempotency_key': key, **overrides.pop('data', {})}
        return self.client.post('/owner/ai/generations', headers=overrides.pop('headers', self.headers), data=data, **overrides)

    def generate_for_project(self, project_id, plan_id=3, key='project-generation-key-0001', **overrides):
        data = {'plan_id': str(plan_id), 'idempotency_key': key, **overrides.pop('data', {})}
        return self.client.post(f'/owner/projects/{project_id}/ai/generations',
            headers=overrides.pop('headers', self.headers), data=data, **overrides)

    def eligibility(self):
        return self.client.get('/owner/ai/eligibility', headers=self.headers)

    def ledger(self):
        with Session(self.engine) as db:
            return [(r.transaction_type, r.credits_change, r.subscription_id, r.period_start, r.period_end)
                    for r in db.scalars(select(CreditTransaction).order_by(CreditTransaction.id))]

    def test_two_image_mode_replay_refund_and_historical_eight_gallery(self):
        self.assertEqual(self.activate('trial').status_code, 200)
        original = self.generate('original-eight-batch').json()
        with patch.object(entitlements, 'BATCH_COST', 2), patch('app.services.generation_planning.BATCH_SIZE', 2):
            self.mock.return_value = OWNER_IMAGES[:2]
            result = self.generate('temporary-two-batch')
            self.assertEqual(result.status_code, 201, result.text)
            body = result.json()
            self.assertEqual((len(body['images']), body['charged_credits']), (2, 2))
            calls = self.mock.call_count
            self.assertTrue(self.generate('temporary-two-batch').json()['replayed'])
            self.assertEqual(self.mock.call_count, calls)
            historical = self.client.get(f"/owner/ai/generations/{original['id']}", headers=self.headers)
            self.assertEqual(len(historical.json()['images']), 8)
            self.mock.side_effect = RuntimeError('mock provider failure')
            self.assertEqual(self.generate('temporary-failure').status_code, 503)
            self.assertEqual(self.ledger()[-1][:2], ('refund', 2))
            self.generate('temporary-failure')
            self.assertEqual(sum(row[0] == 'refund' for row in self.ledger()), 1)
        restored = self.client.get(f"/owner/ai/generations/{body['id']}", headers=self.headers)
        self.assertEqual(len(restored.json()['images']), 2)

    def test_basic_owner_batch_charges_eight_and_insufficient_credits_block_next(self):
        self.assertEqual(self.activate('basic').status_code, 200)
        result = self.generate('generation-key-0000')
        self.assertEqual(result.status_code, 201, result.text)
        body = result.json()
        self.assertEqual(body['remaining_credits'], 2)
        self.assertEqual(body['charged_credits'], 8)
        self.assertEqual(len(body['images']), 8)
        self.assertEqual(self.mock.call_args.kwargs['generation_id'], body['id'])
        for image in body['images']:
            self.assertEqual(len(image['guidance']['camera_setup']['steps']), 7)
            self.assertEqual(
                self.client.get(image['url'], headers=self.headers).content,
                OWNER_IMAGES[body['images'].index(image)],
            )
        self.assertEqual(self.generate('generation-third-001').status_code, 402)
        self.assertEqual(self.mock.call_count, 1)
        self.assertEqual(self.eligibility().json()['remaining_credits'], 2)
        self.assertEqual([x[:2] for x in self.ledger()], [('grant',10),('spend',-8)])
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(AIResult)),8)

    def test_incomplete_duplicate_provider_and_storage_failure_refund_once(self):
        self.activate('basic')
        failures = ([OWNER_IMAGES[0]], OWNER_IMAGES[:2], OWNER_IMAGES[:7],
                    [OWNER_IMAGES[0]]*8, HTTPException(502,'private-upstream'))
        for index, value in enumerate(failures):
            self.mock.side_effect = value if isinstance(value, Exception) else None
            self.mock.return_value = value
            key=f'failed-generation-{index:04d}'
            result=self.generate(key)
            self.assertEqual(result.status_code,503,result.text)
            self.assertNotIn('private-upstream',result.text)
            self.assertEqual(self.eligibility().json()['remaining_credits'],10)
            before=self.mock.call_count
            replay=self.generate(key)
            self.assertEqual(replay.status_code,200,replay.text)
            self.assertEqual(replay.json()['status'],'failed')
            self.assertEqual(replay.json()['images'],[])
            self.assertEqual(self.mock.call_count,before)
        self.mock.side_effect=None; self.mock.return_value=OWNER_IMAGES
        with patch.object(storage,'write_image',side_effect=OSError('private path')):
            self.assertEqual(self.generate('storage-failure-0001').status_code,503)
        self.assertEqual(self.eligibility().json()['remaining_credits'],10)
        self.assertEqual(len([r for r in self.ledger() if r[0]=='grant']),1)
        self.assertEqual(len([r for r in self.ledger() if r[0]=='refund']),6)

    def test_generation_stage_diagnostics_are_correlated_and_safe(self):
        self.activate('basic')
        private_error = 'private-storage-path-marker'
        with self.assertLogs(service.logger, level='INFO') as logs:
            with patch.object(storage, 'write_image', side_effect=OSError(private_error)):
                failed = self.generate('diagnostic-storage-key-001')
        self.assertEqual(failed.status_code, 503)
        self.assertNotIn(private_error, failed.text)
        with Session(self.engine) as db:
            failed_id = db.scalar(select(AIGeneration.id).order_by(AIGeneration.id.desc()))
        output = '\n'.join(logs.output)
        self.assertIn(f'generation_id={failed_id}', output)
        self.assertIn('stage=storage_error', output)
        self.assertIn('exception_category=OSError', output)
        self.assertIn('stage=credit_refund_completed', output)
        self.assertNotIn(private_error, output)

        with self.assertLogs(service.logger, level='INFO') as logs:
            succeeded = self.generate('diagnostic-settlement-key-001')
        self.assertEqual(succeeded.status_code, 201, succeeded.text)
        output = '\n'.join(logs.output)
        self.assertIn(f'generation_id={succeeded.json()["id"]}', output)
        self.assertIn('stage=credit_settlement_completed', output)

    def test_same_key_success_replays_and_changed_inputs_conflict(self):
        self.activate('basic')
        first=self.generate(files={'reference':('reference.png',IMAGES[0],'image/png')})
        self.assertEqual(first.status_code,201,first.text)
        with Session(self.engine) as db:
            db.get(PhotographyPlan,1).preferences={'pose_preference':'Formal'};db.commit()
        second=self.generate(files={'reference':('reference.png',IMAGES[0],'image/png')})
        self.assertEqual(second.status_code,200,second.text)
        self.assertEqual(second.json()['images'],first.json()['images'])
        self.assertEqual(second.json()['remaining_credits'],2)
        self.assertEqual(self.generate().status_code,409)  # Different reference fingerprint.
        self.assertEqual(self.generate(data={'description':'changed'}).status_code,409)
        self.mock.assert_called_once()
        self.assertIn('Garden',self.mock.call_args.args[0])
        self.assertIn('Formal',self.mock.call_args.args[0])
        self.assertIsNotNone(self.mock.call_args.args[1])

    def test_trial_total_expiry_and_monthly_no_carryover(self):
        self.activate('trial')
        expiry=self.eligibility().json()['subscription_end']
        self.generate()
        self.now+=timedelta(days=10)
        self.assertEqual(self.eligibility().json()['remaining_credits'],92)
        self.assertEqual(len([r for r in self.ledger() if r[0]=='grant']),1)
        self.now=datetime.fromisoformat(expiry)
        read=self.eligibility().json()
        self.assertEqual(read['plan'],'basic'); self.assertTrue(read['previous_subscription_expired'])
        self.assertEqual(read['remaining_credits'],10)
        result=self.generate('after-expiry-000001')
        self.assertEqual(result.status_code,201,result.text)
        self.assertEqual(result.json()['remaining_credits'],2)
        with Session(self.engine) as db:
            active=db.scalar(select(Subscription).where(Subscription.status=='active'))
            self.assertEqual(active.start_date,self.now)
            self.assertEqual(active.plan_kind,'basic')
            self.assertEqual(len(list(db.scalars(select(Subscription)))),2)
        self.assertEqual(self.activate('trial','trial-not-again-001').status_code,409)
        self.now=datetime(2026,2,28,12)
        self.assertEqual(self.eligibility().json()['remaining_credits'],10)
        self.assertEqual(self.generate('new-month-00000001').json()['remaining_credits'],2)

    def test_roles_ownership_forged_fields_and_pro_disabled(self):
        self.activate('basic')
        for headers,status in (({},401),(self.auth(1),403),(self.auth(3),403),(self.auth(4),403)):
            self.assertEqual(self.generate(headers=headers).status_code,status)
        self.assertEqual(self.generate(data={'plan_id':'2'}).status_code,403)
        for name in ('subscription_id','credits','user_id','balance'):
            self.assertEqual(self.generate(data={name:'100'}).status_code,422)
        self.assertEqual(self.generate(data={'idempotency_key':'short'}).status_code,422)
        self.mock.assert_not_called()
        result=self.generate().json()
        self.assertEqual(self.client.get(f"/owner/ai/generations/{result['id']}",headers=self.auth(4)).status_code,403)
        self.assertEqual(self.client.get(result['images'][0]['url'],headers=self.auth(4)).status_code,404)
        self.assertEqual(self.client.post('/ai/generations',headers=self.headers,data={'plan_id':'1'}).status_code,403)
        self.assertEqual(self.client.post('/owner/subscription/pro',headers=self.headers,json={'idempotency_key':'pro-disabled-00001'}).status_code,404)
        with Session(self.engine) as db:
            sub=db.scalar(select(Subscription));sub.plan_kind='pro';sub.plan_id=3;sub.end_date=self.now+timedelta(days=30);db.commit()
        self.assertEqual(self.eligibility().json()['reason'],'paid_activation_disabled')
        self.assertEqual(self.generate('pro-disabled-generation').status_code,409)
        self.assertEqual(self.mock.call_count,1)

    def test_project_generation_and_gallery_preserve_project_plan_result_chain(self):
        self.activate('basic')
        generated = self.generate_for_project(1)
        self.assertEqual(generated.status_code, 201, generated.text)
        result = generated.json()
        self.assertEqual(result['plan_id'], 3)
        self.assertEqual(len(result['images']), 8)
        gallery = self.client.get('/owner/projects/1/ai/generations', headers=self.headers)
        self.assertEqual(gallery.status_code, 200, gallery.text)
        self.assertEqual([item['id'] for item in gallery.json()], [result['id']])
        self.assertEqual(gallery.json()[0]['plan_id'], 3)
        for image in gallery.json()[0]['images']:
            self.assertEqual(self.client.get(image['url'], headers=self.headers).content,
                OWNER_IMAGES[gallery.json()[0]['images'].index(image)])
        with Session(self.engine) as db:
            generation = db.get(AIGeneration, result['id'])
            self.assertEqual(generation.plan_id, 3)
            self.assertEqual(db.get(PhotographyPlan, generation.plan_id).project_id, 1)
            assets = list(db.scalars(select(MediaAsset).where(MediaAsset.generation_id == generation.id)))
            self.assertEqual(len(assets), 8)
            self.assertTrue(all(asset.plan_id == 3 and asset.user_id == 2 for asset in assets))

    def test_owner_preferences_build_eight_distinct_project_linked_shots_and_replay_safely(self):
        self.activate('trial')
        data = {
            'background_mode': 'different',
            'pose_mode': 'high',
            'camera_angle_mode': 'cinematic',
            'outfit_mode': 'different',
            'dress_colors': 'navy, ivory, and burgundy',
            'outfit_details': 'Keep the clothing formal and modest',
            'additional_instructions': 'Use soft evening light and preserve the same person.',
        }
        response = self.generate_for_project(
            1, key='owner-eight-preferences-001', data=data,
            files={'reference_photo': ('reference.png', IMAGES[0], 'image/png')},
        )
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(len(body['images']), 8)
        self.assertEqual(body['charged_credits'], 8)
        self.assertEqual(body['remaining_credits'], 92)
        self.assertNotIn('prompt', body)
        self.assertNotIn('internal_prompt', body)
        prompt, reference, shots = self.mock.call_args.args[0], self.mock.call_args.args[1], self.mock.call_args.kwargs['shots']
        self.assertIsNotNone(reference)
        self.assertEqual(len(shots), 8)
        self.assertEqual(len({shot['pose_name'] for shot in shots}), 8)
        self.assertEqual(len({shot['camera_angle'] for shot in shots}), 8)
        for phrase, shot in zip((
            "sandy ocean beach", "urban plaza", "mountain overlook",
            "historic cobblestone street", "lakeside wooden pier", "desert dune",
            "rooftop terrace", "rural meadow",
        ), shots):
            self.assertIn(phrase, shot['instructions'])
        self.assertTrue(all('distinct coordinated outfit' in shot['instructions'] for shot in shots))
        for value in ('Project Garden', 'navy, ivory, and burgundy',
                      'Keep the clothing formal and modest', 'same person'):
            self.assertIn(value, prompt)
        repeated = self.generate_for_project(
            1, key='owner-eight-preferences-001', data=data,
            files={'reference_photo': ('reference.png', IMAGES[0], 'image/png')},
        )
        self.assertEqual(repeated.status_code, 200, repeated.text)
        self.assertEqual(repeated.json()['id'], body['id'])
        self.assertEqual(self.mock.call_count, 1)
        changed = self.generate_for_project(
            1, key='owner-eight-preferences-001',
            data={**data, 'dress_colors': 'green'},
            files={'reference_photo': ('reference.png', IMAGES[0], 'image/png')},
        )
        self.assertEqual(changed.status_code, 409, changed.text)
        self.assertEqual(self.mock.call_count, 1)

    def test_custom_preferences_require_matching_owner_instructions(self):
        self.activate('trial')
        invalid_preferences = (
            {'background_mode': 'custom'},
            {'pose_mode': 'custom'},
            {'camera_angle_mode': 'custom'},
            {'outfit_mode': 'custom'},
        )
        for index, preferences in enumerate(invalid_preferences):
            response = self.generate(
                f'owner-invalid-custom-{index:04d}',
                data={'plan_id': '1', **preferences},
            )
            self.assertEqual(response.status_code, 422, response.text)
        self.mock.assert_not_called()
        self.assertFalse(any(row[0] == 'spend' for row in self.ledger()))

    def test_project_generation_rejects_cross_owner_project_and_plan_ids(self):
        self.activate('basic')
        for project_id, plan_id in ((2, 3), (1, 2), (9876, 3)):
            response = self.generate_for_project(project_id, plan_id=plan_id,
                key=f'cross-project-generation-{project_id:05d}')
            self.assertEqual(response.status_code, 404, response.text)
        self.mock.assert_not_called()
        gallery = self.client.get('/owner/projects/2/ai/generations', headers=self.headers)
        self.assertEqual(gallery.status_code, 404)

    def test_read_only_project_allows_existing_images_but_blocks_new_generation(self):
        trial = self.activate('trial')
        with Session(self.engine) as db:
            db.add_all([
                CustomerProject(id=3, studio_owner_id=2, customer_name='Editable Customer',
                    created_at=datetime(2026, 1, 2)),
                CustomerProject(id=4, studio_owner_id=2, customer_name='Read-only Customer',
                    created_at=datetime(2026, 1, 3)),
            ])
            db.get(PhotographyPlan, 3).project_id = 4
            db.commit()
        generated = self.generate_for_project(4, key='read-only-project-first-key')
        self.assertEqual(generated.status_code, 201, generated.text)
        self.now = datetime.fromisoformat(trial.json()['period_end'])

        gallery = self.client.get('/owner/projects/4/ai/generations', headers=self.headers)
        self.assertEqual(gallery.status_code, 200, gallery.text)
        self.assertEqual(gallery.json()[0]['id'], generated.json()['id'])
        self.assertEqual(len(gallery.json()[0]['images']), 8)
        provider_calls = self.mock.call_count
        denied = self.generate_for_project(4, key='read-only-project-second-key')
        self.assertEqual(denied.status_code, 409, denied.text)
        self.assertEqual(self.mock.call_count, provider_calls)

    def test_interrupted_reservation_deadline_refund_and_late_worker_fence(self):
        self.activate('basic')
        with Session(self.engine,expire_on_commit=False) as db:
            gid,_,_=service._reserve(db,db.get(User,2),1,'',None,'interrupted-key-001')
        self.assertEqual(self.generate('interrupted-key-001').status_code,409)
        self.assertEqual(self.eligibility().json()['remaining_credits'],2)
        self.assertEqual(self.client.post(f'/owner/ai/generations/{gid}/recover',headers=self.headers).status_code,409)
        self.now+=service.RECOVERY_AFTER
        recovered=self.client.post(f'/owner/ai/generations/{gid}/recover',headers=self.headers)
        self.assertEqual(recovered.status_code,200,recovered.text)
        self.assertEqual(recovered.json()['remaining_credits'],10)
        self.assertEqual(recovered.json()['status'],'failed')
        self.client.post(f'/owner/ai/generations/{gid}/recover',headers=self.headers)
        self.assertEqual(self.generate('interrupted-key-001').json()['status'],'failed')
        self.mock.assert_not_called()
        self.assertEqual(len([r for r in self.ledger() if r[0]=='refund']),1)
        def late(*args,**kwargs):
            self.now+=service.RECOVERY_AFTER
            with Session(self.engine,expire_on_commit=False) as db:
                current=db.scalar(select(AIGeneration).where(AIGeneration.status==service.PENDING))
                service.recover(db,db.get(User,2),current.id)
            return OWNER_IMAGES
        self.mock.side_effect=late
        self.assertEqual(self.generate('late-worker-key-001').status_code,503)
        self.assertEqual(self.eligibility().json()['remaining_credits'],10)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(MediaAsset)),0)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_success_commit_ack_loss_never_refunds_or_regenerates(self):
        self.activate('basic')
        with Session(self.engine,expire_on_commit=False) as db:
            original=db.commit
            calls=0
            def commit():
                nonlocal calls
                calls+=1
                original()
                if calls==2: raise SQLAlchemyError('ack lost')
            with patch.object(db,'commit',side_effect=commit):
                with self.assertRaises(HTTPException) as error:
                    service.generate(db,db.get(User,2),plan_id=1,description='',reference=None,idempotency_key='commit-ack-loss-001')
                self.assertEqual(error.exception.status_code,503)
        replay=self.generate('commit-ack-loss-001')
        self.assertEqual(replay.status_code,200,replay.text)
        self.assertEqual(len(replay.json()['images']),8)
        self.assertEqual(replay.json()['remaining_credits'],2)
        self.assertEqual(len(list(self.root.iterdir())),8)
        self.assertFalse(any(r[0]=='refund' for r in self.ledger()))
        self.mock.assert_called_once()

    def test_database_flush_failure_rolls_back_partial_results_and_refunds(self):
        self.activate('basic')
        with Session(self.engine,expire_on_commit=False) as db:
            original=db.flush
            failed=False
            def flush(*args,**kwargs):
                nonlocal failed
                if not failed and any(isinstance(row, MediaAsset) for row in db.new):
                    failed=True
                    raise SQLAlchemyError('private DB failure')
                return original(*args,**kwargs)
            with patch.object(db,'flush',side_effect=flush):
                with self.assertRaises(HTTPException):
                    service.generate(db,db.get(User,2),plan_id=1,description='',reference=None,idempotency_key='flush-failure-00001')
        self.assertEqual(self.eligibility().json()['remaining_credits'],10)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(MediaAsset)),0)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_uncommitted_completion_is_recovered_without_repeating_provider(self):
        self.activate('basic')
        with Session(self.engine,expire_on_commit=False) as db:
            original=db.commit
            calls=0
            def commit():
                nonlocal calls
                calls+=1
                if calls==2: raise SQLAlchemyError('commit unavailable')
                original()
            with patch.object(db,'commit',side_effect=commit):
                with self.assertRaises(HTTPException):
                    service.generate(db,db.get(User,2),plan_id=1,description='',reference=None,idempotency_key='uncertain-commit-001')
        self.assertEqual(self.generate('uncertain-commit-001').status_code,409)
        self.now+=service.RECOVERY_AFTER
        recovered=self.generate('uncertain-commit-001')
        self.assertEqual(recovered.status_code,200,recovered.text)
        self.assertEqual(recovered.json()['status'],'failed')
        self.assertEqual(recovered.json()['remaining_credits'],10)
        self.mock.assert_called_once()
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(MediaAsset)),0)
        # Files are deliberately retained after an uncertain COMMIT, never served.
        self.assertEqual(len(list(self.root.iterdir())),8)

    def test_failure_refund_stays_in_original_period_after_trial_expires(self):
        self.activate('trial')
        expiry=datetime.fromisoformat(self.eligibility().json()['subscription_end'])
        self.now=expiry-timedelta(minutes=1)
        def fail(*args,**kwargs):
            self.now=expiry+timedelta(minutes=1)
            raise HTTPException(502,'timeout')
        self.mock.side_effect=fail
        self.assertEqual(self.generate().status_code,503)
        self.assertEqual(self.eligibility().json()['remaining_credits'],10)
        debit=next(r for r in self.ledger() if r[0]=='spend')
        refund=next(r for r in self.ledger() if r[0]=='refund')
        self.assertEqual(debit[2:],refund[2:])

    def test_role_change_during_provider_blocks_publication_but_refunds_original_owner(self):
        self.activate('basic')
        def changed_role(*args,**kwargs):
            with Session(self.engine) as db:
                db.get(User,2).role='user'
                db.commit()
            return OWNER_IMAGES
        self.mock.side_effect=changed_role
        self.assertEqual(self.generate().status_code,503)
        self.assertEqual(sum(row[1] for row in self.ledger()),10)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(MediaAsset)),0)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_no_locks_during_provider_and_saved_plan_routes(self):
        self.activate('basic')
        with Session(self.engine,expire_on_commit=False) as db:
            def provider_call(*args,**kwargs):
                self.assertFalse(db.in_transaction())
                return OWNER_IMAGES
            self.mock.side_effect=provider_call
            result=service.generate(db,db.get(User,2),plan_id=1,description='',reference=None,idempotency_key='unlocked-provider-01')
            self.assertEqual(len(result['images']),8)
        created=self.client.post('/owner/photography-plans',headers=self.headers,json={
            'photography_type':'Wedding','people_count':2,'environment':'Studio',
            'preferences':{'clothing_style':'Traditional','extra_instructions':'Soft light'}})
        self.assertEqual(created.status_code,201,created.text)
        plan_id=created.json()['id']
        self.assertEqual(self.client.get(f'/owner/photography-plans/{plan_id}',headers=self.auth(4)).status_code,404)
        edited=self.client.patch(f'/owner/photography-plans/{plan_id}',headers=self.headers,json={'location':'Jaffna'})
        self.assertEqual(edited.status_code,200)
        self.assertEqual(edited.json()['preferences']['clothing_style'],'Traditional')
