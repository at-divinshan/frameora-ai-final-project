"""Persist successful phases under the existing owner lock; never backfill history."""
from fastapi import HTTPException
from sqlalchemy import inspect, select, func
from app.models.project_generation_phase import ProjectGenerationPhase as Phase, ShareLinkPhase
from app.models.photography_plan import PhotographyPlan
from app.models.customer_project import CustomerProject
from app.models.ai_generation import AIGeneration
from app.models.share_link import ShareLink


def available(db):
    inspector = inspect(db.connection())
    return all(inspector.has_table(t.__tablename__) for t in (Phase, ShareLinkPhase))


def phase_for(db, generation_id):
    return db.scalar(select(Phase).where(Phase.generation_id == generation_id)) if available(db) else None


def record_completed(db, generation, now):
    # Caller holds the owner row lock through completion/commit. Missing migration
    # preserves existing generation behavior, without pretending history was recorded.
    if generation.status != 'completed' or not available(db):
        return
    plan = db.get(PhotographyPlan, generation.plan_id)
    if not plan or plan.user_id != generation.user_id or plan.project_id is None:
        return
    project = db.scalar(select(CustomerProject).where(CustomerProject.id == plan.project_id,
        CustomerProject.studio_owner_id == generation.user_id, CustomerProject.deleted_at.is_(None)).with_for_update())
    if project is None or phase_for(db, generation.id):
        return
    number = (db.scalar(select(func.max(Phase.phase_number)).where(Phase.project_id == project.id)) or 0) + 1
    db.add(Phase(project_id=project.id, generation_id=generation.id, phase_number=number, created_at=now))
    db.flush()


def visible_generations(db, link, project, base):
    # Existing token always retains precisely its original generation grant.
    generations = {base.id: base}
    if available(db):
        rows = db.scalars(select(AIGeneration).join(Phase, Phase.generation_id == AIGeneration.id)
            .join(ShareLinkPhase, ShareLinkPhase.phase_id == Phase.id)
            .join(PhotographyPlan, PhotographyPlan.id == AIGeneration.plan_id)
            .where(ShareLinkPhase.share_link_id == link.id, Phase.project_id == project.id,
                   PhotographyPlan.project_id == project.id, PhotographyPlan.user_id == project.studio_owner_id,
                   AIGeneration.user_id == project.studio_owner_id, AIGeneration.status == 'completed'))
        generations.update((g.id, g) for g in rows)
    return list(generations.values())


def publish(db, user, project_id, link_id, phase_id):
    from app.services import share_service, project_service
    try:
        if user.role != 'owner':
            raise HTTPException(403, 'Studio Owner access required.')
        if not available(db):
            raise HTTPException(503, 'Phase publication requires migration 010.')
        from app.repositories.user_repository import lock_profile
        lock_profile(db, user.id)
        project_service.require_project_access(db, user, project_id, editable=True)
        share_service._sync_owner_limit(db, user, share_service._now())
        link = db.scalar(select(ShareLink).where(ShareLink.id == link_id,
            ShareLink.project_id == project_id).with_for_update())
        now = share_service._now()
        if not link or not link.is_active or (link.expires_at and link.expires_at <= now):
            raise HTTPException(404, 'Active share link not found.')
        phase = db.scalar(select(Phase).where(Phase.id == phase_id, Phase.project_id == project_id))
        if not phase or share_service._owned_generation(db, user, project_id, phase.generation_id) is None:
            raise HTTPException(404, 'Completed project phase not found.')
        existing = db.scalar(select(ShareLinkPhase).where(ShareLinkPhase.share_link_id == link.id,
                                                         ShareLinkPhase.phase_id == phase.id))
        if not existing:
            db.add(ShareLinkPhase(share_link_id=link.id, phase_id=phase.id, published_by=user.id, created_at=now))
            from app.services.notification_service import revision_shared
            revision_shared(db, project_id, phase.generation_id, link.id)
        db.commit()
        return {'phase_id': phase.id, 'share_link_id': link.id, 'published': True}
    finally:
        db.rollback()
