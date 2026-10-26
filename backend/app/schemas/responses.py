"""Public response contracts; provider traces remain explicitly structured JSON."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"]
    expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str
    role: Literal["ADMIN", "MANAGER", "EMPLOYEE"]


class ProfileResponse(UserResponse):
    tenant: str


class DocumentResponse(BaseModel):
    id: str
    name: str
    version: int
    status: str
    size: int
    min_role: int
    error: str | None
    created_at: datetime
    updated_at: datetime


class ChunkPreview(BaseModel):
    id: str
    text: str
    page: int | None
    section: str


class DocumentDetail(DocumentResponse):
    chunks: list[ChunkPreview]
    chunk_count: int


class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: datetime


class MessageResponse(BaseModel):
    id: str
    role: str
    query_id: str | None
    content: str
    citations: list[dict[str, Any]]
    grounding: str | None
    guardrails: list[dict[str, Any]] = Field(default_factory=list)


class EvaluationResponse(BaseModel):
    id: str
    status: str
    created_at: datetime
    results: dict[str, Any]


class DashboardResponse(BaseModel):
    documents_indexed: int
    total_queries: int
    successful_queries: int
    average_latency_ms: float | None
    recent_documents: list[DocumentResponse]
    recent_queries: list[dict[str, Any]]
    scope: str
    generation_mode: str


class DebugResponse(BaseModel):
    id: str
    question: str
    rewritten_query: str
    route: str
    status: str
    grounding: str
    answer: str
    latency_ms: float | None
    token_usage: dict[str, Any] | None
    estimated_cost: float | None
    trace: list[dict[str, Any]]
    error: str | None
    request_id: str
    candidates: list[dict[str, Any]]
