"""Paid generation safety tests: mocks only, no database or provider connections."""
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from fastapi import HTTPException
import app.main  # Register the application model graph without connecting.
from app.services import user_paid_generation as service
from app.models.ai_generation import AIGeneration

class PaidGenerationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1)
        self.user = NS(id=7, role='user')
        self.sub = NS(id=8,user_id=7,plan_kind='starter',end_date=self.now+timedelta(days=30))
        self.db = Mock()
        self.db.scalar.return_value = None
        self.db.scalars.return_value = [self.sub]
        self.db.add.side_effect = lambda row: setattr(row,'id',9) if isinstance(row,AIGeneration) else None
        self.args = dict(plan_id=1,prompt='test',reference=b'person',background_reference=b'scene',idempotency_key='a'*32)
        for target, value in [('lock_profile', self.user), ('clock', self.now)]:
            p=patch.object(service,target,return_value=value);p.start();self.addCleanup(p.stop)
        p=patch.object(service.paid_credit_service,'balance',return_value=(40,self.now,self.sub.end_date))
        self.balance=p.start();self.addCleanup(p.stop)

    def test_reserves_exactly_four_from_verified_period(self):
        result=service.reserve(self.db,self.user,**self.args)
        debit=self.db.add.call_args_list[-1].args[0]
        self.assertEqual((debit.credits_change,debit.subscription_id,result.generation_id),(-4,8,9))
        self.balance.assert_called_once_with(self.db,self.sub,self.now)
        self.db.commit.assert_called_once()

    def test_low_balance_and_unverified_produce_no_writes(self):
        for outcome in [3, None]:
            self.balance.return_value=(outcome,self.now,self.sub.end_date)
            self.balance.side_effect=HTTPException(503,'Unverified') if outcome is None else None
            with self.assertRaises(HTTPException): service.reserve(self.db,self.user,**self.args)
        self.db.add.assert_not_called()

    def test_free_fallback_does_not_grant_or_reset_allowance(self):
        self.db.scalars.return_value=[]
        self.assertIsNone(service.reserve(self.db,self.user,**self.args))
        self.balance.assert_not_called();self.db.add.assert_not_called()

    def test_owner_and_missing_key_rejected(self):
        for user,key in [(NS(id=7,role='owner'),'a'*32),(self.user,None)]:
            with self.assertRaises(HTTPException): service.reserve(self.db,user,**dict(self.args,idempotency_key=key))
        self.db.add.assert_not_called()

    def test_retry_completed_is_no_second_debit(self):
        service.reserve(self.db,self.user,**self.args)
        debit=self.db.add.call_args_list[-1].args[0]
        self.db.reset_mock();self.db.scalar.return_value=debit
        self.db.get.return_value=NS(id=9,user_id=7,status='completed')
        self.assertTrue(service.reserve(self.db,self.user,**self.args).replay)
        self.db.add.assert_not_called();self.db.commit.assert_not_called()
        with self.assertRaises(HTTPException):
            service.reserve(self.db,self.user,**dict(self.args,background_reference=b'changed'))

    def test_pending_replay_never_refunds(self):
        service.reserve(self.db,self.user,**self.args)
        debit=self.db.add.call_args_list[-1].args[0]
        self.db.reset_mock();self.db.scalar.return_value=debit
        self.db.get.return_value=NS(id=9,user_id=7,status=service.PENDING)
        with self.assertRaises(HTTPException): service.reserve(self.db,self.user,**self.args)
        self.db.add.assert_not_called()

    def test_failure_refunds_original_period_once(self):
        generation=NS(id=9,user_id=7,status=service.PENDING)
        self.db.get.return_value=generation
        debit=NS(credits_change=-4,subscription_id=8,period_start=self.now,period_end=self.sub.end_date,request_hash=b'x'*32)
        self.db.scalar.side_effect=[debit,None]
        service.fail(self.db,self.user,service.Reservation(9))
        refund=self.db.add.call_args.args[0]
        self.assertEqual((refund.credits_change,refund.subscription_id,refund.period_end),(4,8,self.sub.end_date))
        service.fail(self.db,self.user,service.Reservation(9))
        self.db.add.assert_called_once()

    def test_uncertain_reservation_commit_is_not_refunded(self):
        self.db.commit.side_effect=RuntimeError('ack lost')
        with self.assertRaises(RuntimeError): service.reserve(self.db,self.user,**self.args)
        self.assertEqual(len(self.db.add.call_args_list),2)

    def test_pro_settlement_checks_original_proof(self):
        self.db.scalar.return_value=NS(credits_change=-4,subscription_id=8)
        self.db.get.return_value=self.sub
        with patch.object(service.paid_credit_service,'proof') as proof:
            service.settle(self.db,self.user,service.Reservation(9))
            proof.assert_called_once_with(self.db,self.sub,self.now,settlement=True)

    def test_finalization_uncertainty_keeps_files_and_debit(self):
        from app.services import ai_service
        generation=NS(id=9,user_id=7,status=service.PENDING)
        db=Mock();db.get.return_value=generation
        db.commit.side_effect=RuntimeError('lost acknowledgement')
        with patch.object(ai_service.provider,'require_reference_support'), \
             patch.object(ai_service.provider,'require_configured'), \
             patch.object(ai_service.plan_repository,'find_for_user',return_value=NS()), \
             patch.object(ai_service,'build_image_prompt',return_value='prompt'), \
             patch.object(ai_service,'planned_shots',return_value=[{}]*4), \
             patch.object(service,'reserve',return_value=service.Reservation(9)), \
             patch.object(service,'settle'), patch.object(service,'fail') as refund, \
             patch.object(ai_service,'lock_profile'), \
             patch.object(ai_service.provider,'generate_images',return_value=[b'a',b'b',b'c',b'd']), \
             patch.object(ai_service.storage,'write_image',side_effect=['a','b','c','d']), \
             patch.object(ai_service.storage,'delete_image') as delete:
            with self.assertRaises(HTTPException) as error:
                ai_service.generate(db,self.user,plan_id=1,description='',reference=None,idempotency_key='a'*32)
            self.assertEqual(error.exception.status_code,503)
            refund.assert_not_called();delete.assert_not_called()

    def test_account_lock_precedes_balance_and_commit(self):
        calls=[]
        with patch.object(service,'lock_profile',side_effect=lambda *a: calls.append('lock') or self.user):
            self.balance.side_effect=lambda *a: calls.append('balance') or (40,self.now,self.sub.end_date)
            self.db.commit.side_effect=lambda: calls.append('commit')
            service.reserve(self.db,self.user,**self.args)
        self.assertEqual(calls,['lock','balance','commit'])

    def test_two_concurrent_requests_cannot_spend_last_four_twice(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Lock
        mutex=Lock()
        funds=[4]
        sessions=[]
        for _ in range(2):
            db=Mock();db.scalar.return_value=None;db.scalars.return_value=[self.sub]
            db.add.side_effect=lambda row: setattr(row,'id',9) if isinstance(row,AIGeneration) else None
            db.held=False
            def unlock(db=db):
                if db.held: db.held=False;mutex.release()
            def commit(db=db,unlock=unlock):
                funds[0]-=4;unlock()
            db.commit.side_effect=commit;db.rollback.side_effect=unlock
            sessions.append(db)
        def lock(db,user_id):
            mutex.acquire();db.held=True;return self.user
        def attempt(index):
            try:
                service.reserve(sessions[index],self.user,**dict(self.args,idempotency_key=str(index)*32))
                return 200
            except HTTPException as error: return error.status_code
        with patch.object(service,'lock_profile',side_effect=lock):
            self.balance.side_effect=lambda *a: (funds[0],self.now,self.sub.end_date)
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(attempt,[0,1]))
        self.assertEqual(sorted(results),[200,402]);self.assertEqual(funds[0],0)
