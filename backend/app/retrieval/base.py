from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass

from app.security.scope import Scope


@dataclass
class Candidate:
    chunk_id: str
    document_id: str
    document: str
    text: str
    page: int | None
    section: str
    version: int
    dense_score: float | None = None
    lexical_score: float | None = None
    rrf_score: float = 0
    reranker_score: float | None = None

    def serialize(self):
        return asdict(self)


class Retriever(ABC):
    @abstractmethod
    async def retrieve(self, query: str, scope: Scope, k: int = 20) -> list[Candidate]: ...
