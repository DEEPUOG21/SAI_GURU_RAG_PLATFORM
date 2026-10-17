import pytest
from sqlalchemy.dialects import postgresql

from app.retrieval.base import Candidate
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.postgres import authorized_chunks
from app.security.scope import Scope
from app.services.cache import InMemoryCache, scoped_key
from app.services.context import build_context


def item(id, text="Evidence", **kwargs):
    return Candidate(id, "doc", "Policy.md", text, 2, "Leave", 1, **kwargs)


def test_rrf_scores_not_concatenation():
    result = reciprocal_rank_fusion([item("a"), item("b")], [item("b"), item("c")])
    assert [c.chunk_id for c in result] == ["b", "a", "c"]
    assert result[0].rrf_score == pytest.approx(1 / 62 + 1 / 61)


def test_rrf_preserves_independent_scores_without_mutation():
    dense = item("a", dense_score=0.7)
    result = reciprocal_rank_fusion([dense], [item("a", lexical_score=0.2)])
    assert result[0].dense_score == 0.7 and result[0].lexical_score == 0.2
    assert dense.rrf_score == 0


def test_authorization_is_in_retrieval_sql():
    sql = str(
        authorized_chunks(Scope("tenant-A", "user", "EMPLOYEE")).compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "document_chunks.tenant_id = 'tenant-A'" in sql
    assert "documents.tenant_id = 'tenant-A'" in sql
    assert "documents.min_role <= 0" in sql
    assert "document_chunks.version = documents.version" in sql


def test_context_deduplicates_and_keeps_metadata():
    context = build_context([item("a"), item("b"), item("c", "Other evidence")])
    assert len(context) == 2
    assert context[0]["page"] == 2 and context[0]["chunk_id"] == "a"
    assert context[1]["label"] == "Source 2"
    assert build_context([item("a")], max_bytes=1) == []


def test_cache_tenant_role_revision_isolation_and_expiry():
    cache = InMemoryCache(1)
    a, b = Scope("a", "u", "ADMIN"), Scope("b", "u", "ADMIN")
    cache.set(scoped_key(a, "v1", "q"), ["private"])
    assert cache.get(scoped_key(b, "v1", "q")) is None
    assert cache.get(scoped_key(a, "v2", "q")) is None
    cache.set(("expired",), 1, ttl=-1)
    assert cache.get(("expired",)) is None
    assert cache.get(scoped_key(a, "v1", "q")) is None
