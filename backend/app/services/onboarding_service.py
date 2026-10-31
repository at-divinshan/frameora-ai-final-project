"""Studio setup only: never creates subscriptions, credits or payment state."""

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.profile import UserProfile
from app.models.user import User
from app.repositories.profile_repository import STUDIO_FIELDS, find_owner_profile, save_studio
from app.repositories.user_repository import lock_profile
from app.schemas.owner import OwnerOnboarding, StudioDetails, StudioUpdate

NEXT_STEP = {"pending_studio": "studio_setup", "pending_plan": "subscription_selection", "completed": "dashboard"}


def require_owner(user: User | None):
    if user is None or user.role != "owner":
        raise HTTPException(403, "You do not have access to this resource.")


def response_for(profile: UserProfile | None) -> OwnerOnboarding:
    status = profile.onboarding_status if profile else "pending_studio"
    if status not in NEXT_STEP:
        # Unknown legacy state must not be silently promoted or overwritten.
        raise HTTPException(503, "Studio onboarding is temporarily unavailable.")
    return OwnerOnboarding(
        onboarding_status=status,
        onboarding_completed_at=profile.onboarding_completed_at if profile else None,
        next_step=NEXT_STEP[status],
        studio=StudioDetails(**{key: getattr(profile, key) for key in STUDIO_FIELDS}) if profile else None,
    )


def get_onboarding(db: Session, user: User) -> OwnerOnboarding:
    require_owner(user)
    return response_for(find_owner_profile(db, user.id))


def update_studio(db: Session, user: User, data: StudioUpdate) -> OwnerOnboarding:
    try:
        # The existing parent row always exists, unlike a first-time profile.
        # Every writer takes this lock first to serialize creation and updates.
        current = lock_profile(db, user.id)
        require_owner(current)
        profile = find_owner_profile(db, current.id, lock=True)
        if profile is None:
            profile = UserProfile(user_id=current.id, onboarding_status="pending_studio")
            db.add(profile)
        response_for(profile)  # Reject an unknown persisted state before changes.
        if profile.onboarding_status == "pending_studio":
            profile.onboarding_status = "pending_plan"
        # pending_plan/completed and completion timestamps remain intact.
        save_studio(db, profile, data.model_dump())
        result = response_for(profile)
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        # Covers a non-cooperating legacy writer; never overwrite another row.
        raise HTTPException(409, "Studio details changed concurrently. Please retry.") from None
    except Exception:
        db.rollback()
        raise
