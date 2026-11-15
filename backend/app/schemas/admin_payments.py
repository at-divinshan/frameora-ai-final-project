from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator

class PaymentFilters(BaseModel):
    role: Literal['user','owner'] | None = None
    plan: str | None = Field(default=None,max_length=30)
    status: str | None = Field(default=None,max_length=30)
    date_from: date | None = None
    date_to: date | None = None
    page: int = Field(default=1,ge=1,le=10000)

    @model_validator(mode='after')
    def dates(self):
        if self.date_to and self.date_to == date.max: raise ValueError('End date is out of range.')
        if self.date_from and self.date_to and self.date_from > self.date_to: raise ValueError('Start date must not follow end date.')
        return self
