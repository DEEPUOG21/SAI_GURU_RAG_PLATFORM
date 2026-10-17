from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=1, max_length=128)


class UserRequest(LoginRequest):
    password: str = Field(min_length=12, max_length=128)
    role: Literal["ADMIN", "MANAGER", "EMPLOYEE"] = "EMPLOYEE"


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=36)


class FeedbackRequest(BaseModel):
    query_id: str = Field(max_length=36)
    rating: Literal[-1, 1]
    comment: str = Field(default="", max_length=2000)
