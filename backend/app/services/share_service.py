from datetime import datetime
from hashlib import sha256
import re
import secrets

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ai_generation import AIGeneration
from app.models.customer_project import CustomerProject
from app.models.media_asset import MediaAsset
from app.models.photography_plan import PhotographyPlan
from app.models.share_link import ShareLink
from app.models.user import User
from app.repositories.user_repository import lock_profile
from app.schemas.sharing import (
    ShareLinkCreated,
    ShareLinkRead,
    SharedGeneration,
    SharedImage,
)
from app.services import ai_image_storage, ai_service, owner_entitlement_service, project_service, subscription_service
from app.services.onboarding_service import require_owner

TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")


def _now() -> datetime:
    return subscription_service.clock()


def _owned_generation(db: Session, user: User, project_id: int, generation_id: int):
    return db.execute(
        select(AIGeneration, PhotographyPlan)
        .join(PhotographyPlan, PhotographyPlan.id == AIGeneration.plan_id)
        .where(
            AIGeneration.id == generation_id,
            AIGeneration.user_id == user.id,
            AIGeneration.status == "completed",
            PhotographyPlan.user_id == user.id,
            PhotographyPlan.project_id == project_id,
        )
    ).one_or_none()


def _generation_assets(db: Session, user_id: int, generation_id: int):
    return list(
        db.scalars(
            select(MediaAsset)
            .where(
                MediaAsset.generation_id == generation_id,
                MediaAsset.user_id == user_id,
                MediaAsset.asset_type == "ai_generated",
            )
            .order_by(MediaAsset.id)
        )
    )


def _sync_owner_limit(db: Session, user: User, now: datetime) -> int:
    _, entitlement = owner_entitlement_service.resolve_locked(db, user, now=now)
    limit = entitlement["max_share_links"]
    if limit < 1:
        raise HTTPException(409, "Select an owner subscription before managing share links.")

    rows = list(
        db.execute(
            select(ShareLink, CustomerProject)
            .join(CustomerProject, CustomerProject.id == ShareLink.project_id)
            .where(CustomerProject.studio_owner_id == user.id)
            .order_by(ShareLink.created_at.asc(), ShareLink.id.asc())
            .with_for_update()
        )
    )
    retained = 0
    for link, project in rows:
        if not link.is_active:
            continue
        if project.deleted_at is not None or (link.expires_at is not None and link.expires_at <= now):
            link.is_active = False
            continue
        if retained >= limit:
            link.is_active = False
            continue
        retained += 1
    db.flush()
    return limit


def _validate_project(db: Session, user: User, project_id: int, *, editable: bool) -> None:
    project_service.require_project_access(db, user, project_id, editable=editable)


def create_link(
    db: Session, user: User, project_id: int, generation_id: int, expires_at: datetime | None
) -> ShareLinkCreated:
    try:
        now = _now()
        _validate_project(db, user, project_id, editable=True)
        lock_profile(db, user.id)
        require_owner(user)
        limit = _sync_owner_limit(db, user, now)
        if expires_at is not None and expires_at <= now:
            raise HTTPException(422, "Share-link expiration must be in the future.")
        if _owned_generation(db, user, project_id, generation_id) is None:
            raise HTTPException(404, "Generation not found for this project.")
        if not _generation_assets(db, user.id, generation_id):
            raise HTTPException(404, "Generation images not found.")

        active_count = db.scalar(
            select(func.count())
            .select_from(ShareLink)
            .join(CustomerProject, CustomerProject.id == ShareLink.project_id)
            .where(
                CustomerProject.studio_owner_id == user.id,
                ShareLink.is_active.is_(True),
            )
        )
        if active_count >= limit:
            raise HTTPException(409, "Your subscription share-link limit has been reached.")

        token = secrets.token_urlsafe(32)
        link = ShareLink(
            project_id=project_id,
            generation_id=generation_id,
            token_hash=sha256(token.encode("ascii")).hexdigest(),
            expires_at=expires_at,
            is_active=True,
        )
        db.add(link)
        db.flush()
        db.refresh(link)
        result = ShareLinkCreated(
            id=link.id,
            project_id=link.project_id,
            generation_id=link.generation_id,
            is_active=link.is_active,
            expires_at=link.expires_at,
            created_at=link.created_at,
            token=token,
        )
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def list_links(db: Session, user: User, project_id: int) -> list[ShareLinkRead]:
    try:
        now = _now()
        _validate_project(db, user, project_id, editable=False)
        lock_profile(db, user.id)
        _sync_owner_limit(db, user, now)
        rows = db.scalars(
            select(ShareLink)
            .where(ShareLink.project_id == project_id)
            .order_by(ShareLink.created_at.asc(), ShareLink.id.asc())
        )
        result = [ShareLinkRead.model_validate(link) for link in rows]
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def deactivate_link(db: Session, user: User, project_id: int, link_id: int) -> None:
    try:
        now = _now()
        _validate_project(db, user, project_id, editable=False)
        lock_profile(db, user.id)
        _sync_owner_limit(db, user, now)
        link = db.scalar(
            select(ShareLink).where(
                ShareLink.id == link_id,
                ShareLink.project_id == project_id,
            )
        )
        if link is None:
            raise HTTPException(404, "Share link not found.")
        link.is_active = False
        db.commit()
    except Exception:
        db.rollback()
        raise


