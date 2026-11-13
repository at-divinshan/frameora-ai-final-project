"""Private project folders: real owned project relationships only."""
from fastapi import HTTPException
from sqlalchemy import select, func, and_
from app.models.ai_generation import AIGeneration as Generation
from app.models.photography_plan import PhotographyPlan as Plan
from app.models.customer_project import CustomerProject as Project
from app.models.media_asset import MediaAsset as Asset
from app.models.credit_transaction import CreditTransaction
from app.services import ai_service, owner_generation_service


def scope(user):
    query = select(Generation, Project).outerjoin(Plan, and_(Plan.id == Generation.plan_id, Plan.user_id == user.id))\
        .outerjoin(Project, and_(Project.id == Plan.project_id, Project.studio_owner_id == user.id,
                                Project.deleted_at.is_(None))).where(Generation.user_id == user.id)
    if user.role == 'owner':
        query = query.where(select(CreditTransaction.id).where(CreditTransaction.generation_id == Generation.id,
            CreditTransaction.user_id == user.id, CreditTransaction.transaction_type == 'spend').exists())
    return query


def folders(db, user):
    # SQL aggregation is independent of generation-page size; counts never describe
    # only the first 20 batches. Cover IDs use the same private image endpoint.
    query = scope(user).with_only_columns(Project.id, Project.project_title, Project.customer_name,
        func.count(Asset.id), func.max(Asset.id), func.max(Generation.id)).outerjoin(Asset,
        and_(Asset.generation_id == Generation.id, Asset.user_id == user.id,
             Asset.asset_type == 'ai_generated', Generation.status == 'completed'))\
        .group_by(Project.id, Project.project_title, Project.customer_name).order_by(func.max(Generation.id).desc())
    return [dict(key=str(pid) if pid is not None else 'unassigned', project_id=pid,
                 name=(title or customer or f'Project #{pid}') if pid is not None else 'Unassigned Images',
                 image_count=count, cover_id=cover) for pid, title, customer, count, cover, _ in db.execute(query)]


def contents(db, user, key, before=None):
    try:
        query = scope(user)
        if key == 'unassigned':
            query = query.where(Project.id.is_(None))
        else:
            if not key.isdigit() or not db.scalar(select(Project.id).where(Project.id == int(key),
                Project.studio_owner_id == user.id, Project.deleted_at.is_(None))):
                raise HTTPException(404, 'Project not found.')
            query = query.where(Project.id == int(key))
        if before is not None:
            query = query.where(Generation.id < before)
        if user.role == 'owner':
            owner_generation_service._lock_owner(db, user)
        rows = list(db.execute(query.order_by(Generation.id.desc()).limit(21)))
        items = [owner_generation_service._response_locked(db, user, g) if user.role == 'owner'
                 else ai_service.generation_view(db, g) for g, _ in rows[:20]]
        return dict(items=items, next_before=rows[19][0].id if len(rows) > 20 else None)
    finally:
        db.rollback()
