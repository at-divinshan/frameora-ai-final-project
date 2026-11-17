"""In-memory Redis/session doubles only; no database or external connections."""
import time
from dataclasses import replace
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from app.core import security, dependencies as deps
from app.services import session_revocation as service
from app.routers.auth import logout

@pytest.fixture
def setup():
    redis=Mock(); revoked={}
    redis.exists.side_effect=lambda key: key in revoked
    def put(key,value,pxat): revoked[key]=(value,pxat); return True
    redis.set.side_effect=put
    with patch.object(security,'settings',replace(security.settings,jwt_secret_key='mock-signing-key-only'*4,auth_version_enabled=True)), patch.object(service,'client',return_value=redis):
        yield redis,revoked

def creds(token): return HTTPAuthorizationCredentials(scheme='Bearer',credentials=token)

def test_current_token_only_ttl_and_repeat_are_safe(setup):
    redis,revoked=setup
    first,_=security.create_access_token('1',False,0,0)
    second,_=security.create_access_token('1',False,0,0)
    assert first!=second
    claims=security.decode_access_claims(first)
    assert logout(NS(id=1),creds(first)).status_code==204
    assert revoked=={service.key(first):('1',int(claims['exp'])*1000)}
    assert first not in str(revoked) and claims['jti'] not in str(revoked)
    service.revoke(first,claims)  # Identical absolute expiry, never broader revocation.
    assert len(revoked)==1
    with pytest.raises(HTTPException) as error:service.require_not_revoked(first)
    assert error.value.status_code==401
    service.require_not_revoked(second)
    db=Mock();user=NS(id=1,role='user');db.get.return_value=user
    with patch.object(deps.account_state,'enabled',return_value=True) as schema, patch.object(deps,'find_by_id',return_value=user) as repository, patch.object(deps.account_state,'require_active',return_value=0),patch.object(deps,'require_single_admin'),patch.object(deps,'check_version'):
        for _ in range(2):
            with pytest.raises(HTTPException) as error:deps.get_current_user(creds(first),db)
            assert error.value.status_code==401
        schema.assert_not_called();repository.assert_not_called();assert not db.mock_calls
        assert deps.get_current_user(creds(second),db) is user

@pytest.mark.parametrize('operation',['check','write'])
def test_redis_outage_fails_closed(setup,operation):
    redis,_=setup;redis.exists.side_effect=RuntimeError('private');redis.set.side_effect=RuntimeError('private')
    token,_=security.create_access_token('1',False,0,0);db=Mock()
    with patch.object(deps.account_state,'enabled') as schema,patch.object(deps,'find_by_id') as repository:
        with pytest.raises(HTTPException) as error:
            if operation=='check':deps.get_current_user(creds(token),db)
            else:logout(NS(id=1),creds(token))
        assert error.value.status_code==503 and 'private' not in error.value.detail
        schema.assert_not_called();repository.assert_not_called();assert not db.mock_calls

def test_expired_and_invalid_tokens_do_not_reach_redis_or_database(setup):
    import jwt
    redis,_=setup;token,_=security.create_access_token('1',False,0,0)
    claims=security.decode_access_claims(token);claims['exp']=int(time.time())-10
    expired=jwt.encode(claims,security.settings.jwt_secret_key,algorithm='HS256')
    for value in ('invalid',expired):
        db=Mock()
        with patch.object(deps.account_state,'enabled') as schema:
            with pytest.raises(HTTPException) as error:deps.get_current_user(creds(value),db)
            assert error.value.status_code==401
            schema.assert_not_called();assert not db.mock_calls
    redis.exists.assert_not_called();redis.set.assert_not_called()

def test_new_sessions_are_distinct_even_without_password_versioning(setup):
    with patch.object(security,'settings',replace(security.settings,auth_version_enabled=False)):
        a,_=security.create_access_token('1',False);b,_=security.create_access_token('1',False)
        assert a!=b
        service.revoke(a,security.decode_access_claims(a));service.require_not_revoked(b)

def test_equivalent_signature_encoding_cannot_evade_revocation(setup):
    token,_=security.create_access_token('1',False,0,0)
    service.revoke(token,security.decode_access_claims(token))
    padded=token+'='
    security.decode_access_claims(padded)
    with pytest.raises(HTTPException) as error:service.require_not_revoked(padded)
    assert error.value.status_code==401
