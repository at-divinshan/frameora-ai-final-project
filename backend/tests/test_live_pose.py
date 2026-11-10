"""All tests use disposable SQLite and mocked HTTP. No live provider or MySQL."""
import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta
from io import BytesIO
import json
from pathlib import Path
import tempfile
import time
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4

import httpx
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
import test_users
from app.main import app
from app.models.user import User
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.models.live_pose_session import LivePoseSession
from app.services import live_pose_service as service, live_pose_provider as provider
from app.database.connection import engine as production_engine

def scene_result(count=1):
    return dict(scene='Open garden', composition='Keep the horizon level.', camera_angle='Approximately eye level.',
        framing='Full body, space beside the group.', detected_people_count=count,
        suggestions=[dict(title='Garden portrait', instructions='Face the camera and follow your individual target.',
            people=[dict(person=i+1,pose_id=p,instructions='Follow the supported standing target.') for i in range(count)],
            spacing='none' if count==1 else 'comfortable',group_guidance=None) for p in provider.POSES[:3]] if 1<=count<=3 else [])

RESULT = scene_result()
NOW = datetime(2026, 11, 10, 12)

def jpeg(color='white'):
    out=BytesIO(); Image.new('RGB',(100,100),color).save(out,format='JPEG'); return out.getvalue()

