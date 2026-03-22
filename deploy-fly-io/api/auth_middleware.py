"""
Authentication Middleware for OpenMemory

Single authentication method: OAuth 2.0
- Claude Desktop/Claude.ai: OAuth client credentials
- UI: OAuth client credentials (same flow)
- API clients: OAuth client credentials

Rate Limiting:
- 5 failed auth attempts → 30 min lockout per IP
- 10 requests/minute per IP for token endpoint (pre-auth)
- 100 requests/minute per app/user for API endpoints (post-auth)
"""

import os
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from collections import defaultdict
import base64

from fastapi import Request, HTTPException, Depends, Form, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger()

# =============================================================================
# Configuration
# =============================================================================

OAUTH_CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID", "openmemory")
OAUTH_CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET")
TOKEN_EXPIRY_HOURS = int(os.environ.get("TOKEN_EXPIRY_HOURS", "24"))
REQUIRE_AUTH = os.environ.get("REQUIRE_AUTH", "true").lower() == "true"

# Rate limiting config
MAX_FAILED_ATTEMPTS = int(os.environ.get("MAX_FAILED_ATTEMPTS", "5"))
LOCKOUT_DURATION_MINUTES = int(os.environ.get("LOCKOUT_DURATION_MINUTES", "30"))
TOKEN_RATE_LIMIT = int(os.environ.get("TOKEN_RATE_LIMIT", "10"))  # per minute, per IP (pre-auth)
API_RATE_LIMIT = int(os.environ.get("API_RATE_LIMIT", "100"))  # per minute, per app/user (post-auth)

# In-memory stores
oauth_tokens: dict = {}
failed_attempts: dict = {}
locked_ips: dict = {}
request_counts: dict = defaultdict(list)  # ip -> list of timestamps (pre-auth)
user_request_counts: dict = defaultdict(list)  # client_id -> list of timestamps (post-auth)


# =============================================================================
# Rate Limiting
# =============================================================================

def check_rate_limit(ip: str, limit: int = API_RATE_LIMIT, window: int = 60) -> bool:
    """Check if IP is within rate limit (pre-auth). Returns False if rate limited."""
    now = time.time()
    cutoff = now - window

    # Clean old entries
    request_counts[ip] = [t for t in request_counts[ip] if t > cutoff]

    # Check limit
    if len(request_counts[ip]) >= limit:
        return False

    # Record this request
    request_counts[ip].append(now)
    return True


def check_user_rate_limit(client_id: str, limit: int = API_RATE_LIMIT, window: int = 60) -> bool:
    """Check if user/app is within rate limit (post-auth). Returns False if rate limited."""
    now = time.time()
    cutoff = now - window

    # Clean old entries
    user_request_counts[client_id] = [t for t in user_request_counts[client_id] if t > cutoff]

    # Check limit
    if len(user_request_counts[client_id]) >= limit:
        return False

    # Record this request
    user_request_counts[client_id].append(now)
    return True


def get_user_rate_limit_remaining(client_id: str, limit: int = API_RATE_LIMIT, window: int = 60) -> int:
    """Get remaining requests for a user/app in the current window."""
    now = time.time()
    cutoff = now - window
    user_request_counts[client_id] = [t for t in user_request_counts[client_id] if t > cutoff]
    return max(0, limit - len(user_request_counts[client_id]))


def check_auth_lockout(ip: str) -> bool:
    """Check if IP is locked out from auth attempts."""
    now = datetime.now(timezone.utc)
    if ip in locked_ips:
        if now < locked_ips[ip]:
            return False
        del locked_ips[ip]
        failed_attempts.pop(ip, None)
    return True


def record_auth_failure(ip: str):
    """Record failed auth attempt."""
    now = datetime.now(timezone.utc)
    if ip not in failed_attempts:
        failed_attempts[ip] = []

    cutoff = now - timedelta(minutes=LOCKOUT_DURATION_MINUTES)
    failed_attempts[ip] = [t for t in failed_attempts[ip] if t > cutoff]
    failed_attempts[ip].append(now)

    if len(failed_attempts[ip]) >= MAX_FAILED_ATTEMPTS:
        locked_ips[ip] = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        logger.warning("IP locked out due to failed auth", ip=ip, duration_min=LOCKOUT_DURATION_MINUTES)


def clear_auth_failures(ip: str):
    failed_attempts.pop(ip, None)


def get_remaining_lockout(ip: str) -> Optional[int]:
    """Get remaining lockout time in seconds."""
    if ip in locked_ips:
        remaining = (locked_ips[ip] - datetime.now(timezone.utc)).total_seconds()
        if remaining > 0:
            return int(remaining)
    return None


# =============================================================================
# OAuth 2.0
# =============================================================================

def validate_client(client_id: str, client_secret: str) -> bool:
    if not OAUTH_CLIENT_SECRET:
        logger.warning("OAUTH_CLIENT_SECRET not set")
        return False
    return (
        hmac.compare_digest(client_id, OAUTH_CLIENT_ID) and
        hmac.compare_digest(client_secret, OAUTH_CLIENT_SECRET)
    )


def create_token(client_id: str, scope: str = "read write") -> dict:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRY_HOURS)

    oauth_tokens[token] = {
        "client_id": client_id,
        "scope": scope.split(),
        "expires_at": expires_at,
    }

    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": TOKEN_EXPIRY_HOURS * 3600,
        "scope": scope,
    }