def _active_share(db: Session, token: str, now: datetime):
    if not TOKEN_PATTERN.fullmatch(token):
        raise HTTPException(404, "Share link not found.")
    digest = sha256(token.encode("ascii")).hexdigest()
    row = db.execute(
        select(ShareLink, CustomerProject, AIGeneration, PhotographyPlan)
        .join(CustomerProject, CustomerProject.id == ShareLink.project_id)
        .join(AIGeneration, AIGeneration.id == ShareLink.generation_id)
        .join(PhotographyPlan, PhotographyPlan.id == AIGeneration.plan_id)
        .where(
            ShareLink.token_hash == digest,
            AIGeneration.status == "completed",
            AIGeneration.user_id == CustomerProject.studio_owner_id,
            PhotographyPlan.user_id == CustomerProject.studio_owner_id,
            PhotographyPlan.project_id == CustomerProject.id,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "Share link not found.")
    link, project, generation, plan = row
    owner = db.get(User, project.studio_owner_id)
    if owner is None:
        raise HTTPException(404, "Share link not found.")
    _sync_owner_limit(db, owner, now)
    db.refresh(link, with_for_update=True)
    db.refresh(project, with_for_update=True)
    if (
        not link.is_active
        or project.deleted_at is not None
        or (link.expires_at is not None and link.expires_at <= now)
    ):
        db.commit()
        raise HTTPException(404, "Share link not found.")
    return link, project, generation


def view_shared_generation(db: Session, user: User, token: str) -> SharedGeneration:
    try:
        link, project, generation = _active_share(db, token, _now())
        result = ai_service.generation_view(db, generation)
        if not result["images"]:
            raise HTTPException(404, "Shared images not found.")
        shared = SharedGeneration(
            project_id=project.id,
            generation_id=generation.id,
            images=[
                SharedImage(id=image["id"], guidance=image["guidance"])
                for image in result["images"]
            ],
        )
        db.commit()
        return shared
    finally:
        db.rollback()


def read_shared_image(db: Session, user: User, token: str, asset_id: int) -> bytes:
    try:
        link, project, generation = _active_share(db, token, _now())
        asset = db.scalar(
            select(MediaAsset).where(
                MediaAsset.id == asset_id,
                MediaAsset.generation_id == generation.id,
                MediaAsset.user_id == project.studio_owner_id,
                MediaAsset.asset_type == "ai_generated",
            )
        )
        if asset is None:
            raise HTTPException(404, "Shared image not found.")
        key = asset.file_url
        db.commit()
    finally:
        db.rollback()
    try:
        from app.services.shared_preview import preview_bytes
        return preview_bytes(ai_image_storage.read_image(key))
    except OSError:
        raise HTTPException(404, "Shared image not found.") from None