"""Real JWT validation with mocked persistence only; no services or database writes."""
from dataclasses import replace
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import time
import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from app.core import dependencies as deps, security

SECRET = 'unit-test-only-signing-key-not-a-real-secret' * 2

@pytest.fixture
def signing():
    with patch.object(security, 'settings', replace(security.settings,
            jwt_secret_key=SECRET, auth_version_enabled=True)), patch.object(deps, "require_not_revoked") as revocation:
        yield revocation

def token(**changes):
    now = int(time.time())
    claims = dict(sub='1', iat=now, nbf=now, exp=now+60,
                  iss=security.JWT_ISSUER, aud=security.JWT_AUDIENCE,
                  type='access', auth_version=0, account_version=0)
    claims.update(changes)
    return jwt.encode(claims, SECRET, algorithm='HS256')

def credentials(value):
    return HTTPAuthorizationCredentials(scheme='Bearer', credentials=value)

@pytest.mark.parametrize('case', [
    'missing', 'malformed', 'tampered', 'expired', 'future', 'issuer', 'audience',
    'type', 'version', 'missing_version', 'algorithm', 'subject', 'zero_subject',
    'overflow_subject', 'unicode_subject', 'account_version', 'negative_account_version',
])
def test_rejected_jwt_has_zero_database_schema_repository_operations(signing, case):
    changes = {'expired': {'exp': int(time.time())-10}, 'future': {'nbf': int(time.time())+600},
        'issuer': {'iss':'wrong'}, 'audience': {'aud':'wrong'}, 'type': {'type':'refresh'},
        'version': {'auth_version':True}, 'missing_version': {'auth_version':None},
        'subject': {'sub':'not-an-id'}, 'zero_subject': {'sub':'0'},
        'overflow_subject': {'sub':'2147483648'}, 'unicode_subject': {'sub':'١'},
        'account_version': {'account_version':True}, 'negative_account_version': {'account_version':-1}}
    value = token(**changes.get(case, {}))
    if case == 'missing_version':
        claims = jwt.decode(value, options={'verify_signature':False})
        claims.pop('auth_version')
        value = jwt.encode(claims, SECRET, algorithm='HS256')
    if case == 'malformed': value = 'not-a-jwt'
    if case in ('tampered', 'algorithm'):
        claims = jwt.decode(value, options={'verify_signature':False})
        value = jwt.encode(claims, 'wrong-key-for-test-only'*3 if case=='tampered' else SECRET,
                           algorithm='HS256' if case=='tampered' else 'HS384')
    db = Mock()
    with patch.object(deps.account_state,'enabled') as schema, \
         patch.object(deps.account_state,'require_active') as active, \
         patch.object(deps,'find_by_id') as repository, \
         patch.object(deps,'check_version') as version, \
         patch.object(deps,'require_single_admin') as admin:
        with pytest.raises(HTTPException) as error:
            deps.get_current_user(None if case=='missing' else credentials(value), db)
        assert error.value.status_code == 401
        assert error.value.headers['WWW-Authenticate'] == 'Bearer'
        assert not db.mock_calls
        signing.assert_not_called()
        for guard in (schema,active,repository,version,admin): guard.assert_not_called()

@pytest.mark.parametrize('role', ['user','owner','admin'])
def test_valid_jwt_preserves_schema_account_version_and_rbac(signing, role):
    user=NS(id=1,role=role); db=Mock(); db.get.return_value=user
    calls=[]
    with patch.object(deps,'decode_access_claims',wraps=security.decode_access_claims) as decode, \
         patch.object(deps.account_state,'enabled',side_effect=lambda db: calls.append('schema') or True), \
         patch.object(deps,'find_by_id',side_effect=lambda db,uid: calls.append('lookup') or user), \
         patch.object(deps.account_state,'require_active',return_value=0) as active, \
         patch.object(deps,'check_version') as version, patch.object(deps,'require_single_admin') as admin:
        result=deps.get_current_user(credentials(token()),db)
        decode.assert_called_once(); assert calls==['schema','lookup']
        active.assert_called_once_with(db,user,0)
        version.assert_called_once_with(db,user,0); admin.assert_called_once_with(db,user)
        assert result._authenticated_version==0 and result._account_version==0
        assert deps.require_roles(role)(result) is result
        with pytest.raises(HTTPException) as error: deps.require_roles('owner' if role!='owner' else 'admin')(result)
        assert error.value.status_code==403

@pytest.mark.parametrize('failure', ['schema','inactive','stale_account','stale_password','admin'])
def test_valid_signature_does_not_bypass_security_guards(signing, failure):
    user=NS(id=1,role='admin'); db=Mock(); db.get.return_value=user
    with patch.object(deps.account_state,'enabled',return_value=True) as schema, \
         patch.object(deps,'find_by_id',return_value=user), \
         patch.object(deps.account_state,'require_active',return_value=0) as active, \
         patch.object(deps,'check_version') as version, patch.object(deps,'require_single_admin') as admin:
        target={'schema':schema,'inactive':active,'stale_account':active,'stale_password':version,'admin':admin}[failure]
        status=503 if failure=='schema' else 403 if failure=='admin' else 401
        target.side_effect=HTTPException(status,'Rejected')
        with pytest.raises(HTTPException) as error: deps.get_current_user(credentials(token()),db)
        assert error.value.status_code==status
        target.assert_called_once()

@pytest.mark.parametrize('versioned', [False, True])
def test_legacy_account_version_zero_still_enforces_account_state(signing,versioned):
    claims=jwt.decode(token(),options={'verify_signature':False}); claims.pop('account_version')
    if not versioned: claims.pop('auth_version')
    value=jwt.encode(claims,SECRET,algorithm='HS256'); user=NS(id=1,role='user'); db=Mock(); db.get.return_value=user
    with patch.object(security,'settings',replace(security.settings,auth_version_enabled=versioned)), \
         patch.object(deps.account_state,'enabled',return_value=True), patch.object(deps,'find_by_id',return_value=user), \
         patch.object(deps.account_state,'require_active',return_value=0) as active, \
         patch.object(deps,'require_single_admin'),patch.object(deps,'check_version') as version:
        deps.get_current_user(credentials(value),db)
        active.assert_called_once_with(db,user,0)
        assert version.call_count==int(versioned)
