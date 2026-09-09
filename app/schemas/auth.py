import re
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Complexity: at least 1 uppercase, 1 lowercase, 1 digit, 1 special character
PASSWORD_REGEX = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&_\-#^~`+=])[A-Za-z\d@$!%*?&_\-#^~`+=]{8,128}$"
)


class UserRegister(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Must be 8-128 chars, include uppercase, lowercase, number, and special character.",
    )
    full_name: str = Field(..., min_length=1, max_length=150)
    target_language: str = Field(..., min_length=2, max_length=50, examples=["Spanish"])
    native_language: str = Field(..., min_length=2, max_length=50, examples=["English"])

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, value: str) -> str:
        if not PASSWORD_REGEX.match(value):
            raise ValueError(
                "Password must contain at least one uppercase letter, "
                "one lowercase letter, one numeric digit, and one special character."
            )
        return value


class UserLogin(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(..., description="Access token expiration window in seconds")


class TokenRefreshRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    refresh_token: str = Field(..., min_length=1, description="Valid refresh token with jti claim")


class TokenPayload(BaseModel):
    """Decoded internal JWT claim payload."""
    sub: UUID | str
    type: Literal["access", "refresh"]
    exp: int
    iat: int
    nbf: int | None = None
    iss: str | None = None
    jti: str | None = None