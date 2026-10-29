"""Password writes and session revocation form a single database transaction."""

from fastapi import HTTPException
from sqlalchemy import update

from app.core.auth_version import check_version, invalid_session
from app.core.security import require_password_management, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import lock_profile
from app.services.auth_service import SUPPORTED_ROLES, require_single_admin


def locked_account(db, user, expected):
    current = lock_profile(db, user.id)
    if current is None or current.role not in SUPPORTED_ROLES:
        raise invalid_session()
    check_version(db, current, expected, lock=True)
    require_single_admin(db, current)
    return current


def write_password(db, current, expected, new_hash):
    require_password_management()
    if type(expected) is not int or not 0 <= expected < 2**64 - 1:
        raise HTTPException(503, "Password management is unavailable.")
    # CAS additionally protects against stale writers; never overwrite a concurrent change.
    result = db.execute(update(User).where(
        User.id == current.id, User.auth_version == expected,
        User.password_hash == current.password_hash,
    ).values(password_hash=new_hash, auth_version=expected + 1),
        execution_options={"synchronize_session": False})
    if result.rowcount != 1:
        raise invalid_session()
    db.commit()
    return {"status": "password_updated", "reauthentication_required": True}


def change_password(db, user, request):
    require_password_management()
    expected = getattr(user, "_authenticated_version", None)
    try:
        current = locked_account(db, user, expected)
        if not verify_password(request.current_password, current.password_hash):
            raise HTTPException(400, "Unable to change password. Check your current password.")
        return write_password(db, current, expected, hash_password(request.new_password))
    except Exception:
        db.rollback()
        raise
