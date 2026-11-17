"""Mock-only regressions: no database, Redis, SMTP or Stripe connections."""
import hashlib
import hmac
import json
import time
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import pytest
from fastapi import HTTPException, Response
from app.services import payment_service, email_verification as email, rate_limit_service as limits
from app.routers import email_verification as routes

@pytest.mark.parametrize('signature', ['', 't=1,v1=bad', 't=9999999999,v1=bad'])
def test_invalid_signature_never_initializes_payment_runtime(signature):
    with patch('app.core.stripe_test.require_release', return_value=NS(webhook_secret='whsec_mock')), \
         patch.object(payment_service, 'runtime') as runtime, \
         patch('app.database.connection.SessionLocal') as session, \
         patch('app.services.payment_schema.require_payment_schema') as schema:
        with pytest.raises(HTTPException) as error:
            payment_service.receive_webhook(b'{}', signature)
        assert error.value.status_code == 400
        runtime.assert_not_called(); session.assert_not_called(); schema.assert_not_called()

def test_oversized_payload_never_initializes_runtime():
    with patch('app.core.stripe_test.require_release', return_value=NS(webhook_secret='whsec_mock')), patch.object(payment_service, 'runtime') as runtime:
        with pytest.raises(HTTPException) as error:
            payment_service.receive_webhook(b'x' * 262145, '')
        assert error.value.status_code == 413
        runtime.assert_not_called()

def test_valid_signature_preserves_processing():
    event = {'id':'evt_test', 'object':'event', 'livemode':False, 'type':'checkout.session.completed', 'data':{'object':{}}}
    raw = json.dumps(event).encode(); stamp = str(int(time.time()))
    digest = hmac.new(b'whsec_mock', stamp.encode()+b'.'+raw, hashlib.sha256).hexdigest()
    db, repo, provider = Mock(), Mock(), Mock()
    with patch('app.core.stripe_test.require_release', return_value=NS(webhook_secret='whsec_mock')), \
         patch.object(payment_service, 'runtime', return_value=(repo, provider, None)) as runtime, \
         patch('app.services.payment_processing.process_event', return_value={'ok':True}) as process:
        assert payment_service.receive_webhook(raw, f't={stamp},v1={digest}', db) == {'ok':True}
        runtime.assert_called_once_with(db)
        process.assert_called_once_with(event, raw, repo, provider)

@pytest.mark.parametrize('action', ['readiness', 'verify', 'resend'])
def test_peer_limit_precedes_all_expensive_checks(action):
    request = NS(client=NS(host='peer')); db = Mock()
    with patch.object(routes, 'limit_verification_peer', side_effect=HTTPException(429,'Too many attempts')) as limit, \
         patch.object(email, 'prerequisites') as prerequisites, \
         patch.object(routes, 'EmailVerificationRepository') as repository, \
         patch.object(routes, 'limit_public_auth') as token_limit:
        with pytest.raises(HTTPException) as error:
            if action == 'readiness': routes.readiness(Response(), request, db)
            elif action == 'verify': routes.verify(routes.VerificationRequest(token='a'*43), request, Response(), db)
            else: routes.resend(routes.ResendRequest(email='someone@example.com'), request, Response(), db)
        assert error.value.status_code == 429
        limit.assert_called_once_with(action, 'peer')
        prerequisites.assert_not_called(); repository.assert_not_called(); token_limit.assert_not_called()

def test_delivery_independent_prerequisites_keep_security_checks():
    inspector = Mock(); inspector.get_columns.return_value = [{'name':n,'nullable':False} for n in ('email_verification_required','is_verified','auth_version')]
    with patch('sqlalchemy.inspect', return_value=inspector), patch('app.core.account_state.enabled') as enabled, \
         patch.object(email, 'client') as client, \
         patch('app.services.gmail_auth_email.GmailAuthEmailDelivery', side_effect=HTTPException(503,'SMTP unavailable')) as smtp:
        client.return_value.ping.return_value = True
        assert email.prerequisites(Mock(), require_delivery=False) is None
        enabled.assert_called_once(); smtp.assert_not_called()
        with pytest.raises(HTTPException): email.prerequisites(Mock())
        client.return_value.ping.return_value = False
        with pytest.raises(HTTPException): email.prerequisites(Mock(), require_delivery=False)
        inspector.get_columns.return_value = []
        with pytest.raises(HTTPException): email.prerequisites(Mock(), require_delivery=False)

