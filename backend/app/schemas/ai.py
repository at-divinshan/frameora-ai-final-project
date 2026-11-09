"""Public AI contracts intentionally omit provider prompts and storage keys."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FreeGenerationEligibility(BaseModel):
    free_request_status: Literal["available", "in_progress", "used"]
    free_request_available: bool

class CameraSetupGuide(BaseModel):
    camera_height: str
    camera_distance: str
    camera_direction_and_tilt: str
    suggested_lens_or_zoom: str
    lighting_direction: str
    subject_position: str
    steps: list[str] = Field(min_length=5, max_length=7)


class ImageGuidance(BaseModel):
    pose_name: str
    camera_angle: str
    shot_type: str
    camera_position: str
    instructions: str
    camera_setup: CameraSetupGuide | None = None


class GeneratedImage(BaseModel):
    id: int
    url: str
    guidance: ImageGuidance | None = None


class GenerationResponse(BaseModel):
    id: int
    plan_id: int
    status: str
    created_at: datetime
    images: list[GeneratedImage]
