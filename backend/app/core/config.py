"""Backend settings loaded without exposing database credentials."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import URL


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str = field(repr=False)
    jwt_secret_key: str = field(default="", repr=False)
    jwt_access_token_expire_minutes: int = 30
    jwt_remember_me_expire_days: int = 7
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

    @property
    def database_url(self) -> URL:
        # URL.create handles special characters in credentials without interpolation.
        return URL.create(
            drivername="mysql+pymysql",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={"charset": "utf8mb4"},
        )


def load_settings() -> Settings:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    # Keep literal password characters intact; environment variables take precedence.
    file_values = dotenv_values(env_path, interpolate=False)
    names = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
    values = {name: os.environ.get(name, file_values.get(name)) for name in names}
    missing = [name for name, value in values.items() if value is None or value == ""]
    if missing:
        raise RuntimeError(
            "Missing database configuration: " + ", ".join(missing)
            + ". Check backend/.env or the environment."
        )

    try:
        port = int(values["DB_PORT"])
    except (TypeError, ValueError):
        raise RuntimeError("DB_PORT must be an integer between 1 and 65535.") from None
    if not 1 <= port <= 65535:
        raise RuntimeError("DB_PORT must be an integer between 1 and 65535.")

    def optional(name: str, default: str) -> str:
        return os.environ.get(name, file_values.get(name) or default)

    def positive_integer(name: str, default: str, maximum: int) -> int:
        try:
            value = int(optional(name, default))
        except ValueError:
            raise RuntimeError(f"{name} must be a positive integer.") from None
        if not 1 <= value <= maximum:
            raise RuntimeError(f"{name} must be between 1 and {maximum}.")
        return value

    return Settings(
        db_host=values["DB_HOST"],
        db_port=port,
        db_name=values["DB_NAME"],
        db_user=values["DB_USER"],
        db_password=values["DB_PASSWORD"],
        jwt_secret_key=optional("JWT_SECRET_KEY", ""),
        jwt_access_token_expire_minutes=positive_integer(
            "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30", 1440
        ),
        jwt_remember_me_expire_days=positive_integer(
            "JWT_REMEMBER_ME_EXPIRE_DAYS", "7", 30
        ),
    )


settings = load_settings()
