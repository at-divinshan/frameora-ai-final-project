"""Strict contract for photography plan suggestions."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


Suggestion = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=240),
]
SuggestionList = list[Suggestion]


class PhotographySuggestions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    pose_suggestions: SuggestionList = Field(min_length=3, max_length=3)
    camera_angles: SuggestionList = Field(min_length=3, max_length=3)
    lighting_tips: SuggestionList = Field(min_length=3, max_length=3)
    camera_settings: SuggestionList = Field(min_length=3, max_length=3)
    composition_tips: SuggestionList = Field(min_length=3, max_length=3)
    photography_tools: SuggestionList = Field(min_length=3, max_length=3)
