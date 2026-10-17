"""Conservative literal conflict reporting; never chooses which undated claim is current."""

import re
from collections import defaultdict


def literal_conflicts(question, context):
    stop = {"what", "is", "are", "our", "the", "in", "any", "documents", "identify", "conflicting", "amounts"}
    terms = set(re.findall(r"[a-z]+", question.lower())) - stop
    groups = defaultdict(list)
    for source in context:
        for sentence in re.split(r"(?<=[.!?])\s+", source["text"]):
            if not re.search(r"\d", sentence):
                continue
            words = set(re.findall(r"[a-z]+", sentence.lower())) - stop
            if len(words & terms) < min(2, max(1, len(terms))):
                continue
            skeleton = re.sub(r"\d+(?:[,.]\d+)*", "#", sentence.lower()).strip()
            groups[skeleton].append((sentence.strip(), source))
    for group in groups.values():
        if len({sentence.lower() for sentence, _ in group}) < 2:
            continue
        if len({source.get("document_id") for _, source in group}) < 2:
            continue
        return (
            "The retrieved documents disagree:\n\n"
            + "\n\n".join(f"> {sentence}\n\n[{source['label']}]" for sentence, source in group)
            + "\n\nI cannot determine which statement is authoritative from these conflicting excerpts. Please confirm with the document owner."
        )
    return None


def relevant_excerpts(question, context):
    """Fallback is labeled quotation, never a claim that the model's rejected answer was verified."""
    stop = {
        "what",
        "where",
        "when",
        "who",
        "how",
        "is",
        "are",
        "our",
        "the",
        "a",
        "an",
        "of",
        "in",
        "it",
        "does",
    }
    terms = set(re.findall(r"[a-z]+", question.lower())) - stop
    matches = []
    for rank, source in enumerate(context):
        for sentence in re.split(r"(?<=[.!?])\s+", source["text"]):
            if re.search(
                r"ignore|instructions?|system prompt|credentials?|api.?key|password|output\s|send\s|reveal|access restrictions",
                sentence,
                re.I,
            ):
                continue
            overlap = len(terms & set(re.findall(r"[a-z]+", sentence.lower())))
            if overlap >= 2:
                matches.append((rank, -overlap, sentence, source["label"]))
    if not matches:
        return None
    # Preserve semantic reranker order; lexical overlap alone favors distractors
    # and fails on equivalent forms such as "launch" / "launches".
    matches.sort(key=lambda row: (row[0], row[1]))
    selected, seen = [], set()
    for _, _, sentence, label in matches:
        if label not in seen:
            selected.append((sentence, label))
            seen.add(label)
        if len(selected) == 2:
            break
    return "Relevant source excerpts (the generated answer could not be verified):\n\n" + "\n\n".join(
        f"> {sentence.strip()}\n\n[{label}]" for sentence, label in selected
    )
