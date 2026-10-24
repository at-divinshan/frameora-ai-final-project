"""FastAPI application, local frontend access, and health endpoints."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.database.connection import check_database_connection, engine
from app.routers.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(title="Frameora AI", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth_router)


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
