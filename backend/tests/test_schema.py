from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.database.session import Base
from app.models.entities import Chunk, Document, DocumentVersion


def test_tenant_scoped_documents_and_chunks():
    for model in (Chunk, Document, DocumentVersion):
        assert not model.__table__.c.tenant_id.nullable
    constraints = str(CreateTable(Chunk.__table__).compile(dialect=postgresql.dialect()))
    assert "FOREIGN KEY(document_id, tenant_id)" in constraints
    assert "VECTOR(384)" in constraints


def test_required_tables():
    assert {
        "users",
        "tenants",
        "documents",
        "document_versions",
        "document_chunks",
        "conversations",
        "messages",
        "queries",
        "retrieval_results",
        "feedback",
        "evaluations",
    } <= set(Base.metadata.tables)
