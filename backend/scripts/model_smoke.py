import asyncio

from app.reranking.providers import reranker
from app.retrieval.base import Candidate
from app.services.providers import embeddings


async def main():
    vectors = await embeddings().embed(
        ["Employees receive 24 days of annual leave.", "Deploy using reviewed pull requests."]
    )
    assert len(vectors) == 2 and len(vectors[0]) == 384
    candidates = [
        Candidate(str(i), "doc", "policy.md", text, None, "Policy", 1)
        for i, text in enumerate(
            ["Deploy using reviewed pull requests.", "Employees receive 24 days of annual leave."]
        )
    ]
    ranked = await reranker().rerank("How many annual leave days do employees receive?", candidates)
    assert ranked[0].chunk_id == "1"
    print(
        {
            "embedding_dimensions": len(vectors[0]),
            "reranker_order": [c.chunk_id for c in ranked],
            "reranker_scores": [c.reranker_score for c in ranked],
        }
    )


asyncio.run(main())
