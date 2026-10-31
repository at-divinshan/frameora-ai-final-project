"""Owner-scoped access to existing studio profiles; service owns transactions."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.profile import UserProfile


STUDIO_FIELDS = ("studio_name", "studio_phone", "studio_address", "studio_city", "studio_description")


def find_owner_profile(db: Session, user_id: int, *, lock: bool = False) -> UserProfile | None:
    query = select(UserProfile).where(UserProfile.user_id == user_id)
    if lock:
        # A MySQL locking/current read sees a concurrent insert after the User lock
        # was acquired, even if authentication established an older RR snapshot.
        query = query.with_for_update().execution_options(populate_existing=True)
    return db.scalar(query)


def save_studio(db: Session, profile: UserProfile, values: dict) -> None:
    for field in STUDIO_FIELDS:
        setattr(profile, field, values[field])
    db.flush()
