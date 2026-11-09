"""Opt-in real InnoDB tests; exclusively a marked /tmp private-socket MySQL instance.

Never reads production DB credentials. Initialization/startup is documented in the
Phase 1 report. With no explicit test socket these tests skip, never fall back.
"""
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from dataclasses import replace
import secrets
import tempfile
import threading
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, select, text, func
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.database.connection import engine as production_engine
from app.models.user import User
from app.models.profile import UserProfile
from app.models.photography_plan import PhotographyPlan
from app.models.ai_generation import AIGeneration
from app.models.ai_result import AIResult
from app.models.media_asset import MediaAsset
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.models.credit_transaction import CreditTransaction
from app.models.customer_project import CustomerProject
from app.schemas.project import ProjectCreate
from app.services import subscription_service, owner_generation_service as service, project_service
from app.services import ai_image_storage as storage, pollinations_service as provider
from test_ai import IMAGES, png

OWNER_IMAGES = [*IMAGES, *(png(color) for color in ('purple', 'orange', 'cyan', 'magenta'))]


@unittest.skipUnless(os.environ.get('FRAMEORA_TEST_MYSQL_SOCKET'), 'No explicit disposable MySQL socket')
class MySQLCreditConcurrencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        socket=Path(os.environ['FRAMEORA_TEST_MYSQL_SOCKET']).resolve()
        root=socket.parent
        if root.parent != Path('/tmp') or not root.name.startswith('frameora-owner-credit-') or not (root/'isolated-test-marker').is_file():
            raise RuntimeError('Refusing any unmarked/non-temporary MySQL instance')
        cls.guard=patch.object(production_engine,'connect',side_effect=AssertionError('Live DB forbidden'))
        cls.guard.start()
        cls.addClassCleanup(cls.guard.stop)
        bootstrap=create_engine(URL.create('mysql+pymysql',username='root',query={'unix_socket':str(socket)}))
        with bootstrap.connect() as db:
            actual=Path(db.execute(text('SELECT @@datadir')).scalar()).resolve()
            if actual != root/'data': raise RuntimeError('Refusing unexpected MySQL data directory')
            name='frameora_owner_credit_test_'+secrets.token_hex(6)
            db.execute(text(f'CREATE DATABASE `{name}`'))  # Only this verified disposable instance.
        bootstrap.dispose()
        cls.engine=create_engine(URL.create('mysql+pymysql',username='root',database=name,query={'unix_socket':str(socket)}),pool_size=5)
        cls.addClassCleanup(cls.engine.dispose)
        for model in (User,UserProfile,PhotographyPlan,AIGeneration,SubscriptionPlan,Subscription,CreditTransaction,AIResult,MediaAsset,CustomerProject):
            model.__table__.create(cls.engine)
        with Session(cls.engine) as db:
            db.add_all([
                SubscriptionPlan(id=1,name='Free Basic',user_role='owner',monthly_credits=10,price=0,is_active=True,max_projects=2,max_share_links=3,currency='LKR',code='basic'),
                SubscriptionPlan(id=2,name='Free Trial',user_role='owner',monthly_credits=100,price=0,is_active=True,max_projects=10,max_share_links=20,trial_days=14,currency='LKR',code='trial'),
                SubscriptionPlan(id=3,name='Paid Pro',user_role='owner',monthly_credits=500,price=1500,is_active=True,max_projects=50,max_share_links=100,currency='LKR',code='pro')])
            db.commit()

    def setUp(self):
        self.now=datetime(2026,1,15,12)
        self.temp=tempfile.TemporaryDirectory(prefix='frameora-owner-integration-images-')
        self.addCleanup(self.temp.cleanup)
        for module,changes in ((storage,{'ai_image_dir':self.temp.name}),(provider,{'pollinations_enabled':True,'pollinations_api_key':'test-only'})):
            p=patch.object(module,'settings',replace(module.settings,**changes));p.start();self.addCleanup(p.stop)
        p=patch.object(subscription_service,'clock',side_effect=lambda:self.now);p.start();self.addCleanup(p.stop)
        p=patch.object(provider,'generate_images',return_value=OWNER_IMAGES);self.mock=p.start();self.addCleanup(p.stop)
        with Session(self.engine,expire_on_commit=False) as db:
            user=User(name='Disposable Owner',email=secrets.token_hex(8)+'@example.invalid',role='owner')
            db.add(user);db.flush();self.uid=user.id
            db.add(UserProfile(user_id=user.id,onboarding_status='completed',studio_name='Studio',studio_phone='+94771234567',studio_address='Test',studio_city='Jaffna'))
            plan=PhotographyPlan(user_id=user.id,photography_type='Portrait',people_count=1,environment='Outdoor')
            db.add(plan);db.flush();self.pid=plan.id;db.commit()
            subscription_service.snapshot(db,user,'basic',secrets.token_hex(16))

    def run_request(self,key):
        with Session(self.engine,expire_on_commit=False,autoflush=False) as db:
            try:
                return service.generate(db,db.get(User,self.uid),plan_id=self.pid,description='',reference=None,idempotency_key=key)
            except HTTPException as e:
                return e.status_code

    def test_parallel_batches_never_overspend(self):
        start=threading.Barrier(3)
        provider_barrier=threading.Barrier(1)
        def provider_call(*args,**kwargs):
            provider_barrier.wait(timeout=15)
            return OWNER_IMAGES
        self.mock.side_effect=provider_call
        def run(index):
            start.wait(timeout=15)
            return self.run_request(f'concurrent-request-{index}')
        with ThreadPoolExecutor(max_workers=3) as pool:
            results=list(pool.map(run,range(3)))
        self.assertEqual(sum(isinstance(r,dict) and r['status']=='completed' for r in results),1,results)
        self.assertEqual(results.count(402),2,results)
        self.assertEqual(self.mock.call_count,1)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.sum(CreditTransaction.credits_change)).where(CreditTransaction.user_id==self.uid)),2)
            self.assertEqual(db.scalar(select(func.count()).select_from(MediaAsset).where(MediaAsset.user_id==self.uid)),8)

    def test_concurrent_project_creates_cannot_bypass_basic_limit(self):
        start=threading.Barrier(5)
        def run(index):
            start.wait(timeout=15)
            with Session(self.engine,expire_on_commit=False,autoflush=False) as db:
                try:
                    return project_service.create_project(
                        db,db.get(User,self.uid),ProjectCreate(customer_name=f'Concurrent {index}')
                    )
                except HTTPException as error:
                    return error.status_code
        with ThreadPoolExecutor(max_workers=5) as pool:
            results=list(pool.map(run,range(5)))
        self.assertEqual(sum(not isinstance(result,int) for result in results),2,results)
        self.assertEqual(results.count(409),3,results)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CustomerProject).where(
                CustomerProject.studio_owner_id==self.uid,CustomerProject.deleted_at.is_(None))),2)

    def test_parallel_same_key_runs_provider_once(self):
        started=threading.Event();release=threading.Event()
        def provider_call(*args,**kwargs):
            started.set()
            if not release.wait(timeout=15): raise RuntimeError('test timeout')
            return OWNER_IMAGES
        self.mock.side_effect=provider_call
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(self.run_request,'same-key-concurrently')
            self.assertTrue(started.wait(timeout=15))
            try:
                second=pool.submit(self.run_request,'same-key-concurrently').result(timeout=15)
                self.assertEqual(second,409)
            finally:release.set()
            result=first.result(timeout=15)
        self.assertEqual(result['status'],'completed',result)
        self.assertEqual(len(result['images']),8)
        self.assertEqual(self.run_request('same-key-concurrently')['id'],result['id'])
        self.mock.assert_called_once()

    def test_concurrent_expiry_creates_one_basic_at_original_anchor(self):
        with Session(self.engine,expire_on_commit=False) as db:
            subscription_service.snapshot(db,db.get(User,self.uid),'trial','trial-activation-key')
            trial=db.scalar(select(Subscription).where(Subscription.user_id==self.uid,Subscription.status=='active'))
            expiry=trial.end_date
        self.now=expiry
        start=threading.Barrier(2)
        def run(index):
            start.wait(timeout=15)
            return self.run_request(f'expiry-request-{index}')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(run,range(2)))
        self.assertTrue(all(isinstance(r,dict) and r['status']=='completed' for r in results),results)
        with Session(self.engine) as db:
            active=list(db.scalars(select(Subscription).where(Subscription.user_id==self.uid,Subscription.status=='active')))
            self.assertEqual(len(active),1)
            self.assertEqual(active[0].plan_kind,'basic')
            self.assertEqual(active[0].start_date,expiry)
            grants=list(db.scalars(select(CreditTransaction).where(CreditTransaction.user_id==self.uid,CreditTransaction.subscription_id==active[0].id,CreditTransaction.transaction_type=='grant')))
            self.assertEqual(len(grants),1)
            self.assertEqual(grants[0].credits_change,10)

    def test_concurrent_recovery_refunds_only_once(self):
        with Session(self.engine,expire_on_commit=False,autoflush=False) as db:
            gid,_,_=service._reserve(db,db.get(User,self.uid),self.pid,'',None,'crash-before-provider')
        self.now+=service.RECOVERY_AFTER
        start=threading.Barrier(2)
        def run(_):
            with Session(self.engine,expire_on_commit=False,autoflush=False) as db:
                user=db.get(User,self.uid)
                start.wait(timeout=15)
                return service.recover(db,user,gid)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(run,range(2)))
        self.assertTrue(all(r['status']=='failed' for r in results))
        self.mock.assert_not_called()
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditTransaction).where(
                CreditTransaction.user_id==self.uid,CreditTransaction.transaction_type=='refund')),1)
            self.assertEqual(db.scalar(select(func.sum(CreditTransaction.credits_change)).where(
                CreditTransaction.user_id==self.uid)),10)

    def test_composite_ledger_foreign_key_rejects_wrong_owner(self):
        from hashlib import sha256
        from sqlalchemy.exc import IntegrityError
        with Session(self.engine,expire_on_commit=False) as db:
            other=User(name='Disposable Other',email=secrets.token_hex(8)+'@example.invalid',role='owner')
            db.add(other);db.commit()
            subscription=db.scalar(select(Subscription).where(Subscription.user_id==self.uid,Subscription.status=='active'))
            digest=sha256(b'test-cross-owner-ledger').digest()
            db.add(CreditTransaction(user_id=other.id,subscription_id=subscription.id,
                credits_change=-4,transaction_type='spend',created_at=self.now,
                period_start=self.now,period_end=self.now+timedelta(days=30),
                operation_key=digest,request_hash=digest))
            with self.assertRaises(IntegrityError):
                db.flush()
            db.rollback()
