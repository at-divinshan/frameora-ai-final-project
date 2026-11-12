from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool
class UserFilters(BaseModel):
    model_config=ConfigDict(extra='forbid')
    q:str=Field(default='',max_length=100)
    role:Literal['user','owner']|None=None
    status:Literal['active','inactive']|None=None
    page:int=Field(default=1,ge=1,le=10000)
    page_size:int=Field(default=20,ge=1,le=50)
class StatusChange(BaseModel):
    model_config=ConfigDict(extra='forbid')
    is_active:StrictBool
    expected_version:int=Field(ge=0,strict=True)