class LivePoseTests(TestCase):
    def setUp(self):
        test_users.ProfileTests.setUp(self)
        for model in (SubscriptionPlan, Subscription, LivePoseSession):
            model.__table__.create(self.engine)
        self.provider=Mock(available=True)
        self.provider.analyze.return_value=RESULT
        app.dependency_overrides[provider.get_scene_provider]=lambda:self.provider
        self.clock=patch.object(service,'clock',return_value=NOW);self.clock.start()
        self.body={'session_id':str(uuid4()),'snapshot':base64.b64encode(jpeg()).decode()}
    def tearDown(self):
        self.clock.stop();test_users.ProfileTests.tearDown(self)
    def post(self,body=None):
        return self.client.post('/live-pose/analyze',headers=self.headers,json=body or self.body)
    def quota(self):
        return self.client.get('/live-pose/entitlements',headers=self.headers)
    def activate(self,role,code,start=NOW-timedelta(days=1),end=None):
        uid=2 if role=='owner' else 1
        self.decode.return_value=str(uid)
        with Session(self.engine) as db:
            db.query(Subscription).delete();db.query(SubscriptionPlan).delete()
            db.add(SubscriptionPlan(id=1,name=code,user_role=role,code=code,monthly_credits=0,price=0,is_active=True,currency='LKR'))
            db.flush()
            db.add(Subscription(user_id=uid,plan_id=1,start_date=start,end_date=end,status='active',plan_kind=code,activation_key=b'test'))
            db.commit()
    def test_camera_quota_reads_never_consume(self):
        for _ in range(3):
            r=self.quota();self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['remaining'],1)
        self.provider.analyze.assert_not_called()
        with Session(self.engine) as db:self.assertEqual(list(db.scalars(select(LivePoseSession))),[])
    def test_success_retry_and_exhaustion(self):
        first=self.post();self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(first.headers['cache-control'],'no-store')
        self.assertEqual(self.post().json(),first.json())
        self.assertEqual(self.quota().json()['remaining'],0)
        self.assertEqual(self.post({**self.body,'session_id':str(uuid4())}).status_code,429)
        self.provider.analyze.assert_called_once()
    def test_duplicate_key_different_snapshot_conflicts(self):
        self.assertEqual(self.post().status_code,200)
        self.assertEqual(self.post({**self.body,'snapshot':base64.b64encode(jpeg('black')).decode()}).status_code,409)
    def test_failure_does_not_charge_and_same_key_can_retry(self):
        self.provider.analyze.side_effect=HTTPException(502,'Mock provider failure')
        self.assertEqual(self.post().status_code,502)
        self.assertEqual(self.quota().json()['remaining'],1)
        self.provider.analyze.side_effect=None
        self.assertEqual(self.post().status_code,200)
    def test_invalid_provider_result_does_not_charge(self):
        invalid=scene_result();invalid['suggestions'][0]['people'][0]['pose_id']='invented'
        self.provider.analyze.return_value=invalid
        self.assertEqual(self.post().status_code,502)
        self.assertEqual(self.quota().json()['remaining'],1)
    def test_auth_and_admin(self):
        self.assertEqual(self.client.get('/live-pose/entitlements').status_code,401)
        self.decode.return_value='3'
        self.assertEqual(self.post().status_code,403)
        self.assertEqual(self.quota().status_code,403)
        self.provider.analyze.assert_not_called()
    def test_all_plan_limits(self):
        for role,limits in service.LIMITS.items():
            for code,limit in limits.items():
                if code=='free':continue
                self.activate(role,code,end=NOW+timedelta(days=13) if code=='trial' else None)
                r=self.quota();self.assertEqual(r.status_code,200,r.text)
                self.assertEqual(r.json()['limit'],limit)
    def test_owner_basic_monthly_reset(self):
        self.decode.return_value='2'
        for _ in range(5):self.assertEqual(self.post({**self.body,'session_id':str(uuid4())}).status_code,200)
        self.assertEqual(self.quota().json()['remaining'],0)
        self.clock.stop();self.clock=patch.object(service,'clock',return_value=datetime(2026,12,1));self.clock.start()
        self.assertEqual(self.quota().json()['remaining'],5)
    def test_trial_total_and_expiry(self):
        self.activate('owner','trial',start=NOW-timedelta(days=13),end=NOW+timedelta(days=1))
        for _ in range(20):self.assertEqual(self.post({**self.body,'session_id':str(uuid4())}).status_code,200)
        self.assertEqual(self.quota().json()['remaining'],0)
        self.clock.stop();self.clock=patch.object(service,'clock',return_value=NOW+timedelta(days=1));self.clock.start()
        self.assertEqual(self.quota().json()['plan'],'basic')
    def test_free_does_not_reset_next_month(self):
        self.post();self.clock.stop();self.clock=patch.object(service,'clock',return_value=datetime(2027,1,1));self.clock.start()
        self.assertEqual(self.quota().json()['remaining'],0)
    def test_missing_migration_fails_closed(self):
        LivePoseSession.__table__.drop(self.engine)
        self.assertEqual(self.post().status_code,503)
        self.provider.analyze.assert_not_called()
    def test_snapshot_validation_and_body_limit(self):
        for image in ('junk',base64.b64encode(b'not jpeg').decode()):
            self.assertEqual(self.post({**self.body,'snapshot':image}).status_code,422)
        self.assertEqual(self.client.post('/live-pose/analyze',headers=self.headers,content=b'x'*1500001).status_code,413)
        self.provider.analyze.assert_not_called()
    def test_result_is_scoped_to_account(self):
        self.post();self.decode.return_value='2';self.post()
        self.assertEqual(self.provider.analyze.call_count,2)

    def test_multi_person_results_charge_once_and_replay(self):
        self.provider.analyze.return_value=scene_result(3)
        result=self.post();self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['detected_people_count'],3)
        self.assertTrue(all(len(s['people'])==3 for s in result.json()['suggestions']))
        self.assertEqual(self.post().json(),result.json())
        self.assertEqual(self.quota().json()['remaining'],0)
        self.provider.analyze.assert_called_once()

    def test_zero_and_over_limit_people_do_not_charge(self):
        for count in (0,4):
            self.provider.analyze.return_value=scene_result(count)
            result=self.post();self.assertEqual(result.status_code,422,result.text)
            self.assertEqual(result.json()['detail']['scene']['detected_people_count'],count)
            self.assertEqual(self.quota().json()['remaining'],1)
        self.provider.analyze.return_value=RESULT
        self.assertEqual(self.post().status_code,200)

    def test_missing_duplicate_or_unsupported_person_targets_fail_without_charge(self):
        for mode in ('missing','duplicate','unsupported','solo_spacing','string_count'):
            result=scene_result(2)
            if mode=='missing':result['suggestions'][0]['people'].pop()
            if mode=='duplicate':result['suggestions'][0]['people'][1]['person']=1
            if mode=='unsupported':result['suggestions'][0]['people'][0]['pose_id']='sitting'
            if mode=='solo_spacing':
                result=scene_result();result['suggestions'][0]['spacing']='close'
            if mode=='string_count':result['detected_people_count']='2'
            self.provider.analyze.return_value=result
            self.assertEqual(self.post().status_code,502,mode)
            self.assertEqual(self.quota().json()['remaining'],1)

    def test_legacy_saved_result_is_not_presented_as_new_analysis(self):
        self.post()
        with Session(self.engine) as db:
            row=db.scalar(select(LivePoseSession));row.result={'scene':'Legacy','poses':[]};db.commit()
        self.assertEqual(self.post().status_code,409)
        self.provider.analyze.assert_called_once()


