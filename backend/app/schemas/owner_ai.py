"""Separate owner contracts; normal-user responses remain unchanged."""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel
from pydantic import Field, model_validator
from app.schemas.ai import GenerationResponse


class OwnerGenerationPreferences(BaseModel):
    background_mode: Literal['same', 'different', 'custom'] = 'same'
    pose_mode: Literal['high', 'natural', 'custom'] = 'natural'
    camera_angle_mode: Literal['mixed', 'eye', 'cinematic', 'custom'] = 'mixed'
    outfit_mode: Literal['same', 'different', 'custom'] = 'same'
    dress_colors: str = Field(default='', max_length=200)
    outfit_details: str = Field(default='', max_length=1000)
    additional_instructions: str = Field(default='', max_length=2000)

    @model_validator(mode='after')
    def require_custom_instructions(self):
        instructions = self.additional_instructions.strip()
        if self.background_mode == 'custom' and not instructions:
            raise ValueError('Add additional instructions describing the custom background.')
        if self.pose_mode == 'custom' and not instructions:
            raise ValueError('Add additional instructions describing the custom poses.')
        if self.camera_angle_mode == 'custom' and not instructions:
            raise ValueError('Add additional instructions describing the custom camera angles.')
        if self.outfit_mode == 'custom' and not self.outfit_details.strip():
            raise ValueError('Add outfit details when using a custom outfit.')
        return self


class OwnerEntitlements(BaseModel):
    plan: Literal['basic', 'trial', 'pro'] | None
    status: Literal['active', 'unavailable']
    previous_subscription_expired: bool
    source_status: Literal['active', 'expired', 'unavailable']
    subscription_id: int | None
    subscription_start: datetime | None
    subscription_end: datetime | None
    remaining_credits: int
    period_start: datetime | None
    period_end: datetime | None
    monthly_renewal_due: bool
    generation_allowed: bool
    batch_cost: int
    reason: str | None
    trial_available: bool
    max_projects: int
    max_share_links: int


class OwnerGenerationResponse(GenerationResponse):
    remaining_credits: int
    reserved_credits: int
    charged_credits: int
    recover_after: datetime | None
    replayed: bool
