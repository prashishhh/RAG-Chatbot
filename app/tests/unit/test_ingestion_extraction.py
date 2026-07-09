import pytest

from app.core.exceptions import ValidationException
from app.modules.ingestion import extraction
from app.modules.ingestion.extraction import MAX_EXTRACTED_TEXT_CHARS, ExtractedText, extract_text


class FakePdfPage:
    def __init__(self, text: str | None) -> None:
        self.text = text

    def extract_text(self) -> str | None:
        return self.text


class FakePdfReader:
    def __init__(self, content, *, encrypted: bool = False, pages=None) -> None:
        self.is_encrypted = encrypted
        self.pages = pages or []


def test_extract_text_supports_plain_text_and_normalizes_line_endings() -> None:
    extracted = extract_text(b"\xef\xbb\xbfhello\r\nworld\r", "Text/Plain; charset=utf-8")

    assert extracted == [ExtractedText(text="hello\nworld")]


def test_extract_text_supports_markdown() -> None:
    assert extract_text(b"# Title\n\nBody", "text/markdown") == [
        ExtractedText(text="# Title\n\nBody")
    ]


def test_extract_text_supports_pdf_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_reader(content):
        return FakePdfReader(
            content,
            pages=[FakePdfPage("Page one\r\ntext"), FakePdfPage("   "), FakePdfPage("Page three")],
        )

    monkeypatch.setattr(extraction, "PdfReader", fake_reader)

    assert extract_text(b"%PDF-1.7", "application/pdf") == [
        ExtractedText(text="Page one\ntext", page_number=1),
        ExtractedText(text="Page three", page_number=3),
    ]


def test_extract_text_rejects_encrypted_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        extraction,
        "PdfReader",
        lambda content: FakePdfReader(content, encrypted=True),
    )

    with pytest.raises(ValidationException, match="Encrypted"):
        extract_text(b"%PDF-1.7", "application/pdf")


def test_extract_text_rejects_pdf_without_extractable_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        extraction,
        "PdfReader",
        lambda content: FakePdfReader(content, pages=[FakePdfPage("")]),
    )

    with pytest.raises(ValidationException, match="empty"):
        extract_text(b"%PDF-1.7", "application/pdf")


def test_extract_text_rejects_broken_pdf() -> None:
    with pytest.raises(ValidationException, match="PDF could not be read"):
        extract_text(b"not a pdf", "application/pdf")


def test_extract_text_rejects_invalid_utf8() -> None:
    with pytest.raises(ValidationException, match="could not be decoded"):
        extract_text(b"\xff", "text/plain")


def test_extract_text_rejects_empty_text() -> None:
    with pytest.raises(ValidationException, match="empty"):
        extract_text(b" \n\t", "text/plain")


def test_extract_text_caps_extracted_text_size() -> None:
    with pytest.raises(ValidationException, match="too large"):
        extract_text(b"a" * (MAX_EXTRACTED_TEXT_CHARS + 1), "text/plain")


def test_extract_text_caps_pdf_text_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        extraction,
        "PdfReader",
        lambda content: FakePdfReader(
            content,
            pages=[FakePdfPage("a" * (MAX_EXTRACTED_TEXT_CHARS + 1))],
        ),
    )

    with pytest.raises(ValidationException, match="too large"):
        extract_text(b"%PDF-1.7", "application/pdf")
