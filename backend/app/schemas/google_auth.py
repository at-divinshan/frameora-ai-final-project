"""Google payloads never accept client-supplied provider identities or roles for login."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class GoogleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class GoogleStart(GoogleRequest):
    remember_me: StrictBool = False


class GoogleRegistration(GoogleRequest):
    name: str = Field(min_length=2, max_length=100)
    role: Literal["user", "owner"]
    accept_terms: StrictBool

    @field_validator("accept_terms")
    @classmethod
    def terms_required(cls, value):
        if value is not True:
            raise ValueError("Terms acceptance is required.")
        return value

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class GoogleLinkConsent(GoogleRequest):
    consent: StrictBool

    @field_validator("consent")
    @classmethod
    def consent_required(cls, value):
        if value is not True:
            raise ValueError("Explicit linking consent is required.")
        return value


class GoogleLinkStart(GoogleLinkConsent):
    password: str = Field(min_length=1, max_length=128, repr=False)
