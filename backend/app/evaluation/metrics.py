import math
import re


def retrieval_metrics(retrieved: list[str], expected: list[str], k: int = 6):
    ranked = list(dict.fromkeys(retrieved))[:k]
    relevant = set(expected)
    hits = [int(doc in relevant) for doc in ranked]
    dcg = sum(hit / math.log2(rank + 2) for rank, hit in enumerate(hits))
    ideal = sum(1 / math.log2(rank + 2) for rank in range(min(len(relevant), k)))
    return {
        "recall_at_k": sum(hits) / len(relevant) if relevant else 0,
        "precision_at_k": sum(hits) / k,
        "mrr": next((1 / (i + 1) for i, hit in enumerate(hits) if hit), 0),
        "ndcg": dcg / ideal if ideal else 0,
    }


def token_f1(actual, expected):
    a, b = set(re.findall(r"\w+", actual.lower())), set(re.findall(r"\w+", expected.lower()))
    if not a or not b:
        return 0.0
    return 2 * len(a & b) / (len(a) + len(b))


def citation_correctness(citations, expected):
    if not citations:
        return 0.0
    return sum(
        any(c.get("document") == e["document"] and c.get("section") == e["section"] for e in expected)
        for c in citations
    ) / len(citations)
