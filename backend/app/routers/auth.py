"""Public register/login endpoints and authenticated session lookup."""

from fastapi import APIRouter, Depends, Response, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, bearer
from app.database.connection import get_db
from app.models.user import User
from app.schemas.auth import AuthUser, LoginRequest, RegisterRequest, TokenResponse
from app.services import auth_service
from app.services import password_service
from app.services.rate_limit_service import limit_password_attempt, limit_public_auth
from app.core.security import require_password_management
from app.schemas.auth import PasswordChange, RegistrationResponse


def no_store(response: Response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


router = APIRouter(prefix="/auth", tags=["Authentication"], dependencies=[Depends(no_store)])


@router.post("/register", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    limit_public_auth("register", str(data.email), request.client.host if request.client else "unknown")
    return auth_service.register(db, data)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    limit_public_auth("login", str(data.email), request.client.host if request.client else "unknown")
    return auth_service.login(db, data)


@router.get("/me", response_model=AuthUser)
def me(user: User = Depends(get_current_user)):
    return auth_service.public_user(user)


@router.post("/password/change", dependencies=[Depends(require_password_management)])
def change_password(data: PasswordChange, request: Request,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    limit_password_attempt("change", user.id, request.client.host if request.client else "unknown")
    return password_service.change_password(db, user, data)


@router.get("/password/capabilities")
def password_capabilities(user: User = Depends(get_current_user)):
    from app.core.config import settings
    enabled = settings.auth_version_enabled and settings.password_management_enabled
    return {"change_password": enabled and user.password_hash is not None,
            "google_password_setup": enabled and settings.google_auth_enabled and user.role in ("user", "owner") and user.password_hash is None and user.google_sub is not None}


@router.post("/logout", status_code=204)
def logout(user: User = Depends(get_current_user),
           credentials=Depends(bearer)):
    from app.core.security import decode_access_claims
    from app.services.session_revocation import revoke
    revoke(credentials.credentials, decode_access_claims(credentials.credentials))
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
