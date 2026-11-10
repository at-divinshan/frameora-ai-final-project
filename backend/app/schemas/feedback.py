from typing import Literal
from uuid import UUID
import unicodedata
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class CommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_key: UUID
    comment: str = Field(min_length=1, max_length=2000, strict=True)

    @field_validator("comment")
    @classmethod
    def clean_comment(cls, value):
        value = value.strip()
        if not value or any(unicodedata.category(c).startswith('C') and c not in '\n\t' for c in value):
            raise ValueError("Enter plain text without control characters.")
        return value

class FeedbackUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["pending", "in_progress", "resolved"] | None = None
    revised_asset_id: int | None = Field(default=None, gt=0, strict=True)

    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set or ('status' in self.model_fields_set and self.status is None):
            raise ValueError("Choose a status or revision image.")
        return self
