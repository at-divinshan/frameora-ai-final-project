"""FastAPI application, local frontend access, and health endpoints."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.database.connection import check_database_connection, engine
from app.routers.auth import router as auth_router
from app.routers.google_auth import router as google_auth_router
from app.services.oauth_transaction_store import close_store


class GoogleAccessLogFilter(logging.Filter):
    """Uvicorn includes the raw query string (and authorization code) in access logs."""
    def filter(self, record):
        return "/auth/google" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(GoogleAccessLogFilter())


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        close_store()
        engine.dispose()


app = FastAPI(title="Frameora AI", lifespan=lifespan)


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


app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys((*settings.cors_origins, *(
        (settings.frontend_origin,) if settings.frontend_origin else ()
    )))),
    allow_credentials=settings.google_auth_enabled,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth_router)
app.include_router(google_auth_router)


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
