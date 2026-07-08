from app.core.responses import ApiResponse, Pagination


def test_success_response_uses_standard_contract() -> None:
    response = ApiResponse.success_response(data={"ok": True}, message="Done.")

    assert response.model_dump(by_alias=True) == {
        "success": True,
        "message": "Done.",
        "errors": {},
        "data": {"ok": True},
        "requestId": None,
    }


def test_error_response_includes_request_id_without_sensitive_details() -> None:
    response = ApiResponse.error_response(
        message="Validation failed.",
        errors={"email": ["A valid email address is required."]},
        request_id="req_test",
    )

    assert response.model_dump(by_alias=True) == {
        "success": False,
        "message": "Validation failed.",
        "errors": {"email": ["A valid email address is required."]},
        "data": None,
        "requestId": "req_test",
    }


def test_pagination_aliases_match_api_contract() -> None:
    pagination = Pagination(
        page=1,
        pageSize=20,
        totalItems=100,
        totalPages=5,
        hasNextPage=True,
        hasPreviousPage=False,
    )

    assert pagination.model_dump(by_alias=True) == {
        "page": 1,
        "pageSize": 20,
        "totalItems": 100,
        "totalPages": 5,
        "hasNextPage": True,
        "hasPreviousPage": False,
    }

