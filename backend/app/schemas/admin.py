"""Explicit allowlists for private, read-only administrator responses."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.owner import StudioDetails
from app.schemas.subscription import Entitlements

class OwnerFilters(BaseModel):
    model_config = ConfigDict(extra='forbid')
    q: str = Field(default='', max_length=100)
    onboarding: Literal['pending_studio', 'pending_plan', 'completed'] | None = None
    page: int = Field(default=1, ge=1, le=10000)
    page_size: int = Field(default=20, ge=1, le=50)

class AdminSummary(BaseModel):
    normal_users: int
    studio_owners: int

class OwnerRecord(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime
    onboarding_status: str
    studio: StudioDetails | None

class OwnerPage(BaseModel):
    items: list[OwnerRecord]
    total: int
    page: int
    page_size: int

class OwnerDetail(OwnerRecord):
    photo_available: bool
    has_photo: bool
    subscription_status: Literal['active', 'not_selected', 'unavailable']
    subscription: Entitlements | None
