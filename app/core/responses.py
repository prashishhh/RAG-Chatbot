from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


class Pagination(BaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(alias="pageSize", ge=1)
    total_items: int = Field(alias="totalItems", ge=0)
    total_pages: int = Field(alias="totalPages", ge=0)
    has_next_page: bool = Field(alias="hasNextPage")
    has_previous_page: bool = Field(alias="hasPreviousPage")

    model_config = ConfigDict(populate_by_name=True)


class ApiResponse[DataT](BaseModel):
    success: bool
    message: str
    errors: dict[str, list[str]] = Field(default_factory=dict)
    data: DataT | None = None
    request_id: str | None = Field(default=None, alias="requestId")

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def success_response(
        cls,
        *,
        data: DataT | None = None,
        message: str = "Operation completed successfully.",
    ) -> "ApiResponse[DataT]":
        return cls(success=True, message=message, errors={}, data=data)

    @classmethod
    def error_response(
        cls,
        *,
        message: str,
        errors: dict[str, list[str]] | None = None,
        request_id: str | None = None,
    ) -> "ApiResponse[object]":
        return cls(
            success=False,
            message=message,
            errors=errors or {},
            data=None,
            request_id=request_id,
        )


class PagedResponse[DataT](ApiResponse[list[DataT]]):
    pagination: Pagination
