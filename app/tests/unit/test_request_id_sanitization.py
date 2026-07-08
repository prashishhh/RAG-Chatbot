from app.middleware.request_id import _extract_request_id


def test_extract_request_id_valid() -> None:
    # Clean request ID should be accepted
    headers = [(b"x-request-id", b"req_abc123-xyz.456")]
    assert _extract_request_id(headers) == "req_abc123-xyz.456"


def test_extract_request_id_invalid_characters() -> None:
    # Characters other than alphanumeric, hyphens, underscores, dots should be rejected
    bad_headers = [
        (b"x-request-id", b"req_abc;injection"),
        (b"x-request-id", b"req_abc\nnewline"),
        (b"x-request-id", b"req_abc<script>"),
        (b"x-request-id", b"req_abc\x00nullbyte"),
        (b"x-request-id", b"req_abc\x7fcontrol"),
    ]
    for headers in bad_headers:
        assert _extract_request_id([headers]) is None


def test_extract_request_id_length_limits() -> None:
    # Too long should be rejected
    long_id = b"a" * 129
    assert _extract_request_id([(b"x-request-id", long_id)]) is None

    # Empty should be rejected
    assert _extract_request_id([(b"x-request-id", b"")]) is None
