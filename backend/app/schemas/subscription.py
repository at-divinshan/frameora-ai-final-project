from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class ActivationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, hide_input_in_errors=True)
    idempotency_key: str = Field(min_length=16, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')

class Entitlements(BaseModel):
    plan: Literal['basic', 'trial'] | None
    remaining_credits: int
    trial_available: bool
    period_start: datetime | None
    period_end: datetime | None
