"""Picture mutations serialize on the authenticated User row; storage is never public."""

import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user_repository import lock_profile
from app.services.auth_service import SUPPORTED_ROLES, require_single_admin
from app.services.user_service import privacy_settings
from app.services import profile_image_storage as storage

logger = logging.getLogger(__name__)


def cleanup(key):
    try:
        storage.delete_image(key)
    except OSError:
        # Orphans stay private; cleanup failure must not undo a committed replacement.
        logger.warning("Private profile picture cleanup deferred.")


def change_picture(db: Session, user: User, data: bytes | None) -> dict:
    key = None
    commit_started = False
    try:
        # Decode before taking a row lock. No file is written for invalid input.
        normalized = storage.normalize_image(data) if data is not None else None
        current = lock_profile(db, user.id)
        if current is None or current.role not in SUPPORTED_ROLES:
            raise HTTPException(401, "Your session is invalid or has expired.")
        require_single_admin(db, current)
        previous = current.profile_image
        if normalized is not None:
            key = storage.write_image(normalized)
        current.profile_image = key
        db.flush()
        commit_started = True
        db.commit()
    except Exception as error:
        db.rollback()
        # A lost commit acknowledgement is ambiguous: keep both files, never break
        # a potentially committed reference. Unreferenced keys have no serving route.
        if not commit_started and key is not None:
            cleanup(key)
        if isinstance(error, OSError):
            raise HTTPException(503, "Profile picture storage is unavailable.") from None
        raise
    cleanup(previous)
    return {"profile_image": key}


def get_picture(db: Session, user_id: int, *, public: bool) -> bytes:
    # Hold the lock until the bytes have been read, preventing replacement cleanup
    # from deleting the selected file halfway through this request.
    user = lock_profile(db, user_id)
    if user is None or (public and (
        user.role not in ("user", "owner") or privacy_settings(user).profile_visibility != "public"
    )):
        raise HTTPException(404, "Profile picture not found.")
    if not public:
        if user.role not in SUPPORTED_ROLES:
            raise HTTPException(401, "Your session is invalid or has expired.")
        require_single_admin(db, user)
    try:
        return storage.read_image(user.profile_image)
    except OSError:
        raise HTTPException(404, "Profile picture not found.") from None
