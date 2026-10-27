import re

from sqlalchemy import func, select

from app.models.entities import Chunk, Document
from app.retrieval.base import Candidate, Retriever
from app.services.providers import embeddings


def authorized_chunks(scope):
    return (
        select(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .where(
            Chunk.tenant_id == scope.tenant_id,
            Document.tenant_id == scope.tenant_id,
            Document.min_role <= scope.level,
            Document.status == "COMPLETED",
            Chunk.version == Document.version,
        )
    )


async def source_catalog(db, scope):
    """Return bounded titles/sections visible to this caller, never document bodies."""
    statement = (
        authorized_chunks(scope)
        .with_only_columns(Chunk.source, Chunk.section)
        .distinct()
        .order_by(Chunk.source, Chunk.section)
        .limit(60)
    )
    rows = (await db.execute(statement)).all()
    return [{"document": source[:160], "section": section[:120]} for source, section in rows]


def candidate(chunk, score, dense):
    result = Candidate(
        chunk.id, chunk.document_id, chunk.source, chunk.text, chunk.page, chunk.section, chunk.version
    )
    if dense:
        result.dense_score = float(score)
    else:
        result.lexical_score = float(score)
    return result


class DenseRetriever(Retriever):
    def __init__(self, db):
        self.db = db

    async def retrieve(self, query, scope, k=20):
        vector = (await embeddings().embed([query]))[0]
        distance = Chunk.embedding.cosine_distance(vector)
        statement = (
            authorized_chunks(scope).add_columns((1 - distance).label("score")).order_by(distance).limit(k)
        )
        return [candidate(row[0], row[1], True) for row in (await self.db.execute(statement)).all()]


class LexicalRetriever(Retriever):
    def __init__(self, db):
        self.db = db

    async def retrieve(self, query, scope, k=20):
        # Natural-language questions rarely share every term with a source. OR retrieval
        # finds partial lexical matches; PostgreSQL ranking and the reranker order them.
        terms = list(dict.fromkeys(re.findall(r"\w+", query.lower())))[:80]
        tsquery = func.websearch_to_tsquery("english", " OR ".join(terms))
        score = func.ts_rank_cd(Chunk.search_vector, tsquery)
        statement = (
            authorized_chunks(scope)
            .add_columns(score)
            .where(Chunk.search_vector.op("@@")(tsquery))
            .order_by(score.desc())
            .limit(k)
        )
        return [candidate(row[0], row[1], False) for row in (await self.db.execute(statement)).all()]
