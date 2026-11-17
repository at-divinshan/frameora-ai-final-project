"""Password integration with mock sessions only; no database writes."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock,patch
from dataclasses import replace
from fastapi import HTTPException
from pydantic import ValidationError
from app.core import security,auth_version
from app.services import password_service as passwords,google_auth_service as google,auth_service as auth
from app.schemas.auth import PasswordChange,NewPassword,LoginRequest

class PasswordIntegration(unittest.TestCase):
 def setUp(self):
  self.settings=patch.object(security,'settings',replace(security.settings,auth_version_enabled=True,password_management_enabled=True,jwt_secret_key='fixture-only-key-'*4));self.settings.start();self.addCleanup(self.settings.stop)
 def account(self,role='user',password='Currentpass1'):
  return NS(id=1,role=role,name='Fixture',email='fixture@example.com',password_hash=security.hash_password(password) if password else None,google_sub=b'subject',_authenticated_version=0,auth_version=0,email_verification_required=False,is_verified=False)
 def test_roles_change_hash_and_version_and_reject_old_session(self):
  for role in ['user','owner','admin']:
   user=self.account(role);db=Mock();db.execute.return_value.rowcount=1
   token,_=security.create_access_token('1',False,0)
   with patch.object(passwords,'lock_profile',return_value=user),patch.object(passwords,'check_version'),patch.object(passwords,'require_single_admin'):
    result=passwords.change_password(db,user,PasswordChange(current_password='Currentpass1',new_password='Changedpass1',confirm_password='Changedpass1'))
   params=db.execute.call_args.args[0].compile().params
   self.assertEqual(params['auth_version'],1);self.assertTrue(security.verify_password('Changedpass1',params['password_hash']))
   self.assertFalse(security.verify_password('Currentpass1',params['password_hash']))
   db.commit.assert_called_once();self.assertTrue(result['reauthentication_required'])
   db.scalar.return_value=1
   with self.assertRaises(HTTPException):auth_version.check_version(db,user,security.decode_access_claims(token)['auth_version'])
   user.password_hash=params['password_hash']
   with patch.object(auth,'find_by_email',return_value=user),patch.object(auth,'lock_profile',return_value=user),patch.object(auth,'issue_session',return_value='fresh'):
    self.assertEqual(auth.login(db,LoginRequest(email=user.email,password='Changedpass1')),'fresh')
 def test_wrong_password_and_concurrent_change_do_not_commit(self):
  user=self.account();db=Mock()
  with patch.object(passwords,'locked_account',return_value=user):
   with self.assertRaises(HTTPException):passwords.change_password(db,user,PasswordChange(current_password='wrong',new_password='Changedpass1',confirm_password='Changedpass1'))
  db.execute.assert_not_called();db.commit.assert_not_called()
  db.execute.return_value.rowcount=0
  with self.assertRaises(HTTPException):passwords.write_password(db,user,0,'hash')
  db.commit.assert_not_called()
 def test_weak_and_mismatched_passwords(self):
  for password,confirm in [('short','short'),('lowercaseonly','lowercaseonly'),('Validpass1','Differentpass1')]:
   with self.assertRaises(ValidationError):NewPassword(new_password=password,confirm_password=confirm)
 def test_google_setup_is_bound_to_original_session_and_subject(self):
  import time
  user=self.account(password=None);db=Mock();db.execute.return_value.rowcount=1
  data=dict(user_id=1,auth_version=0,session_digest=google.digest('Bearer fixture'),started_at=time.time(),subject='subject')
  store=Mock();store.consume.return_value=data
  with patch.object(google,'get_store',return_value=store),patch.object(google,'public_account'),patch.object(google,'locked_account',return_value=user):
   with self.assertRaises(HTTPException):google.complete_password_setup(db,'handle','browser',user,'Bearer other',NewPassword(new_password='Changedpass1',confirm_password='Changedpass1'))
   db.execute.assert_not_called()
   result=google.complete_password_setup(db,'handle','browser',user,'Bearer fixture',NewPassword(new_password='Changedpass1',confirm_password='Changedpass1'))
   self.assertTrue(result['reauthentication_required']);db.commit.assert_called_once()
 def test_legacy_token_rejected_when_versioning_enabled(self):
  with patch.object(security,'settings',replace(security.settings,auth_version_enabled=False)):
   token,_=security.create_access_token('1',False)
  with self.assertRaises(HTTPException):security.decode_access_claims(token)
 def test_registration_preserves_password_hash_and_public_roles(self):
  from app.schemas.auth import RegisterRequest
  db=Mock();user=self.account()
  with patch.object(auth.email_verification,'prerequisites'),patch.object(auth.email_verification,'send_verification'),patch.object(auth,'find_by_email',return_value=None),patch.object(auth,'add_user',return_value=user) as add:
   result=auth.register(db,RegisterRequest(name='Fixture',email=user.email,password='Currentpass1',confirm_password='Currentpass1',role='user',accept_terms=True))
   self.assertEqual(result.role,'user');self.assertTrue(security.verify_password('Currentpass1',add.call_args.kwargs['password_hash']))
   db.commit.assert_called_once()
 def test_google_setup_wrong_subject_and_expiry_fail_closed(self):
  import time
  user=self.account(password=None)
  for subject,started in [('other',time.time()),('subject',time.time()-1000)]:
   db=Mock();store=Mock();store.consume.return_value=dict(user_id=1,auth_version=0,session_digest=google.digest('Bearer fixture'),started_at=started,subject=subject)
   with patch.object(google,'get_store',return_value=store),patch.object(google,'public_account'),patch.object(google,'locked_account',return_value=user):
    with self.assertRaises(HTTPException):google.complete_password_setup(db,'handle','browser',user,'Bearer fixture',NewPassword(new_password='Changedpass1',confirm_password='Changedpass1'))
   db.execute.assert_not_called();db.commit.assert_not_called()
 def test_google_link_preserves_password_and_checks_session(self):
  import time
  user=self.account();user.google_sub=None
  db=Mock();store=Mock();store.consume.return_value=dict(user_id=1,session_digest=google.digest('Bearer fixture'),reauthenticated_at=time.time(),auth_version=0,password_digest=google.digest(user.password_hash),identity={'sub':'subject'})
  original=user.password_hash
  with patch.object(google,'get_store',return_value=store),patch.object(google,'public_account'),patch.object(google,'lock_profile',return_value=user),patch.object(google,'check_version') as version,patch.object(google,'link_google_identity',return_value=True) as link:
   with self.assertRaises(HTTPException):google.link(db,'handle','browser',user,'Bearer wrong')
   link.assert_not_called()
   self.assertEqual(google.link(db,'handle','browser',user,'Bearer fixture'),{'status':'linked'})
   version.assert_called_once_with(db,user,0,lock=True)
   self.assertEqual(link.call_args.kwargs['password_hash'],original)
   self.assertEqual(user.password_hash,original)
   db.commit.assert_called_once()
 def test_capabilities_respect_flags_and_account_type(self):
  from app.routers.auth import password_capabilities
  from app.core import config
  with patch.object(config,'settings',replace(config.settings,auth_version_enabled=True,password_management_enabled=True,google_auth_enabled=True)):
   for role in ['user','owner','admin']:
    self.assertEqual(password_capabilities(self.account(role)),{'change_password':True,'google_password_setup':False})
    self.assertEqual(password_capabilities(self.account(role,password=None)),{'change_password':False,'google_password_setup':role!='admin'})
  with patch.object(config,'settings',replace(config.settings,password_management_enabled=False)):
   self.assertEqual(password_capabilities(self.account()),{'change_password':False,'google_password_setup':False})
