from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr = Field(examples=["candidate@example.com"])
    full_name: str = Field(
        alias="fullName",
        min_length=1,
        max_length=200,
        examples=["Jane Candidate"],
    )
    password: str = Field(min_length=8, max_length=256, examples=["StrongPass#2026"])


class LoginRequest(BaseModel):
    email: EmailStr = Field(examples=["candidate@example.com"])
    password: str = Field(min_length=1, max_length=256, examples=["StrongPass#2026"])


class AuthTokenResponse(BaseModel):
    access_token: str = Field(alias="accessToken", examples=["signed-token"])
    token_type: str = Field(alias="tokenType", examples=["bearer"])

    model_config = ConfigDict(populate_by_name=True)


class UserMeResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str = Field(alias="fullName")
    role: str

    model_config = ConfigDict(populate_by_name=True)


class LogoutResponse(BaseModel):
    status: str = Field(examples=["ok"])


class OAuthProvidersResponse(BaseModel):
    google: bool
    linkedin: bool


class OAuthAuthorizationResponse(BaseModel):
    authorization_url: str = Field(alias="authorizationUrl")

    model_config = ConfigDict(populate_by_name=True)
