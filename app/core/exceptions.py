import logging
from collections.abc import Mapping

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.responses import ApiResponse

logger = logging.getLogger(__name__)


class AppException(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    message = "Request could not be processed."

    def __init__(
        self,
        message: str | None = None,
        *,
        errors: Mapping[str, list[str]] | None = None,
    ) -> None:
        self.message = message or self.message
        self.errors = dict(errors or {})
        super().__init__(self.message)


class ValidationException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message = "Validation failed."


class UnauthorizedException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    message = "Authentication credentials were not provided or are invalid."


class ForbiddenException(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    message = "You do not have permission to perform this action."


class NotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    message = "Resource not found."


class ConflictException(AppException):
    status_code = status.HTTP_409_CONFLICT
    message = "Resource already exists."


class BusinessRuleException(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    message = "Business rule failed."


class ExternalProviderException(AppException):
    status_code = status.HTTP_502_BAD_GATEWAY
    message = "The external provider is temporarily unavailable."


class RateLimitException(AppException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    message = "Too many requests. Please try again later."


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _json_error(
    status_code: int,
    message: str,
    request: Request,
    errors: dict[str, list[str]] | None = None,
) -> JSONResponse:
    response = ApiResponse.error_response(
        message=message,
        errors=errors,
        request_id=_request_id(request),
    )
    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(by_alias=True),
    )


def _validation_errors(exc: RequestValidationError) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", []) if part != "body")
        field = location or "request"
        errors.setdefault(field, []).append(str(error.get("msg", "Invalid value.")))
    return errors


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return _json_error(exc.status_code, exc.message, request, exc.errors)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return _json_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Validation failed.",
            request,
            _validation_errors(exc),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request could not be processed."
        return _json_error(exc.status_code, message, request)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled exception on %s %s",
            request.method,
            request.url.path,
            exc_info=exc,
        )
        return _json_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Internal server error.",
            request,
        )
