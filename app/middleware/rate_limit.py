"""In-memory sliding-window rate limiter middleware.

Applies per-IP request limits with stricter thresholds for sensitive
authentication endpoints. Suitable for single-instance deployments;
upgrade to Redis-backed storage for multi-instance production setups.
"""

import re
import time
from collections import defaultdict
from threading import Lock

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# --- Configuration -----------------------------------------------------------

# Auth endpoints get stricter limits (brute-force protection).
AUTH_RATE_LIMIT = 5  # requests
AUTH_RATE_WINDOW = 60  # seconds

# Global fallback for all other endpoints.
GLOBAL_RATE_LIMIT = 60  # requests
GLOBAL_RATE_WINDOW = 60  # seconds

# Stale entries older than this are cleaned up.
_CLEANUP_INTERVAL = 300  # seconds

# Matches auth-sensitive paths.
_AUTH_PATH_PATTERN = re.compile(r"/api/v\d+/auth/(login|register|refresh)")


# --- Storage -----------------------------------------------------------------


class _SlidingWindowCounter:
    """Thread-safe sliding-window counter keyed by client IP."""

    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()
        self._last_cleanup = time.monotonic()

    def is_rate_limited(self, key: str, max_requests: int, window: int) -> tuple[bool, dict]:
        """Return (is_limited, info_dict) for the given key."""
        now = time.monotonic()

        with self._lock:
            self._maybe_cleanup(now)
            timestamps = self._buckets[key]
            cutoff = now - window
            # Drop timestamps outside the current window.
            self._buckets[key] = [ts for ts in timestamps if ts > cutoff]
            timestamps = self._buckets[key]

            remaining = max(0, max_requests - len(timestamps))
            info = {
                "limit": max_requests,
                "remaining": remaining,
                "reset": int(cutoff + window - now) + 1 if timestamps else window,
            }

            if len(timestamps) >= max_requests:
                return True, info

            timestamps.append(now)
            info["remaining"] = max(0, remaining - 1)
            return False, info

    def _maybe_cleanup(self, now: float) -> None:
        if now - self._last_cleanup < _CLEANUP_INTERVAL:
            return
        self._last_cleanup = now
        stale_keys = [
            k for k, v in self._buckets.items() if not v or v[-1] < now - _CLEANUP_INTERVAL
        ]
        for k in stale_keys:
            del self._buckets[k]


_counter = _SlidingWindowCounter()


# --- Middleware --------------------------------------------------------------


class RateLimitMiddleware:
    """ASGI middleware that enforces per-IP rate limits."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Bypass rate limiting in test environment
        from app.core.config import get_settings
        if get_settings().app_env.lower() == "test":
            await self.app(scope, receive, send)
            return

        client_ip = _get_client_ip(scope)
        path = scope.get("path", "")

        if _AUTH_PATH_PATTERN.search(path):
            max_requests, window = AUTH_RATE_LIMIT, AUTH_RATE_WINDOW
            bucket_key = f"auth:{client_ip}"
        else:
            max_requests, window = GLOBAL_RATE_LIMIT, GLOBAL_RATE_WINDOW
            bucket_key = f"global:{client_ip}"

        limited, info = _counter.is_rate_limited(bucket_key, max_requests, window)

        if limited:
            await _send_429(scope, send, info)
            return

        # Attach rate-limit headers to the response.
        original_send = send

        async def send_with_rate_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-ratelimit-limit", str(info["limit"]).encode()))
                headers.append((b"x-ratelimit-remaining", str(info["remaining"]).encode()))
                headers.append((b"x-ratelimit-reset", str(info["reset"]).encode()))
                message["headers"] = headers
            await original_send(message)

        await self.app(scope, receive, send_with_rate_headers)


# --- Helpers -----------------------------------------------------------------


def _get_client_ip(scope: Scope) -> str:
    """Extract client IP from the ASGI scope."""
    client = scope.get("client")
    if client:
        return client[0]
    # Fallback for proxied requests — check X-Forwarded-For.
    for name, value in scope.get("headers", []):
        if name.lower() == b"x-forwarded-for":
            return value.decode("utf-8").split(",")[0].strip()
    return "unknown"


async def _send_429(scope: Scope, send: Send, info: dict) -> None:
    """Send a 429 Too Many Requests response."""
    import json

    body = json.dumps(
        {
            "success": False,
            "message": "Too many requests. Please try again later.",
            "data": None,
            "errors": None,
            "requestId": None,
        }
    ).encode("utf-8")

    await send(
        {
            "type": "http.response.start",
            "status": 429,
            "headers": [
                (b"content-type", b"application/json"),
                (b"retry-after", str(info["reset"]).encode()),
                (b"x-ratelimit-limit", str(info["limit"]).encode()),
                (b"x-ratelimit-remaining", b"0"),
                (b"x-ratelimit-reset", str(info["reset"]).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
