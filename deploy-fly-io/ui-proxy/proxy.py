"""
Auth Proxy for OpenMemory UI

Sits in front of the UI and handles authentication:
1. Shows login page if no valid session
2. Validates username/password
3. Proxies all requests to the UI after authentication
"""

import os
import secrets
import hmac
import httpx
from datetime import datetime, timedelta, timezone
from string import Template

from fastapi import FastAPI, Request, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

UI_URL = os.environ.get("UI_URL", "http://openmemory-ui:3000")
SESSION_SECRET = os.environ.get("SESSION_SECRET", secrets.token_hex(32))
REQUIRE_AUTH = os.environ.get("REQUIRE_AUTH", "true").lower() == "true"
UI_USERNAME = os.environ.get("UI_USERNAME", "admin")
UI_PASSWORD = os.environ.get("UI_PASSWORD")
SESSION_MAX_AGE = int(os.environ.get("SESSION_MAX_AGE", "86400"))  # 24 hours

app = FastAPI(title="OpenMemory UI Proxy")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, max_age=SESSION_MAX_AGE)

# Simple HTML login page (using Template for safe substitution)
LOGIN_PAGE_TEMPLATE = Template("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenMemory - Login</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #09090b;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 1rem;
        }
        .card {
            background: #18181b;
            border: 1px solid #27272a;
            border-radius: 0.75rem;
            padding: 2rem;
            width: 100%;
            max-width: 400px;
        }
        .header {
            text-align: center;
            margin-bottom: 1.5rem;
        }
        .icon {
            width: 48px;
            height: 48px;
            background: #27272a;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 1rem;
        }
        .icon svg { width: 24px; height: 24px; color: #a1a1aa; }
        h1 { color: #fff; font-size: 1.5rem; margin-bottom: 0.5rem; }
        .subtitle { color: #71717a; font-size: 0.875rem; }
        .error {
            background: rgba(220, 38, 38, 0.1);
            border: 1px solid #991b1b;
            color: #fca5a5;
            padding: 0.75rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
            font-size: 0.875rem;
        }
        .form-group { margin-bottom: 1rem; }
        label {
            display: block;
            color: #d4d4d8;
            font-size: 0.875rem;
            margin-bottom: 0.5rem;
        }
        input {
            width: 100%;
            padding: 0.75rem;
            background: #27272a;
            border: 1px solid #3f3f46;
            border-radius: 0.5rem;
            color: #fff;
            font-size: 1rem;
        }
        input::placeholder { color: #71717a; }
        input:focus { outline: none; border-color: #fff; }
        button {
            width: 100%;
            padding: 0.75rem;
            background: #fff;
            color: #000;
            border: none;
            border-radius: 0.5rem;
            font-size: 1rem;
            font-weight: 500;
            cursor: pointer;
            margin-top: 0.5rem;
        }
        button:hover { background: #e4e4e7; }
        .hint {
            text-align: center;
            color: #52525b;
            font-size: 0.75rem;
            margin-top: 1rem;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="header">
            <div class="icon">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
            </div>
            <h1>OpenMemory</h1>
            <p class="subtitle">Enter your credentials to access the dashboard</p>
        </div>
        $error
        <form method="POST" action="/auth/login">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" placeholder="admin" required>
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" placeholder="Enter your password" required>
            </div>
            <button type="submit">Sign in</button>
        </form>
        <p class="hint">Credentials from your .env file (UI_USERNAME / UI_PASSWORD)</p>
    </div>
</body>
</html>""")


def validate_credentials(username: str, password: str) -> bool:
    """Validate username and password using constant-time comparison."""
    if not UI_PASSWORD:
        return False
    return (
        hmac.compare_digest(username, UI_USERNAME) and
        hmac.compare_digest(password, UI_PASSWORD)
    )


@app.get("/auth/login")
async def login_page(error: str = None):
    """Show login page."""
    error_html = f'<div class="error">{error}</div>' if error else ""
    html = LOGIN_PAGE_TEMPLATE.substitute(error=error_html)
    return HTMLResponse(html)


@app.post("/auth/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    """Authenticate and create session."""
    if validate_credentials(username, password):
        request.session["authenticated"] = True
        request.session["username"] = username
        request.session["expires_at"] = (
            datetime.now(timezone.utc) + timedelta(seconds=SESSION_MAX_AGE)
        ).isoformat()
        return RedirectResponse(url="/", status_code=303)
    else:
        error = "Invalid username or password"
        return RedirectResponse(url=f"/auth/login?error={error}", status_code=303)


@app.get("/auth/logout")
async def logout(request: Request):
    """Clear session and redirect to login."""
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=303)


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy(request: Request, path: str):
    """Proxy all requests to the UI after checking auth."""
    # Check authentication
    if REQUIRE_AUTH:
        authenticated = request.session.get("authenticated")
        expires_at = request.session.get("expires_at")

        if not authenticated or not expires_at:
            return RedirectResponse(url="/auth/login", status_code=303)

        # Check expiry
        try:
            exp = datetime.fromisoformat(expires_at)
            if datetime.now(timezone.utc) > exp:
                request.session.clear()
                return RedirectResponse(url="/auth/login", status_code=303)
        except Exception:
            request.session.clear()
            return RedirectResponse(url="/auth/login", status_code=303)

    # Build target URL
    target_url = f"{UI_URL}/{path}"
    if request.query_params:
        target_url += f"?{request.query_params}"

    # Forward request
    try:
        async with httpx.AsyncClient() as client:
            # Read body for non-GET requests
            body = None
            if request.method != "GET":
                body = await request.body()

            response = await client.request(
                method=request.method,
                url=target_url,
                headers={
                    k: v for k, v in request.headers.items()
                    if k.lower() not in ["host", "content-length"]
                },
                content=body,
                timeout=30.0,
                follow_redirects=False,
            )

        # Return proxied response
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers={
                k: v for k, v in response.headers.items()
                if k.lower() not in ["content-encoding", "transfer-encoding", "content-length"]
            },
        )
    except Exception as e:
        return JSONResponse(
            {"error": "Proxy error", "detail": str(e)},
            status_code=502,
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001)
