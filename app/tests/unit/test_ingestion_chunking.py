import pytest

from app.core.exceptions import ValidationException
from app.modules.ingestion import chunking
from app.modules.ingestion.chunking import MAX_CHUNK_CHARS, PreparedChunk, prepare_chunks
from app.modules.ingestion.extraction import ExtractedText


def test_prepare_chunks_splits_by_paragraph_and_preserves_page_number() -> None:
    chunks = prepare_chunks(
        [ExtractedText(text="First paragraph.\n\nSecond paragraph.", page_number=2)]
    )

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].content == "First paragraph.\n\nSecond paragraph."
    assert chunks[0].page_number == 2
    assert chunks[0].char_count == len(chunks[0].content)
    assert len(chunks[0].content_hash) == 64


def test_prepare_chunks_splits_large_paragraphs() -> None:
    chunks = prepare_chunks([ExtractedText(text="a" * (MAX_CHUNK_CHARS + 1))])

    assert [chunk.chunk_index for chunk in chunks] == [0, 1]
    assert len(chunks[0].content) == MAX_CHUNK_CHARS
    assert chunks[1].content == "a"


def test_prepare_chunks_uses_stable_hash_for_equivalent_whitespace() -> None:
    first = prepare_chunks([ExtractedText(text="alpha   beta")])[0]
    second = prepare_chunks([ExtractedText(text="alpha beta")])[0]

    assert first.content_hash == second.content_hash


def test_prepare_chunks_assigns_global_order_across_pages() -> None:
    chunks = prepare_chunks(
        [
            ExtractedText(text="Page one", page_number=1),
            ExtractedText(text="Page two", page_number=2),
        ]
    )

    assert [(chunk.chunk_index, chunk.page_number, chunk.content) for chunk in chunks] == [
        (0, 1, "Page one"),
        (1, 2, "Page two"),
    ]


def test_prepare_chunks_rejects_empty_input() -> None:
    with pytest.raises(ValidationException, match="empty"):
        prepare_chunks([])


def test_prepare_chunks_rejects_too_many_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chunking, "MAX_CHUNKS_PER_DOCUMENT", 1)

    with pytest.raises(ValidationException, match="too many chunks"):
        prepare_chunks(
            [
                ExtractedText(text="one", page_number=1),
                ExtractedText(text="two", page_number=2),
            ]
        )


def test_prepared_chunk_shape_matches_document_chunk_model() -> None:
    chunk = prepare_chunks([ExtractedText(text="hello")])[0]

    assert isinstance(chunk, PreparedChunk)
    assert chunk.section_title is None
