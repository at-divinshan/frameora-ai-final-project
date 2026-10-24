"""Registration and login for user, owner, and existing admin accounts."""

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token, dummy_password_hash, hash_password,
    require_jwt_configuration, verify_password,
)
from app.models.user import User
from app.repositories.user_repository import add_user, find_by_email
from app.schemas.auth import AuthUser, LoginRequest, RegisterRequest, TokenResponse


SUPPORTED_ROLES = {"user", "owner", "admin"}
PUBLIC_ROLES = {"user", "owner"}


def require_single_admin(db: Session, user: User) -> None:
    """Fail closed for Admin access; never create or modify accounts."""
    if user.role == "admin":
        admin_count = db.scalar(select(func.count()).select_from(User).where(User.role == "admin"))
        if admin_count != 1:
            raise HTTPException(
                status_code=403,
                detail="Admin access is unavailable. Contact the application administrator.",
            )


def public_user(user: User) -> AuthUser:
    return AuthUser(id=str(user.id), name=user.name, email=user.email, role=user.role)


def register(db: Session, data: RegisterRequest) -> AuthUser:
    if data.role not in PUBLIC_ROLES:
        raise HTTPException(status_code=403, detail="This account type cannot be publicly registered.")
    if find_by_email(db, str(data.email)) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    password_hash = hash_password(data.password)
    try:
        user = add_user(
            db, name=data.name, email=str(data.email), password_hash=password_hash, role=data.role,
        )
        result = public_user(user)
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        # The existing unique email index also handles simultaneous registration requests.
        if getattr(exc.orig, "args", (None,))[0] == 1062:
            raise HTTPException(status_code=409, detail="An account with this email already exists.") from None
        raise


def login(db: Session, data: LoginRequest) -> TokenResponse:
    require_jwt_configuration()
    user = find_by_email(db, str(data.email))
    stored_hash = user.password_hash if user else dummy_password_hash()
    valid_password = verify_password(data.password, stored_hash)
    if user is None or not valid_password or user.role not in SUPPORTED_ROLES:
        raise HTTPException(
            status_code=401, detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    require_single_admin(db, user)
    # Login never changes existing account records or hashes.
    token, expires_in = create_access_token(str(user.id), data.remember_me)
    return TokenResponse(access_token=token, expires_in=expires_in, user=public_user(user))
