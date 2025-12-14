"""User ORM and Pydantic models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from enum import Enum

from infrastructure.db.mysql_client import Base


class User(Base):
    """SQLAlchemy ORM model representing an authenticated user."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    phone_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DBUser(BaseModel):
    """Internal representation of user data including hashed password."""

    id: str
    username: str
    phone: str
    password_hash: str = Field(repr=False)
    is_active: bool
    phone_verified_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


class SmsScene(str, Enum):
    """Business scenarios for SMS verification codes."""

    REGISTER = "register"
    LOGIN = "login"
    ACCOUNT_DELETE = "account_delete"


class SmsSendRequest(BaseModel):
    """Request body for sending an SMS verification code."""

    phone: str = Field(min_length=6, max_length=20)
    scene: SmsScene

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return value.strip()


class SmsVerifyRequest(BaseModel):
    """Request body for verifying an SMS verification code."""

    phone: str = Field(min_length=6, max_length=20)
    code: str = Field(min_length=4, max_length=10)
    scene: SmsScene

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return value.strip()


class TokenPair(BaseModel):
    """Access and refresh token pair."""

    token_type: str = Field(default="bearer", pattern=r"^[A-Za-z0-9_\-]+$")
    access_token: str
    refresh_token: str
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime


class SmsVerificationResponse(BaseModel):
    """Result of verifying an SMS code."""

    outcome: str = Field(pattern="^(login|ticket)$")
    token_pair: Optional[TokenPair] = None
    verification_ticket: Optional[str] = None
    ticket_expires_at: Optional[datetime] = None


class UserResponse(BaseModel):
    """Public facing user payload returned by APIs."""

    id: str
    username: str
    phone: str
    preferred_name: str = ""
    is_active: bool
    phone_verified_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RefreshTokenRequest(BaseModel):
    """Request body containing a refresh token."""

    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    """Request body for logging out a session."""

    refresh_token: str = Field(min_length=1)


class RegisterRequest(BaseModel):
    """Request body for registering a new user (phone required)."""

    username: str = Field(min_length=3, max_length=50)
    phone: str = Field(min_length=6, max_length=20)
    password: str = Field(min_length=6, max_length=128)
    verification_ticket: str = Field(min_length=1)

    @field_validator("username")
    @classmethod
    def strip_username(cls, value: str) -> str:
        return value.strip()

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def ensure_password_complexity(self) -> "RegisterRequest":
        pwd = self.password
        if not any(ch.isalpha() for ch in pwd) or not any(not ch.isalnum() for ch in pwd):
            raise ValueError("密码需包含字母或数字中的至少一种，且至少包含一个符号。")
        return self


class PasswordLoginRequest(BaseModel):
    """Request body for password-based login."""

    identifier: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=6, max_length=128)


class AccountDeleteRequest(BaseModel):
    """Request body for deleting (deactivating) an account."""

    password: Optional[str] = Field(default=None, min_length=0, max_length=128)
    verification_ticket: Optional[str] = Field(default=None, min_length=1)

    @field_validator("password")
    @classmethod
    def blank_password_to_none(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if value.strip() == "":
            return None
        return value

    @model_validator(mode="after")
    def ensure_one_factor(self) -> "AccountDeleteRequest":
        if not (self.password or self.verification_ticket):
            raise ValueError("需提供密码或短信验证码凭证之一。")
        return self
