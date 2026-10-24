"""Queries against the existing User table; transactions belong to the service."""

from sqlalchemy import select
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
