"""Request and response contracts for personal photography plans."""

from datetime import datetime, timezone
import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator


def clean_text(value):
    if value is None:
        return None
    value = value.strip()
    if not value or any(unicodedata.category(char).startswith("C") for char in value):
        raise ValueError("Enter valid text.")
    return value


def parse_datetime(value):
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("Enter a valid date and time.") from None
    return value


def store_datetime_without_timezone(value):
    if value is not None and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def clean_optional_equipment_text(value):
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise ValueError("Enter valid text.")
    return value


class PhotographyEquipment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    device_type: Literal["Smartphone", "DSLR", "Mirrorless", "Other"] | None = None
    camera_model: StrictStr | None = Field(default=None, max_length=100)
    lens: StrictStr | None = Field(default=None, max_length=100)
    additional_equipment: StrictStr | None = Field(default=None, max_length=300)

    _clean_text = field_validator("camera_model", "lens", "additional_equipment")(
        clean_optional_equipment_text
    )


def validate_preferences(value):
    if isinstance(value, dict) and "equipment" in value and value["equipment"] is not None:
        equipment = PhotographyEquipment.model_validate(value["equipment"])
        return {**value, "equipment": equipment.model_dump(exclude_unset=True)}
    return value


class PhotographyPlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    photography_type: str = Field(min_length=1, max_length=50)
    people_count: int = Field(ge=1, le=10)
    environment: str = Field(min_length=1, max_length=20)
    location: str | None = Field(default=None, max_length=255)
    shoot_datetime: datetime | None = None
    preferences: Any | None = None

    _clean_text = field_validator("photography_type", "environment", "location")(clean_text)

    _parse_datetime = field_validator("shoot_datetime", mode="before")(parse_datetime)

    _store_datetime_without_timezone = field_validator("shoot_datetime")(store_datetime_without_timezone)
    _validate_preferences = field_validator("preferences")(validate_preferences)


class PhotographyPlanPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    photography_type: str | None = Field(default=None, min_length=1, max_length=50)
    people_count: int | None = Field(default=None, ge=1, le=10)
    environment: str | None = Field(default=None, min_length=1, max_length=20)
    location: str | None = Field(default=None, max_length=255)
    shoot_datetime: datetime | None = None
    preferences: Any | None = None

    @field_validator("photography_type", "environment", mode="before")
    @classmethod
    def require_non_null_text(cls, value):
        if value is None:
            raise ValueError("This field cannot be null.")
        return value

    _clean_text = field_validator("photography_type", "environment", "location")(clean_text)
    _parse_datetime = field_validator("shoot_datetime", mode="before")(parse_datetime)
    _store_datetime_without_timezone = field_validator("shoot_datetime")(store_datetime_without_timezone)
    _validate_preferences = field_validator("preferences")(validate_preferences)

    @field_validator("people_count", mode="before")
    @classmethod
    def require_non_null_people_count(cls, value):
        if value is None:
            raise ValueError("People count cannot be null.")
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