from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.ai import ImageGuidance


class ShareLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    generation_id: int = Field(gt=0)
    expires_at: datetime | None = None

    @field_validator("expires_at", mode="before")
    @classmethod
    def parse_expiry(cls, value):
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError("Enter a valid expiration date and time.") from None
        return value

    @field_validator("expires_at")
    @classmethod
    def normalize_expiry(cls, value):
        if value is not None and value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value


class ShareLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int | None
    generation_id: int
    is_active: bool
    expires_at: datetime | None
    created_at: datetime


class ShareLinkCreated(ShareLinkRead):
    token: str


class SharedImage(BaseModel):
    id: int
    guidance: ImageGuidance | None


class SharedPhase(BaseModel):
    generation_id: int
    phase_number: int | None = None
    images: list[SharedImage]


class SharedGeneration(BaseModel):
    phases: list[SharedPhase] = Field(default_factory=list)
    project_id: int
    generation_id: int
    images: list[SharedImage]