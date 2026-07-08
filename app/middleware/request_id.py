import re
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_SAFE_REQUEST_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]{1,128}$")


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _extract_request_id(scope.get("headers", [])) or f"req_{uuid4().hex}"
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("utf-8")))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_request_id)


def _extract_request_id(headers: list[tuple[bytes, bytes]]) -> str | None:
    for name, value in headers:
        if name.lower() == b"x-request-id":
            try:
                request_id = value.decode("utf-8").strip()
                if _SAFE_REQUEST_ID_PATTERN.match(request_id):
                    return request_id
            except UnicodeDecodeError:
                pass
    return None
