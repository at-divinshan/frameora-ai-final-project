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
    google_auth_enabled: bool = False
    google_client_id: str = ""
    google_client_secret: str = field(default="", repr=False)
    google_redirect_uri: str = ""
    frontend_origin: str = ""
    google_completion_url: str = ""
    redis_url: str = field(default="", repr=False)
    oauth_transaction_key: str = field(default="", repr=False)
    oauth_cookie_secure: bool = True
    auth_version_enabled: bool = False
    password_management_enabled: bool = False
    profile_image_dir: str = str(Path(__file__).resolve().parents[2] / "private" / "profile-pictures")

    live_pose_vision_enabled: bool = False
    pollinations_enabled: bool = False
    pollinations_api_key: str = field(default="", repr=False)
    pollinations_image_model: str = "openai/gpt-image-1-mini"
    pollinations_timeout_seconds: int = 180
    pollinations_chat_model: str = "openai/gpt-5.4-nano"
    pollinations_chat_timeout_seconds: int = 45
    ai_image_dir: str = str(Path(__file__).resolve().parents[2] / "private" / "ai-images")

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
        google_auth_enabled=optional("GOOGLE_AUTH_ENABLED", "false").lower() == "true",
        google_client_id=optional("GOOGLE_CLIENT_ID", ""),
        google_client_secret=optional("GOOGLE_CLIENT_SECRET", ""),
        google_redirect_uri=optional("GOOGLE_REDIRECT_URI", ""),
        frontend_origin=optional("FRONTEND_ORIGIN", ""),
        google_completion_url=optional("GOOGLE_COMPLETION_URL", ""),
        redis_url=optional("REDIS_URL", ""),
        oauth_transaction_key=optional("OAUTH_TRANSACTION_KEY", ""),
        oauth_cookie_secure=optional("OAUTH_COOKIE_SECURE", "true").lower() != "false",
        auth_version_enabled=optional("AUTH_VERSION_ENABLED", "false").lower() == "true",
        password_management_enabled=optional("PASSWORD_MANAGEMENT_ENABLED", "false").lower() == "true",
        live_pose_vision_enabled=optional("LIVE_POSE_VISION_ENABLED", "false").lower() == "true",
        pollinations_enabled=optional("POLLINATIONS_ENABLED", "false").lower() == "true",
        pollinations_api_key=optional("POLLINATIONS_API_KEY", ""),
        pollinations_image_model=optional("POLLINATIONS_IMAGE_MODEL", Settings.pollinations_image_model),
        pollinations_timeout_seconds=positive_integer("POLLINATIONS_TIMEOUT_SECONDS", "180", 300),
        pollinations_chat_model=optional(
            "POLLINATIONS_CHAT_MODEL", Settings.pollinations_chat_model
        ),
        pollinations_chat_timeout_seconds=positive_integer(
            "POLLINATIONS_CHAT_TIMEOUT_SECONDS", "45", 180
        ),
        ai_image_dir=optional("AI_IMAGE_DIR", Settings.ai_image_dir),
        profile_image_dir=optional("PROFILE_IMAGE_DIR", Settings.profile_image_dir),
    )


settings = load_settings()
