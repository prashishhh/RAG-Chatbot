from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core.exceptions import ValidationException

SUPPORTED_TEXT_CONTENT_TYPES = {"text/plain", "text/markdown"}
PDF_CONTENT_TYPE = "application/pdf"
MAX_EXTRACTED_TEXT_CHARS = 1_000_000


@dataclass(frozen=True)
class ExtractedText:
    text: str
    page_number: int | None = None


def extract_text(content: bytes, content_type: str) -> list[ExtractedText]:
    normalized_type = content_type.split(";", 1)[0].strip().lower()
    if normalized_type in SUPPORTED_TEXT_CONTENT_TYPES:
        return [_extract_utf8_text(content)]
    if normalized_type == PDF_CONTENT_TYPE:
        return _extract_pdf_text(content)

    raise ValidationException("Document type is not supported for ingestion yet.")


def _extract_utf8_text(content: bytes) -> ExtractedText:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationException("Document text could not be decoded.") from exc

    return ExtractedText(_clean_text(text))


def _extract_pdf_text(content: bytes) -> list[ExtractedText]:
    try:
        reader = PdfReader(BytesIO(content))
    except PdfReadError as exc:
        raise ValidationException("PDF could not be read.") from exc

    if reader.is_encrypted:
        raise ValidationException("Encrypted PDFs are not supported.")

    pages: list[ExtractedText] = []
    total_chars = 0
    try:
        for page_number, page in enumerate(reader.pages, start=1):
            text = _normalize_text(page.extract_text() or "")
            if not text:
                continue
            total_chars += len(text)
            if total_chars > MAX_EXTRACTED_TEXT_CHARS:
                raise ValidationException("Document text is too large to ingest.")
            pages.append(ExtractedText(text=text, page_number=page_number))
    except ValidationException:
        raise
    except Exception as exc:
        raise ValidationException("PDF text could not be extracted.") from exc

    if not pages:
        raise ValidationException("Document text is empty.")

    return pages


def _clean_text(text: str) -> str:
    text = _normalize_text(text)
    if not text:
        raise ValidationException("Document text is empty.")

    if len(text) > MAX_EXTRACTED_TEXT_CHARS:
        raise ValidationException("Document text is too large to ingest.")

    return text


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()
