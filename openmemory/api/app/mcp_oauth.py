"""
Abstract OAuth 2.1 Router for MCP Servers
Provides the endpoints required by Anthropic's Claude Cloud.

OAuth 2.1 Strict Compliance:
- PKCE is mandatory for all Authorization Code flows.
- Tokens are not allowed in the URL query string.
- Device Authorization Grant (RFC 8628) is supported for headless AI CLI agents.
- Refresh Tokens are rotated.

Usage:
1. Drop this file into your FastAPI app directory.
2. In your main app:
   from .mcp_oauth import oauth_router, verify_oauth_token
   app.include_router(oauth_router)
3. Use the `verify_oauth_token` dependency on your MCP endpoints.
"""

import os
import time
import secrets
import hashlib
import base64
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

oauth_router = APIRouter()
security = HTTPBearer(auto_error=False)

# In-memory stores for the proxy
# For production, use Redis or a database.
auth_codes = {}
access_tokens = {}
refresh_tokens = {}
device_codes = {}

OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID", "claude")
SERVER_PASSWORD = os.getenv("MCP_SERVER_AUTH_TOKEN", "default_password")

def generate_token():
    return secrets.token_hex(32)

def verify_pkce(verifier: str, challenge: str) -> bool:
    """Verify PKCE S256 challenge"""
    if not verifier or not challenge:
        return False
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    computed_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')
    return secrets.compare_digest(computed_challenge, challenge)

@oauth_router.get("/.well-known/oauth-authorization-server")
async def oauth_metadata(request: Request):
    """OAuth 2.1 Authorization Server Metadata (RFC 8414)"""
    base_url = str(request.base_url).rstrip("/")
    return JSONResponse({
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/oauth/authorize",
        "token_endpoint": f"{base_url}/oauth/token",
        "registration_endpoint": f"{base_url}/oauth/register",
        "device_authorization_endpoint": f"{base_url}/oauth/device/authorize",
        "scopes_supported": ["mcp"],
        "response_types_supported": ["code"],
        "grant_types_supported": [
            "authorization_code",
            "refresh_token",
            "urn:ietf:params:oauth:grant-type:device_code"
        ],
        "token_endpoint_auth_methods_supported": ["none"],
        "code_challenge_methods_supported": ["S256"]
    })

@oauth_router.post("/oauth/register")
async def register_client(request: Request):
    """Dynamic Client Registration (RFC 7591)"""
    try:
        data = await request.json()
    except Exception:
        data = {}
    return JSONResponse({
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uris": data.get("redirect_uris", []),
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token", "urn:ietf:params:oauth:grant-type:device_code"],
        "response_types": ["code"]
    }, status_code=201)

