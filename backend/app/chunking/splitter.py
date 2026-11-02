"""Pack parsed document sections into bounded chunks before embedding."""

import re

from app.ingestion.parsing import Section


def chunk_sections(sections: list[Section], max_words: int = 180) -> list[Section]:
    """Preserve section/page boundaries, pack sentences, then split oversized sentences by words."""
    chunks = []
    for section in sections:
        current: list[str] = []
        for sentence in re.split(r"(?<=[.!?])\s+|\n", section.text):
            words = sentence.split()
            for start in range(0, len(words), max_words):
                part = words[start : start + max_words]
                if len(current) + len(part) > max_words:
                    chunks.append(Section(" ".join(current), section.heading, section.page))
                    current = []
                current.extend(part)
        if current:
            chunks.append(Section(" ".join(current), section.heading, section.page))
    if len(chunks) > 5000:
        raise ValueError("Document exceeds 5000 chunks.")
    return chunks
