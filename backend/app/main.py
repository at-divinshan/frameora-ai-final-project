"""FastAPI application, local frontend access, and health endpoints."""

from contextlib import asynccontextmanager
import logging
import re

from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.models.ai_generation import AIGeneration
from app.middleware.ai_upload_limit import AIUploadLimit
from app.core.config import settings
from app.database.connection import check_database_connection, engine
from app.routers.auth import router as auth_router
from app.routers.admin import router as admin_router
from app.routers.google_auth import router as google_auth_router
from app.routers.users import router as users_router
from app.routers.owner import router as owner_router
from app.routers.subscriptions import router as subscriptions_router
from app.routers.plans import router as plans_router
from app.routers.ai import router as ai_router
from app.services.oauth_transaction_store import close_store
from app.services.rate_limit_service import close_rate_limits


class GoogleAccessLogFilter(logging.Filter):
    """Uvicorn includes the raw query string (and authorization code) in access logs."""
    def filter(self, record):
        return "/auth/google" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(GoogleAccessLogFilter())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        close_store()
        close_rate_limits()
        engine.dispose()


app = FastAPI(title="Frameora AI", lifespan=lifespan)


@app.middleware("http")
async def picture_response_protection(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/ai/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.startswith("/users/") and request.url.path.rstrip("/").endswith("/picture"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cross-Origin-Resource-Policy"] = "same-site"
    return response


@app.middleware("http")
async def google_response_protection(request, call_next):
    if not request.url.path.startswith("/auth/google"):
        return await call_next(request)
    try:
        response = await call_next(request)
    except Exception:
        # Do not propagate provider/Redis exceptions into server traceback logging.
        response = JSONResponse(status_code=503, content={"detail": "Google authentication is unavailable. Please try again later."})
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


app.add_middleware(AIUploadLimit)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys((*settings.cors_origins, *(
        (settings.frontend_origin,) if settings.frontend_origin else ()
    )))),
    allow_credentials=settings.google_auth_enabled,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(google_auth_router)
app.include_router(users_router)
app.include_router(owner_router)
app.include_router(subscriptions_router)
app.include_router(plans_router)
app.include_router(ai_router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    # FastAPI's default validation details can include submitted passwords.
    errors = [
        {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request, exc):
    original = getattr(exc, "orig", None)
    original_args = getattr(original, "args", ())
    raw_code = original_args[0] if original_args else None
    driver_code = raw_code if isinstance(raw_code, int) else (
        raw_code if isinstance(raw_code, str) and raw_code.isdecimal() else None
    )
    raw_sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    sqlstate = raw_sqlstate if isinstance(raw_sqlstate, str) and re.fullmatch(r"[A-Z0-9]{5}", raw_sqlstate) else None
    logger.error(
        "Database operation failed: exception_class=%s driver_class=%s driver_code=%s sqlstate=%s",
        type(exc).__name__,
        type(original).__name__ if original is not None else "unavailable",
        driver_code if driver_code is not None else "unavailable",
        sqlstate if sqlstate is not None else "unavailable",
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "The database is temporarily unavailable. Please try again later."},
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred. Please try again later."},
    )


@app.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db", tags=["Health"])
def database_health() -> dict[str, str]:
    error_message = (
        "Database connectivity check failed. Check the MySQL service, network "
        "access, and backend database configuration."
    )
    try:
        connected = check_database_connection()
    except SQLAlchemyError:
        # Never return driver exceptions, connection URLs, or credentials to clients.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_message,
        ) from None

    if not connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_message,
        )
    return {"status": "ok", "database": "connected"}
