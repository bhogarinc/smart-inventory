"""
Authentication schemas for login, token, and registration.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from src.models.user import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    sub: str
    role: UserRole
    exp: datetime
    iat: datetime


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: UserRole = UserRole.WAREHOUSE_MANAGER
    phone: Optional[str] = Field(None, max_length=20)
    assigned_warehouse_id: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8, max_length=128)