def validate_token(token: str) -> Optional[dict]:
    if token not in oauth_tokens:
        return None
    info = oauth_tokens[token]
    if datetime.now(timezone.utc) > info["expires_at"]:
        del oauth_tokens[token]
        return None
    return info


# =============================================================================
# FastAPI Auth
# =============================================================================

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Authenticate via Bearer token (OAuth)."""
    if not REQUIRE_AUTH:
        return {"user_id": "anonymous", "scopes": ["read", "write"]}

    client_ip = request.client.host if request.client else "unknown"

    # Check lockout
    if not check_auth_lockout(client_ip):
        remaining = get_remaining_lockout(client_ip)
        raise HTTPException(
            429,
            f"Too many failed attempts. Try again in {remaining} seconds.",
            headers={"Retry-After": str(remaining)}
        )

    if not credentials:
        raise HTTPException(401, "Bearer token required")

    token_info = validate_token(credentials.credentials)
    if not token_info:
        record_auth_failure(client_ip)
        raise HTTPException(401, "Invalid or expired token")

    clear_auth_failures(client_ip)

    # Rate limit by user/app (not IP) for authenticated requests
    client_id = token_info["client_id"]
    if not check_user_rate_limit(client_id, limit=API_RATE_LIMIT, window=60):
        remaining = get_user_rate_limit_remaining(client_id, limit=API_RATE_LIMIT, window=60)
        raise HTTPException(
            429,
            f"Rate limit exceeded for app '{client_id}'. Try again later.",
            headers={
                "Retry-After": "60",
                "X-RateLimit-Limit": str(API_RATE_LIMIT),
                "X-RateLimit-Remaining": str(remaining),
            }
        )

    return {
        "user_id": client_id,
        "scopes": token_info["scope"],
    }


# =============================================================================
# Auth Router
# =============================================================================

auth_router = APIRouter(prefix="/auth", tags=["authentication"])


@auth_router.post("/oauth/token")
async def oauth_token(
    request: Request,
    grant_type: str = Form(None),
    client_id: str = Form(None),
    client_secret: str = Form(None),
    scope: str = Form("read write"),
):
    """
    OAuth 2.0 Token Endpoint

    Rate limited: 10 requests/minute per IP
    Lockout: 5 failed attempts → 30 min lockout
    """
    client_ip = request.client.host if request.client else "unknown"

    # Check rate limit (stricter for token endpoint)
    if not check_rate_limit(client_ip, limit=TOKEN_RATE_LIMIT, window=60):
        raise HTTPException(
            429,
            "Rate limit exceeded. Try again later.",
            headers={"Retry-After": "60"}
        )

    # Check lockout
    if not check_auth_lockout(client_ip):
        remaining = get_remaining_lockout(client_ip)
        raise HTTPException(
            429,
            f"Too many failed attempts. Try again in {remaining} seconds.",
            headers={"Retry-After": str(remaining)}
        )

    # Support Basic auth header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth_header[6:]).decode()
            client_id, client_secret = decoded.split(":", 1)
        except Exception:
            pass

    # Support JSON body
    if not client_id or not client_secret:
        try:
            body = await request.json()
            client_id = body.get("client_id", client_id)
            client_secret = body.get("client_secret", client_secret)
            grant_type = body.get("grant_type", grant_type)
            scope = body.get("scope", scope)
        except Exception:
            pass

    if not grant_type:
        grant_type = "client_credentials"

    if grant_type != "client_credentials":
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

    if not client_id or not client_secret:
        return JSONResponse(
            {"error": "invalid_request", "error_description": "Missing credentials"},
            status_code=400
        )

    if not validate_client(client_id, client_secret):
        record_auth_failure(client_ip)
        logger.warning("Invalid OAuth credentials", ip=client_ip)
        return JSONResponse({"error": "invalid_client"}, status_code=401)

    clear_auth_failures(client_ip)
    token_response = create_token(client_id, scope)
    logger.info("OAuth token issued", client_id=client_id)

    return JSONResponse(token_response)


@auth_router.get("/verify")
async def verify(current_user: dict = Depends(get_current_user)):
    """Verify current token is valid."""
    return {
        "valid": True,
        "user_id": current_user["user_id"],
        "scopes": current_user["scopes"],
    }


@auth_router.post("/revoke")
async def revoke(request: Request):
    """Revoke a token."""
    try:
        body = await request.json()
        token = body.get("token")
        if token and token in oauth_tokens:
            del oauth_tokens[token]
            return {"status": "revoked"}
    except Exception:
        pass
    return {"status": "ok"}


# =============================================================================
# Middleware
# =============================================================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limit unauthenticated requests by IP (DDoS protection).

    Authenticated API endpoints use per-user rate limiting in get_current_user().
    This middleware provides a safety net for:
    - Unauthenticated endpoints (/health, /metrics)
    - Token endpoint flooding (before auth kicks in)
    """

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"

        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)

        # IP-based rate limit as DDoS protection (generous limit)
        if not check_rate_limit(client_ip, limit=API_RATE_LIMIT * 2, window=60):
            return JSONResponse(
                {"error": "rate_limit_exceeded", "message": "Too many requests from this IP"},
                status_code=429,
                headers={"Retry-After": "60"}
            )

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
        response.headers["X-RateLimit-Limit"] = str(API_RATE_LIMIT)
        return response
