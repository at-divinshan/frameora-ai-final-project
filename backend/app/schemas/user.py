"""Explicit self-profile payloads; authentication identifiers are never serialized."""

import re
import unicodedata
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    name: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=20)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value):
        if value is None:
            raise ValueError("Name cannot be null.")
        if isinstance(value, str):
            value = value.strip()
            if any(unicodedata.category(char).startswith("C") for char in value):
                raise ValueError("Name contains unsupported characters.")
        return value

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, value):
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if not re.fullmatch(r"\+?[0-9 ()-]+", value) or not 7 <= len(re.sub(r"[^0-9]", "", value)) <= 15:
            raise ValueError("Use 7–15 digits, optionally with a leading +, spaces, parentheses or hyphens.")
        return value

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("Provide name or phone.")
        return self


class SelfProfile(BaseModel):
    id: str
    name: str
    phone: str | None
    email: str
    role: Literal["user", "owner", "admin"]
    is_verified: bool
    created_at: datetime
    profile_image: str | None
    has_password: bool
    google_linked: bool


class PrivacySettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    profile_visibility: Literal["public", "private"] = "private"
    photography_plans_default: Literal["public", "private"] = "private"
    ai_images_default: Literal["public", "private"] = "private"


class PrivacyUpdate(PrivacySettings):
    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one privacy setting.")
        return self


class PublicProfile(BaseModel):
    name: str
    profile_image: str | None
