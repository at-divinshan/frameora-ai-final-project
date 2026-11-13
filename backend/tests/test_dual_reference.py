"""Dual-reference contract tests. Isolated SQLite/files and mocked HTTP only."""
import base64
import json
import unittest
from dataclasses import replace
from unittest.mock import patch
import httpx
from fastapi import HTTPException
import test_ai as normal
import test_owner_credits as owner
from app.services import pollinations_service as provider, ai_image_storage as storage


def upload(image=normal.IMAGES[0],kind='image/png'):
    return ('reference.png',image,kind)

class NormalDualTests(unittest.TestCase):
    setUp=normal.GenerationTests.setUp
    tearDown=normal.GenerationTests.tearDown
    auth=normal.GenerationTests.auth
    generate=normal.GenerationTests.generate
    status=normal.GenerationTests.status
    def test_dual_and_alias(self):
        response=self.generate(files={'reference_photo':upload(),'background_reference':upload(normal.IMAGES[1])})
        self.assertEqual(response.status_code,201,response.text)
        self.assertEqual(self.mock_provider.call_args.args[1],storage.normalize_image(normal.IMAGES[0]))
        self.assertEqual(self.mock_provider.call_args.kwargs['background_reference'],storage.normalize_image(normal.IMAGES[1]))
    def test_background_only(self):
        response=self.generate(files={'background_reference':upload()})
        self.assertEqual(response.status_code,201,response.text)
        self.assertIsNone(self.mock_provider.call_args.args[1])
        self.assertIsNotNone(self.mock_provider.call_args.kwargs['background_reference'])
    def test_invalid_duplicate_oversized_before_allowance(self):
        for files,code in [({'background_reference':upload(kind='text/plain')},422),
                           ({'background_reference':upload(b'bad')},422),
                           ({'background_reference':upload(b'x'*(5*1024*1024+1))},413),
                           ({'reference':upload(),'reference_photo':upload()},422),
                           ([('background_reference',upload()),('background_reference',upload())],422)]:
            self.assertEqual(self.generate(files=files).status_code,code)
            self.assertEqual(self.status(),'available')
        self.mock_provider.assert_not_called()
    def test_unsupported_model_rejected_before_allowance(self):
        with patch.object(provider,'settings',replace(provider.settings,pollinations_image_model='unsupported-model')):
            self.assertEqual(self.generate(files={'background_reference':upload()}).status_code,422)
        self.assertEqual(self.status(),'available')
        self.mock_provider.assert_not_called()
    def test_dual_provider_failure_releases_allowance(self):
        self.mock_provider.side_effect=HTTPException(502,'Mock failure')
        self.assertEqual(self.generate(files={'reference':upload(),'background_reference':upload()}).status_code,502)
        self.assertEqual(self.status(),'available')

