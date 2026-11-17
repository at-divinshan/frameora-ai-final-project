"""RBAC and account-state regressions. All persistence uses mocks, never engines."""
from dataclasses import replace
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from app.main import app
from app.database.connection import get_db
from app.core import dependencies as deps, security, account_state
from app.services import auth_service, google_auth_service, project_service, ai_service
from app.repositories import project_repository
from app.schemas.auth import LoginRequest

@pytest.mark.parametrize('role,prefix', [('user','admin'),('user','owner'),('owner','admin'),('admin','owner')])
def test_http_wrong_role_never_reaches_business_database(role,prefix):
    db=Mock(); previous=dict(app.dependency_overrides)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[deps.get_current_user]=lambda:NS(id=7,role=role)
    paths={'admin':['/admin/users','/admin/payments','/admin/owners'],
           'owner':['/owner/onboarding','/owner/projects','/owner/share-links']}
    try:
        with TestClient(app) as client:
            for path in paths[prefix]:
                response=client.get(path)
                assert response.status_code==403, path
        assert not db.mock_calls
    finally:
        app.dependency_overrides.clear();app.dependency_overrides.update(previous)

@pytest.fixture
def signing():
    with patch.object(security,'settings',replace(security.settings,
            jwt_secret_key='phase2-fixture-only-not-a-real-key'*2,auth_version_enabled=True)), \
         patch.object(deps,'require_not_revoked'),patch.object(account_state,'enabled',return_value=True):
        yield

def current(db,user,account_version=0,password_version=0):
    token,_=security.create_access_token(str(user.id),False,password_version,account_version)
    db.get.return_value=user
    with patch.object(deps,'find_by_id',return_value=user):
        return deps.get_current_user(HTTPAuthorizationCredentials(scheme='Bearer',credentials=token),db)

@pytest.mark.parametrize('role',['user','owner'])
def test_deactivated_password_login_and_protected_access_blocked(signing,role):
    user=NS(id=7,role=role,password_hash='mock',email_verification_required=False,is_verified=False)
    db=Mock();db.get.return_value=user;db.scalar.return_value=NS(is_active=False,version=1)
    with patch.object(auth_service,'find_by_email',return_value=user),patch.object(auth_service,'lock_profile',return_value=user),patch.object(auth_service,'verify_password',return_value=True):
        with pytest.raises(HTTPException) as error:
            auth_service.login(db,LoginRequest(email='fixture@example.com',password='fixture'))
        assert error.value.status_code==401
    with pytest.raises(HTTPException) as error:current(db,user)
    assert error.value.status_code==401
    db.commit.assert_not_called();db.add.assert_not_called()

@pytest.mark.parametrize('role',['user','owner'])
def test_reactivated_account_rejects_old_jwt_accepts_fresh_version(signing,role):
    user=NS(id=7,role=role);db=Mock();state=NS(is_active=True,version=2)
    db.scalar.return_value=state
    with pytest.raises(HTTPException) as error:current(db,user,account_version=0)
    assert error.value.status_code==401
    db.scalar.side_effect=[state,0]
    assert current(db,user,account_version=2) is user
    db.commit.assert_not_called();db.add.assert_not_called()

def test_stale_password_version_rejected_after_account_check(signing):
    user=NS(id=7,role='user');db=Mock();db.scalar.side_effect=[NS(is_active=True,version=0),1]
    with pytest.raises(HTTPException) as error:current(db,user,password_version=0)
    assert error.value.status_code==401
    db.commit.assert_not_called()

def test_google_completion_cannot_bypass_deactivation(signing):
    user=NS(id=7,role='user');db=Mock()
    db.scalar.side_effect=[0,NS(is_active=False,version=1)]
    store=Mock();store.consume.return_value={'action':'login','identity':{'sub':'fixture'},'user_id':7,'account_version':0,'auth_version':0,'remember':False}
    with patch.object(google_auth_service,'get_store',return_value=store),patch.object(google_auth_service,'find_by_google_sub',return_value=user),patch.object(google_auth_service,'lock_profile',return_value=user),patch.object(google_auth_service,'issue_session') as issue:
        with pytest.raises(HTTPException) as error:google_auth_service.complete(db,'mock','mock')
        assert error.value.status_code==401;issue.assert_not_called()
    db.commit.assert_not_called()

def test_other_owner_project_and_original_image_are_not_accessible():
    user=NS(id=7,role='owner');db=Mock();db.scalar.return_value=None
    with patch.object(project_service,'_locked_owner',return_value=user):
        with pytest.raises(HTTPException) as error:project_service.require_project_access(db,user,99,editable=True)
        assert error.value.status_code==404
        statement=db.scalar.call_args.args[0]
        params=statement.compile().params
        assert params['studio_owner_id_1']==7 and params['id_1']==99
    with patch.object(ai_service.storage,'read_image') as read:
        with pytest.raises(HTTPException) as error:ai_service.get_image(db,user,99)
        assert error.value.status_code==404;read.assert_not_called()
        params=db.scalar.call_args.args[0].compile().params
        assert params['user_id_1']==7 and params['user_id_2']==7
    db.commit.assert_not_called();db.add.assert_not_called()

@pytest.mark.parametrize('table_exists',[False,True])
def test_missing_or_incomplete_security_schema_fails_closed(table_exists):
    db=Mock();inspector=Mock();inspector.has_table.return_value=table_exists
    inspector.get_columns.return_value=[{'name':'user_id'}]
    with patch.object(account_state,'inspect',return_value=inspector):
        with pytest.raises(HTTPException) as error:account_state.enabled(db)
        assert error.value.status_code==503
    db.scalar.assert_not_called();db.commit.assert_not_called()

def test_every_admin_and_owner_route_has_server_role_guard():
    import inspect
    def guards(dependant):
        call=dependant.call
        if inspect.isfunction(call) and call.__name__=='authorize':
            yield inspect.getclosurevars(call).nonlocals.get('roles')
        for child in dependant.dependencies:yield from guards(child)
    def routes(items):
        for route in items:
            if hasattr(route, "original_router"):
                yield from routes(route.original_router.routes)
            else:
                yield route
    checked=0
    for route in routes(app.routes):
        if not hasattr(route,'dependant'):continue
        role='admin' if route.path.startswith('/admin/') else 'owner' if route.path.startswith('/owner/') else None
        if role:
            assert (role,) in list(guards(route.dependant)),route.path
            checked+=1
    assert checked>20
