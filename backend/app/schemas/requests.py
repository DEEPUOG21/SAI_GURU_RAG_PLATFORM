from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=1, max_length=128)


class UserRequest(LoginRequest):
    password: str = Field(min_length=12, max_length=128)
    role: Literal["ADMIN", "MANAGER", "EMPLOYEE"] = "EMPLOYEE"


class SignupRequest(LoginRequest):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=12, max_length=128)
    workspace_name: str = Field(min_length=2, max_length=120)

    @field_validator("email", "workspace_name", mode="before")
    @classmethod
    def trim_fields(cls, value):
        return value.strip() if isinstance(value, str) else value


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=36)


class FeedbackRequest(BaseModel):
    query_id: str = Field(max_length=36)
    rating: Literal[-1, 1]
    comment: str = Field(default="", max_length=2000)
