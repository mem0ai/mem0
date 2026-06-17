"""HTTP middleware for request-scoped structured logging."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.utils.logging_context import new_request_id, request_id_var


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assign a ``request_id`` per HTTP request for log correlation."""

    async def dispatch(self, request: Request, call_next):
        token = request_id_var.set(
            request.headers.get("x-request-id") or new_request_id()
        )
        try:
            response = await call_next(request)
            response.headers["X-Request-Id"] = request_id_var.get()
            return response
        finally:
            request_id_var.reset(token)