def test_existing_token_route_and_readiness_work_without_smtp():
    request=NS(client=NS(host='peer')); db=Mock()
    with patch.object(routes,'limit_verification_peer'), patch.object(routes,'limit_public_auth'), \
         patch.object(email,'prerequisites') as prerequisites, patch.object(email,'verify',return_value={'status':'verified'}) as verify, \
         patch.object(routes,'EmailVerificationRepository') as repository, \
         patch('app.services.gmail_auth_email.GmailAuthEmailDelivery',side_effect=HTTPException(503,'SMTP unavailable')):
        assert routes.readiness(Response(),request,db) == {'available':True,'delivery_available':False}
        assert routes.verify(routes.VerificationRequest(token='a'*43),request,Response(),db) == {'status':'verified'}
        assert all(c.kwargs == {'require_delivery':False} for c in prerequisites.call_args_list)
        verify.assert_called_once_with('a'*43,repository.return_value)

@pytest.mark.parametrize('count,status', [(30,None),(31,429)])
def test_peer_rate_limit_boundary(count,status):
    with patch.object(limits,'client') as client:
        client.return_value.eval.return_value=count
        if status:
            with pytest.raises(HTTPException) as error: limits.limit_verification_peer('verify','peer')
            assert error.value.status_code==status
            assert error.value.headers['Retry-After']=='60'
        else: limits.limit_verification_peer('verify','peer')
        args=client.return_value.eval.call_args.args
        assert args[1]==1 and args[3]==60 and 'peer' not in args[2].split(':')[-1]

def test_peer_limit_redis_failure_closed():
    with patch.object(limits,'client',side_effect=RuntimeError('unavailable')):
        with pytest.raises(HTTPException) as error: limits.limit_verification_peer('resend','peer')
        assert error.value.status_code==503

def test_tampered_current_signature_never_reaches_runtime():
    with patch('app.core.stripe_test.require_release', return_value=NS(webhook_secret='whsec_mock')), patch.object(payment_service,'runtime') as runtime:
        with pytest.raises(HTTPException):
            payment_service.receive_webhook(b'{}', f't={int(time.time())},v1=' + '0'*64, Mock())
        runtime.assert_not_called()

@pytest.mark.parametrize('action', ['readiness','verify','resend'])
def test_allowed_request_order_and_resend_still_requires_delivery(action):
    calls=[]; request=NS(client=NS(host='peer')); db=Mock()
    with patch.object(routes,'limit_verification_peer',side_effect=lambda *a: calls.append('peer')), \
         patch.object(routes,'limit_public_auth',side_effect=lambda *a: calls.append('token')), \
         patch.object(email,'prerequisites',side_effect=lambda *a,**kw: calls.append(('prerequisites',kw))) as prerequisites, \
         patch.object(routes,'EmailVerificationRepository'), patch.object(email,'verify'), patch.object(email,'resend'), \
         patch('app.services.gmail_auth_email.GmailAuthEmailDelivery'):
        if action=='readiness': routes.readiness(Response(),request,db)
        elif action=='verify': routes.verify(routes.VerificationRequest(token='a'*43),request,Response(),db)
        else: routes.resend(routes.ResendRequest(email='someone@example.com'),request,Response(),db)
        assert calls[0]=='peer'
        if action=='verify': assert calls[1]=='token'
        assert calls[-1] == ('prerequisites', {} if action=='resend' else {'require_delivery':False})
