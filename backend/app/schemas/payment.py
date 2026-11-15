"""Server-owned checkout inputs; prices, credits and account IDs are never accepted."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class OwnerCheckoutRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    plan_code: Literal['starter', 'growth', 'unlimited']
    idempotency_key: str = Field(min_length=16, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')

class UserCheckoutRequest(OwnerCheckoutRequest):
    plan_code: Literal['starter', 'pro']
