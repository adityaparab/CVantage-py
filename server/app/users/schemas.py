from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class UserSelfResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str = Field(alias="fullName")
    avatar_url: HttpUrl | None = Field(default=None, alias="avatarUrl")
    role: str
    email_verified: bool = Field(alias="emailVerified")
    resume_count: int = Field(alias="resumeCount", ge=0)
    analysis_count: int = Field(alias="analysisCount", ge=0)

    model_config = ConfigDict(populate_by_name=True)


class UserProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, alias="fullName", min_length=1, max_length=200)
    avatar_url: HttpUrl | None = Field(default=None, alias="avatarUrl")

    model_config = ConfigDict(populate_by_name=True)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(alias="currentPassword", min_length=1, max_length=256)
    new_password: str = Field(alias="newPassword", min_length=8, max_length=256)

    model_config = ConfigDict(populate_by_name=True)


class PasswordChangedResponse(BaseModel):
    status: str = Field(examples=["ok"])
