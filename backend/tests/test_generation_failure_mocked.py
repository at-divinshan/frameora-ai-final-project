"""Failure injection only: no images, filesystem writes, database or providers."""
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import pytest
from fastapi import HTTPException
from app.services import ai_service as normal, owner_generation_service as owner
from app.services import user_paid_generation as paid

@contextmanager
def rig(role):
    with ExitStack() as stack:
        def mock(obj,name,**kwargs): return stack.enter_context(patch.object(obj,name,**kwargs))
        service=owner if role=='owner' else normal
        count=8 if role=='owner' else 4
        user=NS(id=7,role='owner' if role=='owner' else 'user')
        db=Mock();g=NS(id=9,user_id=7,plan_id=1,status=owner.PENDING if role=='owner' else paid.PENDING if role=='paid' else normal.allowance.PENDING_STATUS,created_at=datetime.now(timezone.utc).replace(tzinfo=None))
        db.get.return_value=g;db.scalar.return_value=0
        mock(service.provider,'require_reference_support');mock(service.provider,'require_configured')
        generate=mock(service.provider,'generate_images',return_value=[bytes([n]) for n in range(count)])
        write=mock(service.storage,'write_image',side_effect=[f'key-{n}' for n in range(count)])
        delete=mock(service.storage,'delete_image')
        if role=='owner':
            mock(owner,'_reserve',return_value=(9,'prompt',[{}]*count))
            mock(owner,'_lock_owner');mock(owner,'_owned',return_value=(g,NS(subscription_id=8)))
            mock(owner,'get_result',return_value={'status':'completed'})
            refund=mock(owner,'_fail',return_value=True)
            stack.enter_context(patch('app.services.paid_credit_service.require_settlement'))
            stack.enter_context(patch('app.services.project_phase_service.record_completed'))
            stack.enter_context(patch('app.services.notification_service.available',return_value=False))
        else:
            mock(normal.plan_repository,'find_for_user',return_value=NS(id=1))
            mock(normal,'build_image_prompt',return_value='prompt');mock(normal,'planned_shots',return_value=[{}]*4)
            mock(normal,'lock_profile');mock(normal,'generation_view',return_value={'status':'completed'})
            mock(paid,'reserve',return_value=paid.Reservation(9) if role=='paid' else None)
            mock(paid,'settle')
            if role=='paid': refund=mock(paid,'fail')
            else:
                mock(normal.allowance,'reconcile_interrupted_request')
                mock(normal.allowance,'reserve_free_request',return_value=NS(generation_id=9))
                refund=mock(normal.allowance,'release_failed_request')
        yield NS(db=db,g=g,generate=generate,write=write,delete=delete,refund=refund,
                 call=lambda:service.generate(db,user,plan_id=1,description='',reference=None,idempotency_key='stable-mocked-request'))

@pytest.mark.parametrize('role',['free','paid','owner'])
@pytest.mark.parametrize('fault',['timeout','http','partial','duplicate','malformed','storage'])
def test_confirmed_failure_releases_claim_without_final_commit(role,fault):
    with rig(role) as r:
        if fault=='timeout':r.generate.side_effect=TimeoutError()
        elif fault=='http':r.generate.side_effect=HTTPException(502,'Provider unavailable')
        elif fault=='partial':r.generate.return_value=[b'a']
        elif fault=='duplicate':r.generate.return_value=[b'a']*(8 if role=='owner' else 4)
        elif fault=='malformed':r.generate.return_value=None
        else:r.write.side_effect=['first-key',OSError('simulated failure')]
        with pytest.raises(HTTPException):r.call()
        r.refund.assert_called_once();r.db.commit.assert_not_called()
        if fault=='storage':r.delete.assert_called_once_with('first-key')
        else:r.write.assert_not_called()

@pytest.mark.parametrize('role',['paid','owner'])
@pytest.mark.parametrize('fault',['before_commit','uncertain_commit','after_commit'])
def test_commit_boundary_controls_refund_and_file_retention(role,fault):
    with rig(role) as r:
        if fault=='before_commit':r.db.flush.side_effect=RuntimeError('precommit')
        elif fault=='uncertain_commit':r.db.commit.side_effect=RuntimeError('lost acknowledgement')
        target='get_result' if role=='owner' else 'generation_view'
        with patch.object(owner if role=='owner' else normal,target,side_effect=RuntimeError('response interrupted') if fault=='after_commit' else None):
            with pytest.raises((HTTPException,RuntimeError)):r.call()
        if fault=='before_commit':
            r.refund.assert_called_once();assert r.delete.call_count==(8 if role=='owner' else 4)
            r.db.commit.assert_not_called()
        else:
            r.refund.assert_not_called();r.delete.assert_not_called();r.db.commit.assert_called_once()


def test_owner_uncertain_refund_preserves_files():
    with rig('owner') as r:
        r.db.flush.side_effect=RuntimeError('precommit')
        r.refund.side_effect=RuntimeError('refund acknowledgement lost')
        with pytest.raises(HTTPException):r.call()
        r.delete.assert_not_called()

@pytest.mark.parametrize('role',['paid','owner'])
def test_process_interruption_leaves_reservation_for_reconciliation(role):
    with rig(role) as r:
        r.generate.side_effect=KeyboardInterrupt()
        with pytest.raises(KeyboardInterrupt):r.call()
        r.refund.assert_not_called();r.delete.assert_not_called();r.db.commit.assert_not_called()

@pytest.mark.parametrize('role',['paid','owner'])
def test_uncertain_reservation_never_starts_provider_or_compensation(role):
    with rig(role) as r:
        with patch.object(owner if role=='owner' else paid,'_reserve' if role=='owner' else 'reserve',side_effect=RuntimeError('reservation acknowledgement lost')):
            with pytest.raises(RuntimeError):r.call()
        r.generate.assert_not_called();r.write.assert_not_called();r.refund.assert_not_called()


def test_owner_pending_duplicate_does_not_call_provider_or_refund():
    with rig('owner') as r:
        with patch.object(owner,'_reserve',return_value=(9,None,None)),patch.object(owner,'get_result',return_value={'status':owner.PENDING}):
            with pytest.raises(HTTPException) as error:r.call()
        assert error.value.status_code==409
        r.generate.assert_not_called();r.refund.assert_not_called();r.write.assert_not_called()