@oauth_router.get("/oauth/authorize")
async def authorize(
    client_id: str,
    redirect_uri: str,
    response_type: str,
    code_challenge: str,
    code_challenge_method: str,
    state: str = None,
    scope: str = None
):
    """Authorization Endpoint (RFC 6749) with PKCE (RFC 7636)"""
    if response_type != "code":
        raise HTTPException(status_code=400, detail="unsupported_response_type")
    if code_challenge_method != "S256":
        raise HTTPException(status_code=400, detail="code_challenge_method must be S256")
    
    req_id = generate_token()
    auth_codes[req_id] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "state": state,
        "scope": scope,
        "expires": time.time() + 300
    }
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Authorize MCP Access</title>
        <style>
            body {{ font-family: system-ui, sans-serif; max-width: 480px; margin: 80px auto; padding: 0 20px; background: #f5f5f5; }}
            .card {{ background: #fff; border-radius: 12px; padding: 32px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
            h1 {{ font-size: 1.3em; margin: 0 0 8px; }}
            input {{ display: block; width: 100%; padding: 10px; margin-bottom: 20px; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; }}
            .btn {{ display: inline-block; padding: 12px 32px; border: none; border-radius: 8px; font-size: 1em; cursor: pointer; background: #2563eb; color: #fff; width: 100%; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Authorize MCP Access</h1>
            <p><strong>{client_id}</strong> is requesting access.</p>
            <form method="POST" action="/oauth/authorize/decision">
                <input type="hidden" name="req_id" value="{req_id}">
                <label>Server Password:</label>
                <input type="password" name="password" required>
                <button type="submit" name="decision" value="approve" class="btn">Approve</button>
            </form>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(html)

@oauth_router.post("/oauth/authorize/decision")
async def authorize_decision(req_id: str = Form(...), decision: str = Form(...), password: str = Form(None)):
    req = auth_codes.pop(req_id, None)
    if not req or time.time() > req["expires"]:
        raise HTTPException(status_code=400, detail="Session expired")
    
    if decision != "approve" or password != SERVER_PASSWORD:
        return RedirectResponse(f"{req['redirect_uri']}?error=access_denied&state={req['state']}", status_code=302)
    
    auth_code = generate_token()
    auth_codes[auth_code] = req
    
    redirect_url = f"{req['redirect_uri']}?code={auth_code}&state={req['state']}"
    return RedirectResponse(redirect_url, status_code=302)

@oauth_router.post("/oauth/device/authorize")
async def device_authorize(client_id: str = Form(...), scope: str = Form(None), request: Request = None):
    """Device Authorization Request (RFC 8628)"""
    device_code = generate_token()
    user_code = secrets.token_hex(4).upper()
    
    device_codes[device_code] = {
        "client_id": client_id,
        "user_code": user_code,
        "scope": scope,
        "status": "authorization_pending",
        "expires": time.time() + 900
    }
    
    base_url = str(request.base_url).rstrip("/")
    return JSONResponse({
        "device_code": device_code,
        "user_code": user_code,
        "verification_uri": f"{base_url}/oauth/device",
        "verification_uri_complete": f"{base_url}/oauth/device?user_code={user_code}",
        "expires_in": 900,
        "interval": 5
    })

@oauth_router.get("/oauth/device")
async def device_verification_page(user_code: str = ""):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Device Login</title><style>body{{font-family:sans-serif;max-width:400px;margin:50px auto;}}input,button{{display:block;width:100%;margin-bottom:15px;padding:10px;}}</style></head>
    <body>
        <h2>Device Authorization</h2>
        <form method="POST" action="/oauth/device/verify">
            <label>User Code:</label>
            <input type="text" name="user_code" value="{user_code}" required>
            <label>Server Password:</label>
            <input type="password" name="password" required>
            <button type="submit">Approve</button>
        </form>
    </body>
    </html>
    """
    return HTMLResponse(html)

@oauth_router.post("/oauth/device/verify")
async def device_verify(user_code: str = Form(...), password: str = Form(...)):
    if password != SERVER_PASSWORD:
        return HTMLResponse("Invalid password.", status_code=401)
        
    user_code = user_code.upper().strip()
    for dc, data in device_codes.items():
        if data["user_code"] == user_code and data["status"] == "authorization_pending":
            if time.time() > data["expires"]:
                return HTMLResponse("Code expired.", status_code=400)
            data["status"] = "approved"
            return HTMLResponse("Success! You may close this window. Your device is now connected.")
            
    return HTMLResponse("Invalid user code.", status_code=400)

@oauth_router.post("/oauth/token")
async def token(
    grant_type: str = Form(...),
    code: str = Form(None),
    client_id: str = Form(...),
    redirect_uri: str = Form(None),
    code_verifier: str = Form(None),
    refresh_token: str = Form(None),
    device_code: str = Form(None)
):
    """Token Endpoint (RFC 6749) + Device Grant + Refresh Token Rotation"""
    
    if grant_type == "authorization_code":
        req = auth_codes.pop(code, None)
        if not req:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        if req["redirect_uri"] != redirect_uri:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        if not verify_pkce(code_verifier, req["code_challenge"]):
            return JSONResponse({"error": "invalid_grant", "error_description": "PKCE verification failed"}, status_code=400)
        scope = req["scope"]
        
    elif grant_type == "urn:ietf:params:oauth:grant-type:device_code":
        req = device_codes.get(device_code)
        if not req:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        if time.time() > req["expires"]:
            device_codes.pop(device_code, None)
            return JSONResponse({"error": "expired_token"}, status_code=400)
        if req["status"] == "authorization_pending":
            return JSONResponse({"error": "authorization_pending"}, status_code=400)
        if req["status"] != "approved":
            return JSONResponse({"error": "access_denied"}, status_code=400)
        
        # Consume the device code
        device_codes.pop(device_code, None)
        scope = req["scope"]
        
    elif grant_type == "refresh_token":
        req = refresh_tokens.pop(refresh_token, None)
        if not req:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        if time.time() > req["expires"]:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        # Invalidate old access token if we tracked them bi-directionally
        access_tokens.pop(req["access_token"], None)
        scope = req["scope"]
        
    else:
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
        
    acc_token = generate_token()
    ref_token = generate_token()
    
    access_tokens[acc_token] = {"expires": time.time() + 3600, "scope": scope}
    refresh_tokens[ref_token] = {"access_token": acc_token, "expires": time.time() + 2592000, "scope": scope}
    
    return JSONResponse({
        "access_token": acc_token,
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_token": ref_token,
        "scope": scope
    })

def verify_oauth_or_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """FastAPI Dependency to verify either the static API Key or an OAuth JWT."""
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization Header",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    token = credentials.credentials
    
    if SERVER_PASSWORD and token == SERVER_PASSWORD:
        return token
        
    token_data = access_tokens.get(token)
    if token_data and time.time() < token_data["expires"]:
        return token
        
    raise HTTPException(
        status_code=401,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
