"""Public AI contracts intentionally omit provider prompts and storage keys."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class FreeGenerationEligibility(BaseModel):
    free_request_status: Literal["available", "in_progress", "used"]
    free_request_available: bool

class GeneratedImage(BaseModel):
    id: int
    url: str


class GenerationResponse(BaseModel):
    id: int
    plan_id: int
    status: str
    created_at: datetime
    images: list[GeneratedImage]
