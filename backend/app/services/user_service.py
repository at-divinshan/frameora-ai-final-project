"""Self-profile operations on the authenticated database account."""

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.user import User
from app.repositories.user_repository import update_self_profile
from app.schemas.user import ProfileUpdate, SelfProfile
from app.schemas.user import PrivacySettings, PrivacyUpdate, PublicProfile
from app.repositories.user_repository import find_by_id, lock_profile, save_privacy
from app.services.auth_service import require_single_admin, SUPPORTED_ROLES
from app.services.profile_image_storage import valid_key


def self_profile(user: User) -> SelfProfile:
    return SelfProfile(
        id=str(user.id), name=user.name, phone=user.phone, email=user.email,
        role=user.role, is_verified=user.is_verified, created_at=user.created_at,
        profile_image=user.profile_image, has_password=user.password_hash is not None,
        google_linked=user.google_sub is not None,
    )


def update_profile(db: Session, user: User, data: ProfileUpdate) -> SelfProfile:
    try:
        user = lock_profile(db, user.id)
        if user is None or user.role not in SUPPORTED_ROLES:
            raise HTTPException(401, "Your session is invalid or has expired.")
        require_single_admin(db, user)
        update_self_profile(db, user, data.model_dump(exclude_unset=True))
        result = self_profile(user)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def privacy_settings(user: User) -> PrivacySettings:
    """Missing, null or malformed stored settings fail closed, without writing on reads."""
    stored = user.privacy_preferences
    values = {}
    if isinstance(stored, dict):
        for key in PrivacySettings.model_fields:
            value = stored.get(key)
            if isinstance(value, str) and value in ("private", "public"):
                values[key] = value
    if user.role == "admin":
        values["profile_visibility"] = "private"
    return PrivacySettings(**values)


def update_privacy(db: Session, user: User, data: PrivacyUpdate) -> PrivacySettings:
    try:
        current = lock_profile(db, user.id)
        if current is None or current.role not in SUPPORTED_ROLES:
            raise HTTPException(401, "Your session is invalid or has expired.")
        require_single_admin(db, current)
        changes = data.model_dump(exclude_unset=True)
        if current.role == "admin" and changes.get("profile_visibility") == "public":
            raise HTTPException(403, "Admin profiles must remain private.")
        values = privacy_settings(current).model_dump()
        values.update(changes)
        result = PrivacySettings(**values)
        save_privacy(db, current, result.model_dump())
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def public_profile(db: Session, user_id: int) -> PublicProfile:
    user = find_by_id(db, user_id)
    if user is None or user.role not in ("user", "owner") or privacy_settings(user).profile_visibility != "public":
        # Identical result for private, Admin and nonexistent accounts.
        raise HTTPException(404, "Profile not found.", headers={"Cache-Control": "no-store", "Pragma": "no-cache"})
    # Legacy filesystem paths/URLs are not public image references.
    return PublicProfile(name=user.name, profile_image=user.profile_image if valid_key(user.profile_image) else None)
