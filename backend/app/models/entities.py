import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


def new_id():
    return str(uuid.uuid4())


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Tenant(Identity, Base):
    __tablename__ = "tenants"
    name: Mapped[str] = mapped_column(String(120))


class User(Identity, Base):
    __tablename__ = "users"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    role: Mapped[str] = mapped_column(String(16), default="EMPLOYEE")
    __table_args__ = (CheckConstraint("role IN ('ADMIN','MANAGER','EMPLOYEE')"),)


class Document(Identity, Base):
    __tablename__ = "documents"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    min_role: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="UPLOADED", index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("tenant_id", "name"),
        UniqueConstraint("id", "tenant_id"),
        CheckConstraint("min_role BETWEEN 0 AND 2"),
    )


class DocumentVersion(Identity, Base):
    __tablename__ = "document_versions"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    document_id: Mapped[str] = mapped_column(String(36), index=True)
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    content_hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "tenant_id"], ["documents.id", "documents.tenant_id"], ondelete="CASCADE"
        ),
        UniqueConstraint("document_id", "version"),
    )


class Chunk(Identity, Base):
    __tablename__ = "document_chunks"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    document_id: Mapped[str] = mapped_column(String(36), index=True)
    version: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str] = mapped_column(String(512))
    source: Mapped[str] = mapped_column(String(255))
    embedding: Mapped[list[float]] = mapped_column(Vector(384))
    search_vector: Mapped[str] = mapped_column(TSVECTOR)
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "tenant_id"], ["documents.id", "documents.tenant_id"], ondelete="CASCADE"
        ),
        Index(
            "ix_chunks_vector",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_chunks_search", "search_vector", postgresql_using="gin"),
    )


class Conversation(Identity, Base):
    __tablename__ = "conversations"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))


class Message(Identity, Base):
    __tablename__ = "messages"
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    query_id: Mapped[str | None] = mapped_column(String(36), index=True)


class Query(Identity, Base):
    __tablename__ = "queries"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"))
    question: Mapped[str] = mapped_column(Text)
    rewritten_query: Mapped[str] = mapped_column(Text, default="")
    route: Mapped[str] = mapped_column(String(16), default="DOCUMENT")
    status: Mapped[str] = mapped_column(String(20), default="RUNNING")
    answer: Mapped[str] = mapped_column(Text, default="")
    grounding: Mapped[str] = mapped_column(String(24), default="NOT_CHECKED")
    latency_ms: Mapped[float | None] = mapped_column(Float)
    token_usage: Mapped[dict | None] = mapped_column(JSON)
    estimated_cost: Mapped[float | None] = mapped_column(Float)
    trace: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str] = mapped_column(String(36))


class RetrievalResult(Identity, Base):
    __tablename__ = "retrieval_results"
    query_id: Mapped[str] = mapped_column(ForeignKey("queries.id", ondelete="CASCADE"), index=True)
    chunk_id: Mapped[str | None] = mapped_column(ForeignKey("document_chunks.id", ondelete="SET NULL"))
    metadata_snapshot: Mapped[dict] = mapped_column(JSON)
    dense_score: Mapped[float | None] = mapped_column(Float)
    lexical_score: Mapped[float | None] = mapped_column(Float)
    rrf_score: Mapped[float] = mapped_column(Float)
    reranker_score: Mapped[float | None] = mapped_column(Float)


class Feedback(Identity, Base):
    __tablename__ = "feedback"
    query_id: Mapped[str] = mapped_column(ForeignKey("queries.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (UniqueConstraint("query_id", "user_id"), CheckConstraint("rating IN (-1, 1)"))


class Evaluation(Identity, Base):
    __tablename__ = "evaluations"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="RUNNING")
    dataset_version: Mapped[str] = mapped_column(String(32), default="saitech-v1")
    results: Mapped[dict] = mapped_column(JSON, default=dict)


class RateLimit(Base):
    __tablename__ = "rate_limits"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    window: Mapped[int] = mapped_column(Integer, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=1)


class Employee(Identity, Base):
    __tablename__ = "employees"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    department: Mapped[str] = mapped_column(String(80))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
