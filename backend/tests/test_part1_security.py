"""No database or Redis writes: mock/in-memory doubles only."""
import unittest
from unittest.mock import Mock,patch
from types import SimpleNamespace
from fastapi import HTTPException
from app.services import rate_limit_service as rate,suggestion_protection as suggestions,auth_email_tokens as tokens
from app.core import account_state
from app.services.auth_email_delivery import UnconfiguredAuthEmailDelivery

class SecurityTests(unittest.TestCase):
 def test_public_auth_limits_are_identical_and_hashed(self):
  for action in ('login','register'):
   db=Mock();db.eval.return_value=6
   with patch.object(rate,'client',return_value=db),self.assertRaises(HTTPException) as error:
    rate.limit_public_auth(action,'fixture@example.test','127.0.0.1')
   self.assertEqual(error.exception.status_code,429)
   self.assertNotIn('fixture',str(db.eval.call_args))
 def test_redis_failure_fails_closed(self):
  with patch.object(rate,'client',side_effect=RuntimeError('secret')),self.assertRaises(HTTPException) as e:
   rate.limit_public_auth('login','a@example.test','peer')
  self.assertEqual(e.exception.status_code,503);self.assertNotIn('secret',e.exception.detail)
 def test_missing_security_table_is_not_optional(self):
  inspector=Mock();inspector.has_table.return_value=False
  with patch.object(account_state,'inspect',return_value=inspector),self.assertRaises(HTTPException) as e:
   account_state.enabled(Mock())
  self.assertEqual(e.exception.status_code,503)
 def test_active_missing_row_and_deactivated_account(self):
  db=Mock();db.scalar.return_value=None
  with patch.object(account_state,'enabled',return_value=True):
   self.assertEqual(account_state.require_active(db,SimpleNamespace(id=1)),0)
   db.scalar.return_value=SimpleNamespace(is_active=False,version=2)
   with self.assertRaises(HTTPException) as e:account_state.require_active(db,SimpleNamespace(id=1))
   self.assertEqual(e.exception.status_code,401)
 def test_suggestion_concurrency_and_cost_limit(self):
  redis=Mock();redis.eval.return_value=1;redis.set.return_value=False
  with patch.object(suggestions,'client',return_value=redis),self.assertRaises(HTTPException) as e:suggestions.acquire(1)
  self.assertEqual(e.exception.status_code,409)
  redis.eval.return_value=61
  with patch.object(suggestions,'client',return_value=redis),self.assertRaises(HTTPException) as e:suggestions.acquire(1)
  self.assertEqual(e.exception.status_code,429)
 def test_suggestion_lock_release_checks_ownership(self):
  redis=Mock();redis.eval.return_value=1;redis.set.return_value=True
  with patch.object(suggestions,'client',return_value=redis):
   lease=suggestions.acquire(1);suggestions.release(lease)
  self.assertEqual(redis.set.call_args.kwargs,{'nx':True,'ex':240})
  self.assertEqual(redis.eval.call_args.args,(suggestions.RELEASE,1,*lease))
 def test_email_token_expiry_purpose_and_single_use(self):
  class Memory:
   def __init__(self):self.data={};self.now=0
   def set(self,k,v,*,nx,ex):self.data[k]=(v,self.now+ex);return True
   def eval(self,script,n,k):
    row=self.data.pop(k,None);return row[0] if row and row[1]>self.now else None
  redis=Memory()
  with patch.object(tokens,'client',return_value=redis):
   token=tokens.issue('verify-email',user_id=1,auth_version=2,email='fixture@example.test')
   self.assertNotIn(token,str(redis.data));self.assertNotIn('fixture@example.test',str(redis.data))
   with self.assertRaises(ValueError):tokens.consume('unsupported-purpose',token)
   self.assertEqual(tokens.consume('verify-email',token)['auth_version'],2)
   with self.assertRaises(HTTPException):tokens.consume('verify-email',token)
   token=tokens.issue('verify-email',user_id=1,auth_version=2,email='fixture@example.test');redis.now=1801
   with self.assertRaises(HTTPException):tokens.consume('verify-email',token)
 def test_email_delivery_has_no_insecure_fallback(self):
  with self.assertRaises(HTTPException) as e:UnconfiguredAuthEmailDelivery().send(recipient='fixture@example.test',purpose='verify-email',link='sensitive-fixture')
  self.assertNotIn('sensitive',e.exception.detail)

class IntegrationMocks(unittest.TestCase):
 def test_auth_routes_limit_before_lookup(self):
  from app.routers import auth
  from app.schemas.auth import LoginRequest,RegisterRequest
  request=SimpleNamespace(client=SimpleNamespace(host='peer'))
  for fn,data in [(auth.login,LoginRequest(email='fixture@example.com',password='fixture')),
                  (auth.register,RegisterRequest(name='Fixture',email='fixture@example.com',password='Fixturepass',confirm_password='Fixturepass',role='user',accept_terms=True))]:
   with patch.object(auth,'limit_public_auth',side_effect=HTTPException(429,'Too many attempts')),patch.object(auth.auth_service,'login') as login,patch.object(auth.auth_service,'register') as register:
    with self.assertRaises(HTTPException):fn(data,request,Mock())
    login.assert_not_called();register.assert_not_called()
 def test_suggestions_release_after_provider_failure(self):
  import asyncio
  from unittest.mock import AsyncMock
  from app.services import photography_suggestions as service
  with patch.object(service.plan_repository,'find_for_user',return_value=object()),patch.object(service,'build_suggestions_prompt',return_value='fixture'),patch.object(suggestions,'acquire',return_value=('key','token')),patch.object(suggestions,'release') as release:
   with self.assertRaises(RuntimeError):asyncio.run(service.get_plan_suggestions(Mock(),SimpleNamespace(id=1),1,SimpleNamespace(generate=AsyncMock(side_effect=RuntimeError()))))
   release.assert_called_once_with(('key','token'))
 def test_stale_account_version_rejected(self):
  db=Mock();db.scalar.return_value=SimpleNamespace(is_active=True,version=2)
  with patch.object(account_state,'enabled',return_value=True),self.assertRaises(HTTPException) as error:account_state.require_active(db,SimpleNamespace(id=1),1)
  self.assertEqual(error.exception.status_code,401)
