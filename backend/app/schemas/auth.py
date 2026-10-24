"""Public authentication payloads; database roles are mapped by the service."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class AuthCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128, repr=False)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class LoginRequest(AuthCredentials):
    remember_me: bool = False


class RegisterRequest(AuthCredentials):
    name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8, max_length=128, repr=False)
    role: Literal["user", "owner"]
    confirm_password: str = Field(min_length=8, max_length=128, repr=False)
    accept_terms: Literal[True]

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, value, info):
        if value != info.data.get("password"):
            raise ValueError("Passwords do not match.")
        return value


class AuthUser(BaseModel):
    id: str
    name: str
    email: str
    role: Literal["user", "owner", "admin"]


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: AuthUser
