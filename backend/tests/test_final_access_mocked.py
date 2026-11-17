"""Sharing/gallery boundary tests with mock sessions and in-memory bytes only."""
from datetime import datetime, timedelta
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import pytest
from fastapi import HTTPException
from app.services import share_service as share, project_phase_service as phases
from app.services import feedback_service as feedback, ai_service, owner_generation_service as owner

NOW=datetime(2026,11,17)

def fixtures():
    return NS(id=4,generation_id=10,is_active=True,expires_at=None),NS(id=3,studio_owner_id=7,deleted_at=None),NS(id=10)

@pytest.mark.parametrize('condition',['disabled','expired','deleted'])
def test_disabled_expired_or_deleted_share_is_denied(condition):
    link,project,generation=fixtures();db=Mock()
    if condition=='disabled':link.is_active=False
    if condition=='expired':link.expires_at=NOW-timedelta(seconds=1)
    if condition=='deleted':project.deleted_at=NOW
    db.execute.return_value.one_or_none.return_value=(link,project,generation,NS())
    db.get.return_value=NS(id=7,role='owner')
    with patch.object(share,'_sync_owner_limit'):
        with pytest.raises(HTTPException) as error:share._active_share(db,'a'*43,NOW)
        assert error.value.status_code==404

def test_publication_query_is_explicit_and_project_owner_scoped():
    link,project,base=fixtures();db=Mock();db.scalars.return_value=[NS(id=11)]
    with patch.object(phases,'available',return_value=True):
        result=phases.visible_generations(db,link,project,base)
    assert [g.id for g in result]==[10,11]
    query=db.scalars.call_args.args[0];sql=str(query);params=query.compile().params
    assert 'ShareLinkPhase' in sql and 'ProjectGenerationPhase' in sql
    assert params['share_link_id_1']==4 and params['project_id_1']==3 and params['project_id_2']==3
    assert params['user_id_1']==7 and params['user_id_2']==7 and params['status_1']=='completed'
    with patch.object(phases,'available',return_value=False):
        assert phases.visible_generations(db,link,project,base)==[base]

@pytest.mark.parametrize('viewer_role',['user','owner','admin'])
def test_valid_link_holder_gets_preview_only(viewer_role):
    link,project,generation=fixtures();db=Mock();db.scalar.return_value=NS(file_url='private-key')
    with patch.object(share,'_active_share',return_value=(link,project,generation)), \
         patch.object(phases,'visible_generations',return_value=[generation]), \
         patch.object(share.ai_image_storage,'read_image',return_value=b'original') as read, \
         patch('app.services.shared_preview.preview_bytes',return_value=b'protected-preview') as preview:
        assert share.read_shared_image(db,NS(id=90,role=viewer_role),'a'*43,88)==b'protected-preview'
        preview.assert_called_once_with(b'original');read.assert_called_once_with('private-key')
        params=db.scalar.call_args.args[0].compile().params
        assert params['generation_id_1']==[10] and params['user_id_1']==7

def test_unpublished_shared_asset_denied_before_file_access():
    link,project,generation=fixtures();db=Mock();db.scalar.return_value=None
    with patch.object(share,'_active_share',return_value=(link,project,generation)),patch.object(phases,'visible_generations',return_value=[generation]),patch.object(share.ai_image_storage,'read_image') as read:
        with pytest.raises(HTTPException) as error:share.read_shared_image(db,NS(id=90),'a'*43,88)
        assert error.value.status_code==404;read.assert_not_called()

def test_owner_original_read_and_customer_denial_use_ownership_query():
    db=Mock();db.scalar.return_value=NS(file_url='private-key')
    with patch.object(ai_service.storage,'read_image',return_value=b'original') as read:
        assert owner.get_image(db,NS(id=7,role='owner'),88)==b'original'
        params=db.scalar.call_args.args[0].compile().params
        assert params['user_id_1']==7 and params['user_id_2']==7
        read.reset_mock();db.scalar.return_value=None
        with pytest.raises(HTTPException) as error:ai_service.get_image(db,NS(id=90,role='user'),88)
        assert error.value.status_code==404;read.assert_not_called()

def test_customer_feedback_is_author_and_published_asset_scoped():
    link,project,generation=fixtures();db=Mock();db.scalar.return_value=NS(id=88);db.scalars.return_value=[]
    with patch.object(share,'_active_share',return_value=(link,project,generation)),patch.object(phases,'visible_generations',return_value=[generation]),patch.object(feedback,'require_schema'):
        assert feedback.customer_comments(db,NS(id=90),'a'*43,88)==[]
        params=db.scalar.call_args.args[0].compile().params
        assert params['generation_id_1']==[10] and params['user_id_1']==7
        params=db.scalars.call_args.args[0].compile().params
        assert params['author_id_1']==90 and params['asset_id_1']==88 and params['project_id_1']==3

def test_revision_from_other_project_is_rejected_before_update():
    db=Mock();row=NS(asset_id=88,status='pending',revised_asset_id=None)
    db.scalar.side_effect=[row,NS(id=99,generation_id=111)]
    data=NS(model_fields_set={'revised_asset_id'},revised_asset_id=99,status=None)
    with patch.object(feedback.project_service,'require_project_access'),patch.object(feedback,'require_schema'),patch.object(share,'_owned_generation',return_value=None):
        with pytest.raises(HTTPException) as error:feedback.owner_feedback(db,NS(id=7,role='owner'),3,1,data)
        assert error.value.status_code==404
    assert row.status=='pending' and row.revised_asset_id is None
    db.commit.assert_not_called();db.flush.assert_not_called()
