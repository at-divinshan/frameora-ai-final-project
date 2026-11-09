"""Studio Owner customer-project API contracts for the current database schema."""

import unicodedata
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _clean_text(value, *, allow_lines=False):
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    value = value.strip()
    allowed = "\n\r\t" if allow_lines else ""
    if any(
        unicodedata.category(char).startswith("C") and char not in allowed
        for char in value
    ):
        raise ValueError("Unsupported characters.")
    return value or None


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    customer_name: str = Field(min_length=1, max_length=100)
    project_title: str | None = Field(default=None, max_length=150)
    customer_contact: str | None = Field(default=None, max_length=100)
    event_type: str | None = Field(default=None, max_length=100)
    shoot_location: str | None = Field(default=None, max_length=255)
    shooting_date: date | None = Field(default=None, strict=False)
    requirements: str | None = None

    @field_validator(
        "customer_name", "project_title", "customer_contact", "event_type",
        "shoot_location", mode="before"
    )
    @classmethod
    def clean_short_text(cls, value):
        return _clean_text(value)

    @field_validator("requirements", mode="before")
    @classmethod
    def clean_requirements(cls, value):
        return _clean_text(value, allow_lines=True)

    @field_validator("customer_name")
    @classmethod
    def require_customer_name(cls, value):
        if not value:
            raise ValueError("Customer name is required.")
        return value

    @field_validator("requirements")
    @classmethod
    def fit_requirements_column(cls, value):
        if value is not None and len(value.encode("utf-8")) > 65535:
            raise ValueError("Requirements are too long.")
        return value


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    customer_name: str | None = Field(default=None, min_length=1, max_length=100)
    project_title: str | None = Field(default=None, max_length=150)
    customer_contact: str | None = Field(default=None, max_length=100)
    event_type: str | None = Field(default=None, max_length=100)
    shoot_location: str | None = Field(default=None, max_length=255)
    shooting_date: date | None = Field(default=None, strict=False)
    requirements: str | None = None

    @field_validator(
        "customer_name", "project_title", "customer_contact", "event_type",
        "shoot_location", mode="before"
    )
    @classmethod
    def clean_short_text(cls, value):
        return _clean_text(value)

    @field_validator("requirements", mode="before")
    @classmethod
    def clean_requirements(cls, value):
        return _clean_text(value, allow_lines=True)

    @field_validator("requirements")
    @classmethod
    def fit_requirements_column(cls, value):
        if value is not None and len(value.encode("utf-8")) > 65535:
            raise ValueError("Requirements are too long.")
        return value

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("At least one project field is required.")
        if "customer_name" in self.model_fields_set and not self.customer_name:
            raise ValueError("Customer name is required.")
        return self


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_name: str
    project_title: str | None
    customer_contact: str | None
    event_type: str | None
    shoot_location: str | None
    shooting_date: date | None
    requirements: str | None
    created_at: datetime
    is_editable: bool