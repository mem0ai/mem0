# MCP OAuth 2.1 Implementation Roadmap

*Last Updated: June 2025*
*Status: Planning Phase*

## Executive Summary

This document outlines the implementation plan for adding OAuth 2.1 support to Jean Memory's MCP (Model Context Protocol) integration while maintaining backward compatibility with our current user-ID-based authentication system.

## Current Architecture Assessment

### ✅ What We Have (Working)
```json
// Current Claude Desktop Configuration
{
  "mcpServers": {
    "api-jeanmemory-com": {
      "command": "npx",
      "args": [
        "-y",
        "supergateway",
        "--sse", 
        "https://api.jeanmemory.com/mcp/claude/sse/66d3d5d1-fc48-44a7-bbc0-1efa2e164fad"
      ]
    }
  }
}
```

**Architecture:** `Claude Desktop → supergateway (proxy) → Our SSE Endpoints`

**Current Endpoints:**
- `/mcp/{client_name}/sse/{user_id}` (SSE connection)
- `/mcp/{client_name}/messages/{user_id}` (HTTP messages)
- `/mcp/chatgpt/sse/{user_id}` (ChatGPT specific)

**Authentication Method:** User ID embedded in URL path

### ✅ Advantages of Current System
- Simple user onboarding (just copy/paste user ID)
- No complex OAuth flows for users
- Works across all MCP clients (Claude, Cursor, ChatGPT)
- Stateless authentication
- Easy debugging and monitoring

## OAuth 2.1 Requirements

### 📋 MCP Specification Compliance (2025-06-18)

To be fully compliant with the latest MCP specification, we need to implement:

#### Required OAuth Metadata Endpoints
```
/.well-known/oauth-protected-resource  - Resource server metadata
/.well-known/oauth-authorization-server - Authorization server metadata
```

#### Required OAuth Flow Endpoints  
```
/oauth/authorize  - Authorization endpoint (user consent)
/oauth/token     - Token exchange endpoint
/oauth/register  - Dynamic client registration (recommended)
```

#### Required OAuth Features
- **PKCE (Proof Key for Code Exchange)** - Mandatory for security
- **Authorization Code Grant** - Primary flow for user authorization
- **Access Token Validation** - JWT or opaque token validation
- **Scope-based Authorization** - Fine-grained permissions

## Implementation Phases

### 🚀 Phase 1: OAuth Foundation (Weeks 1-2)
**Goal:** Add OAuth metadata endpoints while maintaining current functionality

#### 1.1 Add OAuth Metadata Endpoints
```python
# Add to openmemory/api/app/mcp_server.py

@mcp_router.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource_metadata():
    return {
        "authorization_servers": [
            "https://api.jeanmemory.com"
        ],
        "resource": "https://api.jeanmemory.com/mcp",
        "scopes_supported": [
            "mcp:search",
            "mcp:add_memory", 
            "mcp:list_memories",
            "mcp:delete_memories",
            "mcp:deep_search"
        ]
    }

@mcp_router.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server_metadata():
    return {
        "issuer": "https://api.jeanmemory.com",
        "authorization_endpoint": "https://api.jeanmemory.com/oauth/authorize",
        "token_endpoint": "https://api.jeanmemory.com/oauth/token", 
        "registration_endpoint": "https://api.jeanmemory.com/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": [
            "mcp:search", "mcp:add_memory", "mcp:list_memories",
            "mcp:delete_memories", "mcp:deep_search"
        ]
    }
```

