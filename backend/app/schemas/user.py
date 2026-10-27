import re
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator


class UserBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Full name of user")
    email: str = Field(..., description="Unique email address")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be blank or whitespace only")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(email_regex, v):
            raise ValueError("Invalid email format")
        return v


class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
