"""Request and response contracts for personal photography plans."""

from datetime import datetime, timezone
import unicodedata
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PhotographyPlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    photography_type: str = Field(min_length=1, max_length=50)
    people_count: int = Field(ge=1, le=10)
    environment: str = Field(min_length=1, max_length=20)
    location: str | None = Field(default=None, max_length=255)
    shoot_datetime: datetime | None = None
    preferences: Any | None = None

    @field_validator("photography_type", "environment", "location")
    @classmethod
    def clean_text(cls, value):
        if value is None:
            return None
        value = value.strip()
        if not value or any(unicodedata.category(char).startswith("C") for char in value):
            raise ValueError("Enter valid text.")
        return value

    @field_validator("shoot_datetime", mode="before")
    @classmethod
    def parse_datetime(cls, value):
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError("Enter a valid date and time.") from None
        return value

    @field_validator("shoot_datetime")
    @classmethod
    def store_datetime_without_timezone(cls, value):
        if value is not None and value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value


class PhotographyPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int | None
    photography_type: str
    people_count: int
    environment: str
    location: str | None
    shoot_datetime: datetime | None
    preferences: Any | None
    created_at: datetime