#### 1.2 Database Schema Extensions
```python
# Add to openmemory/api/app/models.py

class OAuthClient(Base):
    __tablename__ = "oauth_clients"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(String, unique=True, nullable=False)
    client_secret_hash = Column(String, nullable=True)  # For confidential clients
    client_name = Column(String, nullable=False)
    redirect_uris = Column(JSON, nullable=False)  # Array of allowed redirect URIs
    scope = Column(String, nullable=False, default="mcp:search mcp:add_memory")
    client_type = Column(String, nullable=False)  # "public" or "confidential"
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

class OAuthAuthorizationCode(Base):
    __tablename__ = "oauth_authorization_codes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String, unique=True, nullable=False)
    client_id = Column(String, ForeignKey("oauth_clients.client_id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    redirect_uri = Column(String, nullable=False)
    scope = Column(String, nullable=False)
    code_challenge = Column(String, nullable=True)  # PKCE
    code_challenge_method = Column(String, nullable=True)  # S256
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class OAuthAccessToken(Base):
    __tablename__ = "oauth_access_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String, unique=True, nullable=False)  # The actual token
    client_id = Column(String, ForeignKey("oauth_clients.client_id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    scope = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 🔐 Phase 2: OAuth Authorization Flow (Weeks 3-4)
**Goal:** Implement complete OAuth 2.1 authorization code flow

#### 2.1 Authorization Endpoint
```python
# Add to openmemory/api/app/routers/oauth.py

@oauth_router.get("/authorize")
async def oauth_authorize(
    client_id: str,
    response_type: str,
    redirect_uri: str,
    scope: str,
    state: str = None,
    code_challenge: str = None,
    code_challenge_method: str = None,
    request: Request = None
):
    """OAuth 2.1 Authorization Endpoint with PKCE"""
    
    # Validate client
    client = await get_oauth_client(client_id)
    if not client:
        raise HTTPException(400, "Invalid client_id")
    
    # Validate redirect URI
    if redirect_uri not in client.redirect_uris:
        raise HTTPException(400, "Invalid redirect_uri")
    
    # Check if user is authenticated
    user = await get_current_user_optional(request)
    if not user:
        # Redirect to login with return URL
        login_url = f"/login?return_to={urllib.parse.quote(str(request.url))}"
        return RedirectResponse(login_url)
    
    # Show consent screen (if not already consented)
    if not await has_user_consented(user.id, client_id, scope):
        return await show_consent_screen(user, client, scope, request.url)
    
    # Generate authorization code
    auth_code = await create_authorization_code(
        client_id=client_id,
        user_id=user.id,
        redirect_uri=redirect_uri,
        scope=scope,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method
    )
    
    # Redirect back to client
    callback_url = f"{redirect_uri}?code={auth_code.code}"
    if state:
        callback_url += f"&state={state}"
    
    return RedirectResponse(callback_url)
```

#### 2.2 Token Endpoint
```python
@oauth_router.post("/token")
async def oauth_token(
    grant_type: str = Form(...),
    code: str = Form(None),
    redirect_uri: str = Form(None),
    client_id: str = Form(...),
    client_secret: str = Form(None),
    code_verifier: str = Form(None)  # PKCE
):
    """OAuth 2.1 Token Endpoint"""
    
    if grant_type == "authorization_code":
        return await handle_authorization_code_grant(
            code, redirect_uri, client_id, client_secret, code_verifier
        )
    elif grant_type == "refresh_token":
        return await handle_refresh_token_grant(...)
    else:
        raise HTTPException(400, "Unsupported grant_type")

async def handle_authorization_code_grant(code, redirect_uri, client_id, client_secret, code_verifier):
    """Handle authorization code exchange for access token"""
    
    # Validate authorization code
    auth_code = await get_authorization_code(code)
    if not auth_code or auth_code.used or auth_code.expires_at < datetime.utcnow():
        raise HTTPException(400, "Invalid or expired authorization code")
    
    # Validate PKCE
    if auth_code.code_challenge:
        if not code_verifier:
            raise HTTPException(400, "Missing code_verifier")
        
        expected_challenge = base64url_encode(sha256(code_verifier.encode()).digest())
        if expected_challenge != auth_code.code_challenge:
            raise HTTPException(400, "Invalid code_verifier")
    
    # Mark code as used
    auth_code.used = True
    await save_authorization_code(auth_code)
    
    # Generate access token
    access_token = await create_access_token(
        client_id=client_id,
        user_id=auth_code.user_id,
        scope=auth_code.scope
    )
    
    return {
        "access_token": access_token.token,
        "token_type": "bearer",
        "expires_in": 3600,  # 1 hour
        "scope": access_token.scope
    }
