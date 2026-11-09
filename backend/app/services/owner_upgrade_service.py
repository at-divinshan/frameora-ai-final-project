"""One-way conversion of an authenticated Normal User account to Studio Owner."""

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth_version import current_version
from app.core.security import auth_versions_enabled, require_jwt_configuration
from app.models.profile import UserProfile
from app.models.user import User
from app.repositories.profile_repository import find_owner_profile
from app.repositories.user_repository import lock_profile
from app.schemas.auth import TokenResponse
from app.services.auth_service import issue_session


def convert_to_owner(db: Session, user: User, remember_me: bool) -> TokenResponse:
    require_jwt_configuration()
    try:
        current = lock_profile(db, user.id)
        if current is None:
            raise HTTPException(401, "Your session is invalid or has expired.")
        if current.role == "admin":
            raise HTTPException(403, "You do not have access to this resource.")
        if current.role not in ("user", "owner"):
            raise HTTPException(403, "You do not have access to this resource.")

        if current.role == "user":
            profile = find_owner_profile(db, current.id, lock=True)
            current.role = "owner"
            if auth_versions_enabled():
                version = current_version(db, current.id, lock=True)
                if version is None or version == 2**64 - 1:
                    raise HTTPException(503, "Session refresh is temporarily unavailable.")
                current.auth_version = version + 1
            if profile is None:
                db.add(UserProfile(user_id=current.id, onboarding_status="pending_studio"))
            else:
                profile.onboarding_status = "pending_studio"
                profile.onboarding_completed_at = None

        db.flush()
        result = issue_session(db, current, remember_me)
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "Your account changed concurrently. Sign in again to continue."
        ) from None
    except Exception:
        db.rollback()
        raise
