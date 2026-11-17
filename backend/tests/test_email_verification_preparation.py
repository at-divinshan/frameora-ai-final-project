"""Mock-only preparation tests; database/network connections blocked by runner."""
import unittest
from unittest.mock import Mock,MagicMock,patch
from types import SimpleNamespace as NS
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from fastapi import HTTPException
from app.services import email_verification as service, auth_email_tokens as tokens
from app.services.gmail_auth_email import GmailSettings,GmailAuthEmailDelivery

class RedisFake:
 def __init__(self):self.rows={};self.now=0;self.lock=Lock()
 def set(self,k,v,*,nx,ex):
  with self.lock:
   if k in self.rows and self.rows[k][1]>self.now:return False
   self.rows[k]=(v,self.now+ex);return True
 def eval(self,script,n,k):
  with self.lock:
   row=self.rows.pop(k,None)
   return row[0] if row and row[1]>self.now else None

class VerificationTests(unittest.TestCase):
 def config(self):return GmailSettings('fixture@gmail.com','fixture-not-real','http://localhost:5173')
 def account(self):return NS(id=1,email='fixture@example.com',auth_version=0,email_verification_required=True,is_verified=False)
 def test_starttls_before_auth_and_safe_email(self):
  smtp=Mock();smtp.send_message.return_value={};factory=MagicMock();factory.return_value.__enter__.return_value=smtp
  with patch('app.services.gmail_auth_email.smtplib.SMTP',factory):
   GmailAuthEmailDelivery(self.config()).send(recipient='fixture@example.com',purpose='verify-email',link='http://localhost:5173/verify-email#token=fixture')
  self.assertEqual([c[0] for c in smtp.mock_calls],['ehlo','starttls','ehlo','login','send_message'])
  message=smtp.send_message.call_args.args[0]
  self.assertEqual(message['Subject'],'Verify your Frameora AI email')
  self.assertNotIn('fixture-not-real',message.as_string())
 def test_smtp_failure_sanitized_and_account_not_verified(self):
  redis=RedisFake();account=self.account()
  with patch.object(tokens,'client',return_value=redis),patch('app.services.gmail_auth_email.smtplib.SMTP',side_effect=RuntimeError('SECRET provider detail')):
   with self.assertRaises(HTTPException) as error:service.send_verification(account,GmailAuthEmailDelivery(self.config()))
  self.assertNotIn('SECRET',error.exception.detail);self.assertFalse(account.is_verified);self.assertFalse(redis.rows)
 def test_success_expiry_invalid_and_reuse(self):
  redis=RedisFake();accounts=Mock();accounts.verify_pending.return_value=True
  with patch.object(tokens,'client',return_value=redis):
   token=tokens.issue('verify-email',user_id=1,auth_version=0,email='fixture@example.com')
   self.assertNotIn(token,str(redis.rows))
   self.assertEqual(service.verify(token,accounts)['status'],'verified')
   accounts.verify_pending.assert_called_once()
   with self.assertRaises(HTTPException):service.verify(token,accounts)
   with self.assertRaises(HTTPException):service.verify('bad',accounts)
   token=tokens.issue('verify-email',user_id=1,auth_version=0,email='fixture@example.com');redis.now=1800
   with self.assertRaises(HTTPException):service.verify(token,accounts)
 def test_concurrent_token_has_only_one_winner(self):
  redis=RedisFake();accounts=Mock();accounts.verify_pending.return_value=True
  with patch.object(tokens,'client',return_value=redis):
   token=tokens.issue('verify-email',user_id=1,auth_version=0,email='fixture@example.com')
   def attempt(_):
    try:return service.verify(token,accounts)['status']
    except HTTPException:return 'rejected'
   with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,range(2)))
  self.assertEqual(results.count('verified'),1);accounts.verify_pending.assert_called_once()
 def test_legacy_and_google_accounts_not_forced_to_verify(self):
  for verified in [False,True]:
   service.require_verified_for_password_login(NS(email_verification_required=False,is_verified=verified))
  with self.assertRaises(HTTPException) as error:service.require_verified_for_password_login(self.account())
  self.assertEqual(error.exception.status_code,403)
  account=self.account();account.is_verified=True;service.require_verified_for_password_login(account)
 def test_resend_generic_cooldown_and_limit(self):
  for account in [None,self.account()]:
   redis=RedisFake();accounts=Mock();accounts.pending_by_email.return_value=account;delivery=Mock();delivery.config=self.config()
   with patch.object(service,'client',return_value=redis),patch.object(service,'limit_public_auth'),patch.object(service,'send_verification',side_effect=HTTPException(503,'private')):
    self.assertEqual(service.resend('fixture@example.com','peer',accounts,delivery),service.GENERIC_RESPONSE)
    with self.assertRaises(HTTPException) as error:service.resend('fixture@example.com','peer',accounts,delivery)
    self.assertEqual(error.exception.status_code,429)
  with patch.object(service,'limit_public_auth',side_effect=HTTPException(429,'rate')):
   accounts=Mock()
   with self.assertRaises(HTTPException):service.resend('fixture@example.com','peer',accounts,Mock())
   accounts.pending_by_email.assert_not_called()
 def test_schema_dependent_endpoints_disabled(self):
  from app.routers.email_verification import readiness
  from fastapi import Response
  with patch('app.routers.email_verification.limit_verification_peer'),patch.object(service,'prerequisites',side_effect=HTTPException(503,'Unavailable')):
   self.assertFalse(readiness(Response(),NS(client=NS(host='peer')),Mock())['available'])
  with patch('app.routers.email_verification.limit_verification_peer'),patch.object(service,'prerequisites'):
   self.assertTrue(readiness(Response(),NS(client=NS(host='peer')),Mock())['available'])
 def test_no_insecure_smtp_or_origin(self):
  for config in [GmailSettings('x@gmail.com','fixture','http://example.com'),GmailSettings('x@gmail.com','fixture','https://example.com',port=25)]:
   with self.assertRaises(HTTPException):config.validate()