```

### 🔄 Phase 3: Dual Authentication Support (Week 5)
**Goal:** Support both OAuth and legacy user-ID authentication

#### 3.1 Unified Authentication Middleware
```python
# Update openmemory/api/app/mcp_server.py

async def authenticate_mcp_request(request: Request) -> User:
    """Unified authentication supporting both OAuth and legacy user-ID"""
    
    # Try OAuth Bearer token first
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user = await validate_oauth_access_token(token)
        if user:
            return user
    
    # Fall back to URL-based user ID (legacy)
    user_id = None
    path_parts = request.url.path.split('/')
    
    # Extract user_id from various URL patterns
    if len(path_parts) >= 4 and path_parts[1] == "mcp":
        if path_parts[2] in ["claude", "cursor", "chatgpt"]:
            user_id = path_parts[4] if len(path_parts) > 4 else None
        else:
            user_id = path_parts[2]  # /mcp/{user_id}/sse format
    
    if user_id:
        user = await get_user_by_id(user_id)
        if user:
            return user
    
    raise HTTPException(401, "Authentication required")

async def validate_oauth_access_token(token: str) -> User:
    """Validate OAuth access token"""
    access_token = await get_access_token(token)
    if not access_token or access_token.expires_at < datetime.utcnow():
        return None
    
    return await get_user_by_id(access_token.user_id)
