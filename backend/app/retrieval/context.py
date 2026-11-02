from app.retrieval.base import Candidate

INSUFFICIENT = "I couldn't find sufficient information in the available knowledge base."


def build_context(candidates: list[Candidate], max_bytes: int = 10000) -> list[dict]:
    """UTF-8 byte budget is a conservative upper bound for byte-level BPE tokens."""
    seen, context, used = set(), [], 0
    for item in candidates:
        normalized = " ".join(item.text.split())
        if normalized in seen:
            continue
        citation = item.serialize()
        citation["label"] = f"Source {len(context) + 1}"
        size = len((citation["label"] + item.section + item.document + item.text).encode("utf-8")) + 100
        if used + size > max_bytes:
            continue
        seen.add(normalized)
        used += size
        context.append(citation)
    return context


def evidence_text(context):
    return "\n\n".join(f"[{c['label']}] {c['document']} | {c['section']}\n{c['text']}" for c in context)
