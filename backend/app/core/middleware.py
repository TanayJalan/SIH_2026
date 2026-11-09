"""Middleware for request IDs and structured access logs."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import request_id_var

logger = logging.getLogger("app.request")

_DOCS_PATHS = frozenset({"/docs", "/redoc", "/openapi.json"})
_AUTH_PATHS = ("/auth/",)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach browser hardening headers to every response.

    The API returns JSON, so a strict ``default-src 'none'`` policy is safe.
    The interactive OpenAPI pages need their bundled CDN assets, so they get a
    narrow read-only policy instead. HSTS is emitted only for production
    traffic that actually arrived over HTTPS (directly or through a trusted
    proxy).
    """

    def __init__(
        self,
        app: object,
        *,
        hsts_seconds: int = 0,
    ) -> None:
        super().__init__(app)
        self._hsts_seconds = hsts_seconds

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault(
            "Permissions-Policy",
            "camera=(), geolocation=(), microphone=(), payment=()",
        )
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")

        if request.url.path in _DOCS_PATHS:
            headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; "
                "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
                "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
                "img-src 'self' data: https://fastapi.tiangolo.com; "
                "connect-src 'self'; frame-ancestors 'none'",
            )
        else:
            headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; base-uri 'none'; form-action 'none'; "
                "frame-ancestors 'none'",
            )

        if any(request.url.path.startswith(prefix) for prefix in _AUTH_PATHS):
            headers.setdefault("Cache-Control", "no-store")

        if self._hsts_seconds > 0 and _is_https(request):
            headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={self._hsts_seconds}; includeSubDomains",
            )
        return response


def _is_https(request: Request) -> bool:
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    return request.url.scheme == "https" or forwarded == "https"


class RequestContextMiddleware(BaseHTTPMiddleware):

    """Attach a request ID to logs and responses, and log request completion."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        client_ip = request.client.host if request.client else None

        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request failed",
                extra={
                    "http_method": request.method,
                    "path": request.url.path,
                    "client_ip": client_ip,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            raise
        else:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "request completed",
                extra={
                    "http_method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "client_ip": client_ip,
                    "duration_ms": duration_ms,
                },
            )
            return response
        finally:
            request_id_var.reset(token)
