"""Owner-only studio contracts, separate from personal/public profile schemas."""

from datetime import datetime
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StudioUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    studio_name: str = Field(min_length=2, max_length=150)
    studio_phone: str = Field(min_length=7, max_length=20)
    studio_address: str = Field(min_length=2, max_length=255)
    studio_city: str = Field(min_length=2, max_length=100)
    studio_description: str | None = Field(default=None, max_length=2000)

    @field_validator("*", mode="before")
    @classmethod
    def clean_text(cls, value, info):
        if isinstance(value, str):
            value = value.strip()
            allowed = "\n\t" if info.field_name == "studio_description" else ""
            if any(unicodedata.category(char).startswith("C") and char not in allowed for char in value):
                raise ValueError("Unsupported characters.")
            if info.field_name == "studio_description" and not value:
                return None
        return value

    @field_validator("studio_phone")
    @classmethod
    def valid_phone(cls, value):
        if not re.fullmatch(r"\+?[0-9 ()-]+", value) or not 7 <= len(re.sub(r"[^0-9]", "", value)) <= 15:
            raise ValueError("Use 7–15 digits, optionally with a leading +, spaces, parentheses or hyphens.")
        return value


class StudioDetails(BaseModel):
    studio_name: str | None
    studio_phone: str | None
    studio_address: str | None
    studio_city: str | None
    studio_description: str | None


class OwnerOnboarding(BaseModel):
    onboarding_status: Literal["pending_studio", "pending_plan", "completed"]
    onboarding_completed_at: datetime | None
    next_step: Literal["studio_setup", "subscription_selection", "dashboard"]
    studio: StudioDetails | None