class ConcurrencyTests(TestCase):
    def test_simultaneous_requests_cannot_exceed_free_limit(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(production_engine,'connect',side_effect=AssertionError('Live DB forbidden')):
            engine=create_engine('sqlite:///'+str(Path(folder)/'pose.sqlite'),connect_args={'check_same_thread':False,'timeout':10})
            try:
                for model in (User,SubscriptionPlan,Subscription,LivePoseSession):model.__table__.create(engine)
                with Session(engine) as db:
                    db.add(User(id=1,name='Test',email='pose@example.invalid',role='user'));db.commit()
                fake=Mock(available=True)
                def analyze(_):time.sleep(.05);return RESULT
                fake.analyze.side_effect=analyze
                def run(key):
                    with Session(engine) as db:
                        try:return service.analyze(db,db.get(User,1),key,jpeg(),fake)
                        except HTTPException as e:return e.status_code
                key=str(uuid4())
                with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(run,[key,key,str(uuid4())]))
                self.assertEqual(fake.analyze.call_count,1)
                self.assertTrue(all(r==RESULT or r==429 for r in results))
                with Session(engine) as db:self.assertEqual(len(list(db.scalars(select(LivePoseSession)))),1)
            finally:engine.dispose()

class ProviderTests(TestCase):
    def settings(self):return replace(provider.settings,live_pose_vision_enabled=True,pollinations_enabled=True,pollinations_api_key='mock-secret',pollinations_chat_model='openai/gpt-5.4-nano')
    def test_multimodal_request_and_valid_response(self):
        def handler(request):
            body=json.loads(request.content)
            self.assertEqual(request.headers['authorization'],'Bearer mock-secret')
            parts=body['messages'][1]['content']
            self.assertTrue(parts[1]['image_url']['url'].startswith('data:image/jpeg;base64,'))
            return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(RESULT)}}]})
        with patch.object(provider,'settings',self.settings()):
            self.assertEqual(provider.PollinationsSceneProvider(httpx.MockTransport(handler)).analyze(jpeg()),RESULT)
    def test_disabled_never_calls_provider(self):
        with patch.object(provider,'settings',replace(self.settings(),live_pose_vision_enabled=False)):
            fake=Mock(side_effect=AssertionError('Network forbidden'))
            with self.assertRaises(HTTPException):provider.PollinationsSceneProvider(httpx.MockTransport(fake)).analyze(jpeg())
            fake.assert_not_called()
    def test_invalid_response_and_errors(self):
        bad={**RESULT,'suggestions':[RESULT['suggestions'][0]]*3}
        for response in (httpx.Response(500),httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(bad)}}]}),httpx.Response(200,content=b'x'*33000)):
            with patch.object(provider,'settings',self.settings()):
                with self.assertRaises(HTTPException) as caught:
                    provider.PollinationsSceneProvider(httpx.MockTransport(lambda req:response)).analyze(jpeg())
                self.assertEqual(caught.exception.status_code,502)