class OwnerDualTests(unittest.TestCase):
    setUp=owner.OwnerCreditTests.setUp
    tearDown=owner.OwnerCreditTests.tearDown
    auth=owner.OwnerCreditTests.auth
    activate=owner.OwnerCreditTests.activate
    generate=owner.OwnerCreditTests.generate
    generate_for_project=owner.OwnerCreditTests.generate_for_project
    ledger=owner.OwnerCreditTests.ledger
    eligibility=owner.OwnerCreditTests.eligibility
    def test_dual_retry_hash_and_project_scope(self):
        self.assertEqual(self.activate('trial').status_code,200)
        files={'reference_photo':upload(),'background_reference':upload(normal.IMAGES[1])}
        first=self.generate_for_project(1,files=files)
        self.assertEqual(first.status_code,201,first.text)
        self.assertEqual(self.generate_for_project(1,files=files).status_code,200)
        changed={**files,'background_reference':upload(normal.IMAGES[2])}
        self.assertEqual(self.generate_for_project(1,files=changed).status_code,409)
        self.assertEqual(self.mock.call_count,1)
        self.assertEqual(len([r for r in self.ledger() if r[0]=='spend']),1)
        self.assertEqual(self.mock.call_args.kwargs['background_reference'],storage.normalize_image(normal.IMAGES[1]))
        from app.services.owner_generation_service import request_hash
        self.assertNotEqual(request_hash(3,'',None,1,background_reference=b'a'),request_hash(3,'',None,2,background_reference=b'a'))
    def test_background_only_failure_refunds_once(self):
        self.assertEqual(self.activate('trial').status_code,200)
        self.mock.side_effect=HTTPException(502,'Mock failure')
        files={'background_reference':upload()}
        result=self.generate(files=files)
        self.assertEqual(result.status_code,503,result.text)
        self.generate(files=files)
        self.assertEqual(len([r for r in self.ledger() if r[0]=='refund']),1)
    def test_invalid_background_before_spend(self):
        self.assertEqual(self.activate('trial').status_code,200)
        before=self.ledger()
        for method in (self.generate,lambda **kw:self.generate_for_project(1,**kw)):
            self.assertEqual(method(files={'background_reference':upload(kind='text/plain')}).status_code,422)
            self.assertEqual(method(files={'reference':upload(),'reference_photo':upload()}).status_code,422)
            self.assertEqual(method(files={'background_reference':upload(b'x'*(11*1024*1024))}).status_code,413)
        self.assertEqual(self.ledger(),before)
        self.mock.assert_not_called()

class AdapterDualTests(unittest.TestCase):
    def test_background_only_owner_prompt_does_not_claim_person_reference(self):
        from app.models.photography_plan import PhotographyPlan
        from app.services.generation_planning import build_owner_image_prompt
        from app.services.owner_generation_service import DEFAULT_PREFERENCES
        plan = PhotographyPlan(photography_type='Portrait', people_count=1,
                               environment='Outdoor', location='Garden', preferences={})
        prompt = build_owner_image_prompt(plan, 'Natural lighting', DEFAULT_PREFERENCES,
                                         background_reference=True, person_reference=False)
        self.assertIn('scene reference only', prompt)
        self.assertNotIn('use the supplied reference image to preserve identity', prompt)
        self.assertIn('"background_mode": "uploaded_reference"', prompt)
        self.assertIn('Natural lighting', prompt)

    def test_all_reference_modes_and_order(self):
        config=replace(provider.settings,pollinations_enabled=True,pollinations_api_key='mock-only',pollinations_image_model='microsoft/mai-image-2.6-flash')
        for person,background in ((None,None),(normal.IMAGES[0],None),(None,normal.IMAGES[1]),(normal.IMAGES[0],normal.IMAGES[1])):
            calls=[]
            def handler(request):
                calls.append(request)
                return httpx.Response(200,json={'data':[{'b64_json':base64.b64encode(normal.IMAGES[len(calls)-1]).decode()}]})
            with patch.object(provider,'settings',config),patch.object(provider.httpx,'HTTPTransport',return_value=httpx.MockTransport(handler)):
                provider.generate_images('Test',[person,background]) if person and background else provider.generate_images('Test',person,background_reference=background)
            expected=[base64.b64encode(i).decode() for i in (person,background) if i is not None]
            for request in calls:
                body=json.loads(request.content)
                self.assertEqual([i['image_url'].split(',',1)[1] for i in body.get('image',[])],expected)
                self.assertEqual(request.url.path,'/v1/images/edits' if expected else '/v1/images/generations')
                if background and not person:self.assertIn('ONLY the target background',body['prompt'])
                if background and person:self.assertIn('Image 2 is the target background',body['prompt'])
    def test_background_suppresses_automatic_variations(self):
        from types import SimpleNamespace
        from app.services.generation_planning import planned_owner_shots
        from app.services.owner_generation_service import DEFAULT_PREFERENCES
        shots=planned_owner_shots(SimpleNamespace(preferences={},people_count=1),{**DEFAULT_PREFERENCES,'background_mode':'different'},background_reference=True)
        text=json.dumps(shots)
        self.assertNotIn('different physical location',text)
        self.assertIn('supplied background reference',text)
