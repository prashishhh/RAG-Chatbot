import hashlib
import re
from dataclasses import dataclass

from app.core.exceptions import ValidationException
from app.modules.ingestion.extraction import ExtractedText

MAX_CHUNK_CHARS = 1_200
MAX_CHUNKS_PER_DOCUMENT = 10_000
_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")


@dataclass(frozen=True)
class PreparedChunk:
    chunk_index: int
    content: str
    content_hash: str
    char_count: int
    page_number: int | None = None
    section_title: str | None = None


def prepare_chunks(extracted_items: list[ExtractedText]) -> list[PreparedChunk]:
    chunks: list[PreparedChunk] = []

    for item in extracted_items:
        for content in _chunks_for_text(item.text):
            chunks.append(
                PreparedChunk(
                    chunk_index=len(chunks),
                    content=content,
                    content_hash=_content_hash(content),
                    char_count=len(content),
                    page_number=item.page_number,
                )
            )
            if len(chunks) > MAX_CHUNKS_PER_DOCUMENT:
                raise ValidationException("Document has too many chunks to ingest.")

    if not chunks:
        raise ValidationException("Document text is empty.")

    return chunks


def _chunks_for_text(text: str) -> list[str]:
    paragraphs = [
        paragraph.strip()
        for paragraph in _PARAGRAPH_SPLIT_RE.split(text)
        if paragraph.strip()
    ]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        for piece in _split_large_paragraph(paragraph):
            candidate = f"{current}\n\n{piece}" if current else piece
            if len(candidate) <= MAX_CHUNK_CHARS:
                current = candidate
                continue
            if current:
                chunks.append(current)
            current = piece

    if current:
        chunks.append(current)

    return chunks


def _split_large_paragraph(paragraph: str) -> list[str]:
    return [
        paragraph[index : index + MAX_CHUNK_CHARS].strip()
        for index in range(0, len(paragraph), MAX_CHUNK_CHARS)
        if paragraph[index : index + MAX_CHUNK_CHARS].strip()
    ]


def _content_hash(content: str) -> str:
    normalized = " ".join(content.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
