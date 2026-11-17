"""Transactional adapter and registration contracts, mocks only."""
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace as NS
from hashlib import sha256
from fastapi import HTTPException
from app.services import auth_service as auth
from app.repositories.email_verification_repository import EmailVerificationRepository
from app.schemas.auth import RegisterRequest, LoginRequest

class IntegrationTests(unittest.TestCase):
 def user(self):return NS(id=1,name='Fixture',email='fixture@example.com',role='user',auth_version=0,password_hash='hash',is_verified=False,email_verification_required=False)
 def registration(self):return RegisterRequest(name='Fixture',email='fixture@example.com',role='user',password='Fixturepass1',confirm_password='Fixturepass1',accept_terms=True)
 def test_registration_commit_before_delivery_and_failure_keeps_pending(self):
  for fails in [False,True]:
   user=self.user();db=Mock();order=[];db.commit.side_effect=lambda:order.append('commit')
   def send(account,delivery):
    order.append('send');self.assertTrue(account.email_verification_required)
    if fails:raise HTTPException(503,'SMTP')
   with patch.object(auth,'find_by_email',return_value=None),patch.object(auth,'add_user',return_value=user),patch.object(auth,'hash_password',return_value='hash'),patch.object(auth.email_verification,'prerequisites'),patch.object(auth.email_verification,'send_verification',side_effect=send):
    result=auth.register(db,self.registration())
   self.assertEqual(order,['commit','send']);self.assertEqual(result.email_sent,not fails)
   self.assertEqual(result.status,'verification_required');self.assertTrue(user.email_verification_required);self.assertFalse(user.is_verified)
 def test_uncertain_commit_never_sends_email(self):
  db=Mock();db.commit.side_effect=RuntimeError('uncertain')
  with patch.object(auth,'find_by_email',return_value=None),patch.object(auth,'add_user',return_value=self.user()),patch.object(auth,'hash_password',return_value='hash'),patch.object(auth.email_verification,'prerequisites'),patch.object(auth.email_verification,'send_verification') as send:
   with self.assertRaises(RuntimeError):auth.register(db,self.registration())
   send.assert_not_called()
 def test_login_only_blocks_pending_new_accounts(self):
  for required,verified in [(False,False),(False,True),(True,False),(True,True)]:
   user=self.user();user.email_verification_required=required;user.is_verified=verified
   with patch.object(auth,'require_jwt_configuration'),patch.object(auth,'find_by_email',return_value=user),patch.object(auth,'lock_profile',return_value=user),patch.object(auth,'verify_password',return_value=True),patch.object(auth,'issue_session',return_value='session') as issue:
    if required and not verified:
     with self.assertRaises(HTTPException) as error:auth.login(Mock(),LoginRequest(email=user.email,password='fixture'))
     self.assertEqual(error.exception.status_code,403);issue.assert_not_called()
    else:self.assertEqual(auth.login(Mock(),LoginRequest(email=user.email,password='fixture')),'session')
 def test_repository_locks_checks_and_verifies_once(self):
  user=self.user();user.email_verification_required=True;db=Mock();db.get.return_value=user
  repo=EmailVerificationRepository(db);payload=dict(user_id=1,auth_version=0,email_digest=sha256(user.email.encode()).hexdigest())
  with patch('app.repositories.email_verification_repository.require_active'):
   self.assertTrue(repo.verify_pending(**payload));self.assertFalse(repo.verify_pending(**payload))
  self.assertTrue(user.is_verified);self.assertFalse(user.email_verification_required);db.commit.assert_called_once()
  self.assertTrue(db.get.call_args.kwargs['with_for_update'])
 def test_repository_rejects_changed_identity_version_and_inactive(self):
  for mode in ['email','version','inactive','legacy']:
   user=self.user();user.email_verification_required=mode!='legacy';db=Mock();db.get.return_value=user
   payload=dict(user_id=1,auth_version=1 if mode=='version' else 0,email_digest='wrong' if mode=='email' else sha256(user.email.encode()).hexdigest())
   with patch('app.repositories.email_verification_repository.require_active',side_effect=HTTPException(401,'inactive') if mode=='inactive' else None):
    self.assertFalse(EmailVerificationRepository(db).verify_pending(**payload))
   db.commit.assert_not_called();self.assertFalse(user.is_verified)
