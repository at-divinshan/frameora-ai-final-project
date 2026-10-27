"""Queries against the existing User table; transactions belong to the service."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.user import User


def find_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def find_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def add_user(db: Session, *, name: str, email: str, password_hash: str, role: str) -> User:
    user = User(name=name, email=email, password_hash=password_hash, role=role)
    db.add(user)
    db.flush()
    return user


def find_by_google_sub(db: Session, subject: bytes) -> User | None:
    return db.scalar(select(User).where(User.google_sub == subject))


def add_google_user(db: Session, *, name: str, email: str, subject: bytes, role: str) -> User:
    user = User(name=name, email=email, password_hash=None, google_sub=subject, role=role)
    db.add(user)
    db.flush()
    return user


def link_google_identity(db: Session, *, user_id: int, subject: bytes, password_hash: str) -> bool:
    """Never replace a link or link an account whose password/role has changed."""
    result = db.execute(
        update(User).where(
            User.id == user_id, User.role.in_(("user", "owner")),
            User.google_sub.is_(None), User.password_hash == password_hash,
        ).values(google_sub=subject),
        execution_options={"synchronize_session": False},
    )
    return result.rowcount == 1
