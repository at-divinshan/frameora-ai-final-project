"""Public register/login endpoints and authenticated session lookup."""

from fastapi import APIRouter, Depends, Response, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.schemas.auth import AuthUser, LoginRequest, RegisterRequest, TokenResponse
from app.services import auth_service
from app.services import password_service
from app.services.rate_limit_service import limit_password_attempt
from app.core.security import require_password_management
from app.schemas.auth import PasswordChange


def no_store(response: Response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


router = APIRouter(prefix="/auth", tags=["Authentication"], dependencies=[Depends(no_store)])


@router.post("/register", response_model=AuthUser, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    return auth_service.register(db, data)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.login(db, data)


@router.get("/me", response_model=AuthUser)
def me(user: User = Depends(get_current_user)):
    return auth_service.public_user(user)


@router.post("/password/change", dependencies=[Depends(require_password_management)])
def change_password(data: PasswordChange, request: Request,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    limit_password_attempt("change", user.id, request.client.host if request.client else "unknown")
    return password_service.change_password(db, user, data)
