"""Server-side authentication and reusable role authorization dependencies."""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.core.security import auth_versions_enabled, decode_access_claims
from app.core.auth_version import check_version
from app.database.connection import get_db
from app.models.user import User
from app.repositories.user_repository import find_by_id
from app.services.auth_service import SUPPORTED_ROLES, require_single_admin


bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=401,
        detail="Your session is invalid or has expired. Please sign in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    claims = decode_access_claims(credentials.credentials) if auth_versions_enabled() else None
    subject = claims["sub"] if claims is not None else decode_access_token(credentials.credentials)
    if not subject.isascii() or not subject.isdecimal() or len(subject) > 10:
        raise unauthorized
    user_id = int(subject)
    if not 1 <= user_id <= 2147483647:
        raise unauthorized
    user = find_by_id(db, user_id)
    if user is None or user.role not in SUPPORTED_ROLES:
        raise unauthorized
    require_single_admin(db, user)
    if claims is not None:
        check_version(db, user, claims["auth_version"])
        user._authenticated_version = claims["auth_version"]
    return user


def require_roles(*roles: str):
    """Authorize against the current database role, never a client-supplied role."""
    def authorize(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="You do not have access to this resource.")
        return user
    return authorize
