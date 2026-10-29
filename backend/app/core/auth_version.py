"""Explicit version reads only behind the migration gate. No schema changes."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import auth_versions_enabled
from app.models.user import User


def invalid_session():
    return HTTPException(401, "Your session is invalid or has expired. Please sign in again.",
                         headers={"WWW-Authenticate": "Bearer"})


def current_version(db: Session, user_id: int, *, lock=False) -> int | None:
    if not auth_versions_enabled():
        return None
    query = select(User.auth_version).where(User.id == user_id)
    if lock:
        query = query.with_for_update()
    value = db.scalar(query)
    if type(value) is not int or not 0 <= value <= 2**64 - 1:
        raise invalid_session()
    return value


def check_version(db: Session, user: User, expected, *, lock=False):
    if auth_versions_enabled():
        if type(expected) is not int or current_version(db, user.id, lock=lock) != expected:
            raise invalid_session()


def check_authenticated_snapshot(db: Session, user: User):
    if auth_versions_enabled() and hasattr(user, "_authenticated_version"):
        check_version(db, user, user._authenticated_version, lock=True)
