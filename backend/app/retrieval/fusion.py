from dataclasses import replace

from app.retrieval.base import Candidate


def reciprocal_rank_fusion(*rankings: list[Candidate], constant: int = 60) -> list[Candidate]:
    if constant < 1:
        raise ValueError("RRF constant must be positive.")
    merged: dict[str, Candidate] = {}
    for ranking in rankings:
        seen = set()
        for rank, item in enumerate(ranking, 1):
            if item.chunk_id in seen:
                continue
            seen.add(item.chunk_id)
            target = merged.setdefault(item.chunk_id, replace(item, rrf_score=0))
            target.rrf_score += 1 / (constant + rank)
            if item.dense_score is not None:
                target.dense_score = item.dense_score
            if item.lexical_score is not None:
                target.lexical_score = item.lexical_score
    return sorted(merged.values(), key=lambda item: (-item.rrf_score, item.chunk_id))
