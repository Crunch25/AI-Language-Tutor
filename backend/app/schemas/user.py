from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None
    native_language: str = Field(..., min_length=2, max_length=50)
    target_language: str = Field(..., min_length=2, max_length=50)


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    is_superuser: bool = False
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    native_language: str | None = Field(default=None, min_length=2, max_length=50)
    target_language: str | None = Field(default=None, min_length=2, max_length=50)
    is_active: bool | None = None