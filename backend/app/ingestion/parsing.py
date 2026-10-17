import csv
import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup
from docx import Document as Docx
from pypdf import PdfReader

SUPPORTED = {".pdf", ".docx", ".txt", ".md", ".html", ".csv", ".json"}


@dataclass
class Section:
    text: str
    heading: str = "Overview"
    page: int | None = None


def validate_file(name: str, content: bytes, limit_mb: int = 10):
    if Path(name).name != name or "/" in name or "\\" in name or len(name) > 255:
        raise ValueError("Use a plain filename of at most 255 characters.")
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError("Unsupported file type.")
    if not content or len(content) > limit_mb * 1024 * 1024:
        raise ValueError(f"File must be nonempty and no larger than {limit_mb} MB.")
    if suffix == ".pdf" and not content.startswith(b"%PDF-"):
        raise ValueError("Invalid PDF signature.")
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if len(archive.infolist()) > 2048:
                    raise ValueError("DOCX contains too many archive entries.")
                if "word/document.xml" not in archive.namelist():
                    raise ValueError("Invalid DOCX archive.")
                if sum(item.file_size for item in archive.infolist()) > 40 * 1024 * 1024:
                    raise ValueError("Expanded DOCX exceeds 40 MB.")
        except zipfile.BadZipFile as exc:
            raise ValueError("Invalid DOCX archive.") from exc
    elif suffix != ".pdf":
        content.decode("utf-8-sig")


def parse(name: str, content: bytes) -> list[Section]:
    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(io.BytesIO(content))
        if len(reader.pages) > 500:
            raise ValueError("PDF exceeds 500 pages.")
        sections = [
            Section(page.extract_text() or "", "Page content", index + 1)
            for index, page in enumerate(reader.pages)
        ]
    elif suffix == ".docx":
        document = Docx(io.BytesIO(content))
        sections, heading = [], "Overview"
        for paragraph in document.paragraphs:
            if paragraph.style and paragraph.style.name.startswith("Heading"):
                heading = paragraph.text
            elif paragraph.text.strip():
                sections.append(Section(paragraph.text, heading[:512]))
        for table in document.tables:
            sections.extend(
                Section(" | ".join(cell.text for cell in row.cells), "Table") for row in table.rows
            )
    else:
        text = content.decode("utf-8-sig")
        if suffix == ".json":
            value = json.loads(text)
            rows = value if isinstance(value, list) else [value]
            sections = [
                Section(json.dumps(row, ensure_ascii=False), f"Record {i + 1}") for i, row in enumerate(rows)
            ]
        elif suffix == ".csv":
            sections = [
                Section("; ".join(f"{k}: {v}" for k, v in row.items()), f"Row {i + 2}")
                for i, row in enumerate(csv.DictReader(io.StringIO(text)))
            ]
        elif suffix == ".html":
            soup = BeautifulSoup(text, "html.parser")
            for tag in soup(["script", "style", "iframe"]):
                tag.decompose()
            sections, heading = [], "Overview"
            for tag in soup.find_all(["h1", "h2", "h3", "p", "li", "tr"]):
                if tag.name.startswith("h"):
                    heading = tag.get_text(" ", strip=True)
                else:
                    sections.append(Section(tag.get_text(" ", strip=True), heading[:512]))
        else:
            sections, heading = [], "Overview"
            for paragraph in re.split(r"\n\s*\n", text):
                lines = paragraph.strip().splitlines()
                body = []
                for line in lines:
                    if re.match(r"^#{1,6}\s", line):
                        if body:
                            sections.append(Section("\n".join(body), heading[:512]))
                            body = []
                        heading = line.lstrip("# ")
                    else:
                        body.append(line)
                if body:
                    sections.append(Section("\n".join(body), heading[:512]))
    sections = [section for section in sections if section.text.strip()]
    if not sections:
        raise ValueError("No extractable text. Scanned PDFs require OCR, which is not implemented.")
    if sum(len(section.text) for section in sections) > 2_000_000:
        raise ValueError("Extracted text exceeds 2 million characters.")
    return sections


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