```

### 📱 Phase 4: Client Migration Support (Week 6)
**Goal:** Provide migration paths for different MCP clients

#### 4.1 Claude Desktop OAuth Configuration
```json
// New OAuth-based configuration
{
  "mcpServers": {
    "jean-memory-oauth": {
      "url": "https://api.jeanmemory.com/mcp",
      "auth": {
        "type": "oauth2",
        "authorization_url": "https://api.jeanmemory.com/oauth/authorize",
        "token_url": "https://api.jeanmemory.com/oauth/token",
        "scope": "mcp:search mcp:add_memory mcp:list_memories"
      }
    }
  }
}
```

#### 4.2 supergateway OAuth Support
Monitor and update when `supergateway` adds OAuth support:
```json
// Future supergateway OAuth configuration (when available)
{
  "mcpServers": {
    "jean-memory": {
      "command": "npx",
      "args": [
        "-y",
        "supergateway",
        "--oauth",
        "https://api.jeanmemory.com/mcp"
      ],
      "env": {
        "OAUTH_CLIENT_ID": "claude-desktop"
      }
    }
  }
}
```

## Timeline and Deadlines

### 🎯 Recommended Implementation Timeline

| Phase | Timeline | Priority | Risk |
|-------|----------|----------|------|
| Phase 1: OAuth Foundation | Q3 2025 | Medium | Low |
| Phase 2: OAuth Flow | Q4 2025 | Medium | Low |
| Phase 3: Dual Auth | Q4 2025 | High | Medium |
| Phase 4: Client Migration | Q1 2026 | Low | Low |

### ⏰ External Factors

**No Hard Deadlines:** 
- MCP OAuth is currently "SHOULD" not "MUST"
- Claude Desktop still supports legacy auth
- No announced deprecation dates

**Watch for Changes:**
- Claude Desktop release notes
- supergateway OAuth support
- MCP specification updates
- Enterprise customer requirements

## Migration Strategy

### 🔄 Backward Compatibility Approach

**Maintain Both Systems:**
1. **Legacy endpoints** for existing users: `/mcp/{client}/sse/{user_id}`
2. **OAuth endpoints** for new users: `/mcp` with Bearer token
3. **Gradual migration** with user choice
4. **No forced migration** until industry requires it

### 📋 User Migration Options

**Option A: Keep Current Setup**
Users can continue with existing supergateway + user-ID approach

**Option B: Migrate to OAuth**
Users can switch to OAuth for enhanced security and enterprise compliance

## Testing Strategy

### 🧪 Testing Phases

#### Phase 1: OAuth Metadata Testing
- Verify `.well-known` endpoints return correct metadata
- Test with MCP Inspector tool
- Validate JSON schema compliance

#### Phase 2: OAuth Flow Testing
- Test authorization code flow with PKCE
- Verify token generation and validation
- Test scope-based access control

#### Phase 3: Client Integration Testing
- Test with Claude Desktop OAuth mode
- Test with updated supergateway (when available)
- Verify backward compatibility with existing setups

## Security Considerations

### 🔒 OAuth Security Requirements

**Mandatory Security Features:**
- **PKCE** for all authorization code flows
- **State parameter** to prevent CSRF attacks
- **Secure token storage** (httpOnly cookies or secure headers)
- **Token expiration** (1-hour access tokens, longer refresh tokens)
- **Scope validation** for all API requests

**Additional Security Measures:**
- Rate limiting on OAuth endpoints
- Audit logging of all OAuth flows
- Regular token rotation
- Secure client secret storage (for confidential clients)

## Monitoring and Metrics

### 📊 Key Metrics to Track

**Authentication Metrics:**
- OAuth vs Legacy authentication usage rates
- OAuth flow success/failure rates
- Token refresh rates
- Authentication error rates

**Migration Metrics:**
- Number of users migrated to OAuth
- Client type distribution (Claude, Cursor, ChatGPT)
- Error rates by authentication method

## Support and Documentation

### 📚 Documentation Updates Required

1. **User Migration Guide**: How to switch from user-ID to OAuth
2. **OAuth Setup Guide**: Step-by-step OAuth configuration for each client
3. **Developer Guide**: OAuth implementation details for custom integrations
4. **Troubleshooting Guide**: Common OAuth issues and solutions

### 🎯 Success Criteria

**Phase 1 Complete:**
- [ ] OAuth metadata endpoints returning valid responses
- [ ] Database schema deployed to production
- [ ] Backward compatibility maintained

**Phase 2 Complete:**
- [ ] Full OAuth authorization code flow working
- [ ] PKCE implementation tested and validated
- [ ] Token generation and validation working

**Phase 3 Complete:**
- [ ] Dual authentication system deployed
- [ ] Zero downtime for existing users
- [ ] New OAuth users can authenticate successfully

**Phase 4 Complete:**
- [ ] Claude Desktop OAuth configuration documented
- [ ] supergateway OAuth support integrated (when available)
- [ ] Migration guides published

## Risk Assessment

### ⚠️ Implementation Risks

**Low Risk:**
- OAuth metadata endpoints (simple JSON responses)
- Database schema additions (non-breaking)

**Medium Risk:**
- OAuth authorization flow complexity
- PKCE implementation details
- Token security and storage

**High Risk:**
- Breaking existing user workflows
- supergateway dependency changes
- Client compatibility issues

### 🛡️ Mitigation Strategies

**Risk Mitigation:**
- Extensive testing in staging environment
- Gradual rollout with feature flags
- Maintain legacy support indefinitely
- Monitor authentication success rates
- Provide clear rollback procedures

## Conclusion

This OAuth implementation plan provides a path to MCP 2.1 compliance while maintaining backward compatibility and user choice. The phased approach allows for careful testing and gradual migration without disrupting existing users.

**Key Principles:**
- **Backward Compatibility**: Never break existing user setups
- **User Choice**: Allow users to choose their authentication method
- **Future-Proofing**: Be ready when OAuth becomes mandatory
- **Enterprise Ready**: Support enterprise security requirements

The timeline is flexible and can be adjusted based on industry developments and user needs. The most important factor is maintaining a stable, reliable service for existing users while preparing for future requirements. 