"""Mock-only reporting tests: no database connections or provider calls."""
import unittest
from unittest.mock import Mock,patch
from types import SimpleNamespace
from datetime import date
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.dialects import mysql
from pydantic import ValidationError
from app.main import app
from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.services import admin_payment_service as s
from app.schemas.admin_payments import PaymentFilters

class PaymentManagementTests(unittest.TestCase):
 def test_empty_and_filtered_listing(self):
  db=Mock(); summary=Mock();summary.mappings.return_value.one.return_value=dict(total=0,successful=None,revenue=None,pending=None,failed_refunded=None)
  rows=Mock();rows.mappings.return_value.all.return_value=[];db.execute.side_effect=[summary,rows]
  result=s.listing(db,PaymentFilters(role='owner',plan='starter',status='succeeded',date_from=date(2026,1,1),date_to=date(2026,1,31),page=2))
  self.assertEqual(result['items'],[]);self.assertEqual(result['summary']['revenue'],'0')
  query=db.execute.call_args_list[1].args[0].compile(dialect=mysql.dialect())
  self.assertIn('UNION ALL',str(query));self.assertIn('LEFT OUTER JOIN',str(query))
  for v in ('owner','starter','succeeded',20):self.assertIn(v,query.params.values())
  db.add.assert_not_called();db.commit.assert_not_called()
 def test_both_roles_allowlisted_projection(self):
  for role in ('user','owner'):
   row=dict(kind='payment',id=1,user_id=7,name='Fixture',email='fixture@example.test',role=role,plan='starter',date=None,amount=490,currency='lkr',status='succeeded',transaction_id='pi_fixture',checkout_id=2,livemode=False,verified_at='recorded',revoked_at=None,subscription_id=3)
   result=s.item(row);self.assertEqual(result['role'],role);self.assertTrue(result['verified']);self.assertNotIn('user_id',result)
   row.update(kind='checkout',verified_at=None,status='pending');self.assertFalse(s.item(row)['verified'])
 def test_details_and_missing(self):
  db=Mock();db.execute.return_value.mappings.return_value.one_or_none.return_value=None
  with self.assertRaises(HTTPException) as e:s.detail(db,'payment',1)
  self.assertEqual(e.exception.status_code,404)
  row=dict(kind='checkout',id=1,user_id=7,amount=490,verified_at=None,livemode=False,subscription_id=None,checkout_id=1)
  a,b,c=Mock(),Mock(),Mock();a.mappings.return_value.one_or_none.return_value=row;b.mappings.return_value.one_or_none.return_value=None;c.mappings.return_value.all.return_value=[]
  db.execute.side_effect=[a,b,c];result=s.detail(db,'checkout',1)
  self.assertIsNone(result['allocation']);self.assertIsNone(result['subscription']);self.assertEqual(result['events'],[])
 def test_invalid_filters(self):
  for kwargs in [dict(role='admin'),dict(page=0),dict(date_from='2026-02-01',date_to='2026-01-01')]:
   with self.assertRaises(ValidationError):PaymentFilters(**kwargs)
 def test_recorded_activation_allocation_and_reversal_details(self):
  db=Mock()
  row=dict(kind='payment',id=1,user_id=7,amount=490,verified_at='recorded',livemode=False,subscription_id=3,checkout_id=2)
  values=[row,dict(status='cancelled',start_date=None,end_date=None),dict(credits=40,period_start=None,period_end=None,revoked_at='recorded')]
  responses=[]
  for value in values:
   response=Mock();response.mappings.return_value.one_or_none.return_value=value;responses.append(response)
  events=Mock();events.mappings.return_value.all.return_value=[dict(event_type='refund.updated',outcome='revoked',processed_at=None,amount_minor=49000,currency='lkr')];responses.append(events)
  db.execute.side_effect=responses
  result=s.detail(db,'payment',1)
  self.assertEqual(result['allocation']['credits'],40)
  self.assertEqual(result['subscription']['status'],'cancelled')
  self.assertEqual(result['events'][0]['outcome'],'revoked')
  db.commit.assert_not_called();db.add.assert_not_called()
 def test_admin_only_endpoints(self):
  previous=app.dependency_overrides.copy()
  try:
   app.dependency_overrides[get_db]=lambda:Mock()
   for role in ('user','owner','admin'):
    app.dependency_overrides[get_current_user]=lambda role=role:SimpleNamespace(role=role)
    with patch.object(s,'listing',return_value={'items':[]}) as listing,patch.object(s,'detail',return_value={'id':1}) as detail:
     client=TestClient(app)
     for path in ('/admin/payments','/admin/payments/payment/1'):
      self.assertEqual(client.get(path).status_code,200 if role=='admin' else 403)
     if role!='admin':listing.assert_not_called();detail.assert_not_called()
   def unauthenticated(): raise HTTPException(401,'Authentication required')
   app.dependency_overrides[get_current_user]=unauthenticated
   self.assertEqual(TestClient(app).get('/admin/payments').status_code,401)
  finally:app.dependency_overrides.clear();app.dependency_overrides.update(previous)
