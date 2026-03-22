# OpenMemory Fly.io Deployment Strategy

## Overview

This document describes the deployment strategy for running OpenMemory on Fly.io with security-first practices, ensuring data sovereignty and protection against upstream backdoors.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Fly.io Platform                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐    ┌─────────────────────┐            │
│  │  openmemory-test    │    │  openmemory-prod    │            │
│  │  (Test Environment) │    │  (Production)       │            │
│  │                     │    │                     │            │
│  │  ┌───────────────┐  │    │  ┌───────────────┐  │            │
│  │  │ OpenMemory    │  │    │  │ OpenMemory    │  │            │
│  │  │ API + Auth    │  │    │  │ API + Auth    │  │            │
│  │  └───────────────┘  │    │  └───────────────┘  │            │
│  │         │           │    │         │           │            │
│  │  ┌──────┴──────┐    │    │  ┌──────┴──────┐    │            │
│  │  │   Volume    │    │    │  │   Volume    │    │            │
│  │  │ (1GB test)  │    │    │  │ (10GB prod) │    │            │
│  │  │ - Qdrant    │    │    │  │ - Qdrant    │    │            │
│  │  │ - SQLite    │    │    │  │ - SQLite    │    │            │
│  │  └─────────────┘    │    │  └─────────────┘    │            │
│  └─────────────────────┘    └─────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

## Branch Strategy

```
main (upstream) ───────────────────────────────────────────────────►
        │
        │ Security scan + pre-merge check
        │
        ▼
deploy ────────────────────────────────────────────────────────────►
        │                    │
        │ test deployment    │ production deployment
        ▼                    ▼
   openmemory-test      openmemory-prod
```

### Branch Purposes

| Branch | Purpose | Merges From | Deploys To |
|--------|---------|-------------|------------|
| `main` | Upstream mem0 code | Upstream repo | - |
| `deploy` | Deployment-ready code | `main` (after review) | Both environments |

### Why Separate Branches?

1. **No Merge Conflicts**: `deploy-fly-io/` folder is only in `deploy` branch
2. **Security Review**: All upstream changes go through security scan before merge
3. **Stable Deployments**: Production always deploys from verified code
4. **Easy Updates**: Pull latest from upstream without affecting deployment config

## Workflow

### 1. Initial Setup

```bash
# Clone repository
git clone https://github.com/mem0ai/mem0.git
cd mem0

# Create deploy branch from main
git checkout -b deploy
git push -u origin deploy

# Install fly CLI
curl -L https://fly.io/install.sh | sh
flyctl auth login

# Create apps
flyctl apps create openmemory-prod
flyctl apps create openmemory-test

# Set secrets (production)
flyctl secrets set -a openmemory-prod \
  OPENAI_API_KEY="sk-..." \
  AUTH_SECRET_KEY="$(openssl rand -hex 64)" \
  API_MASTER_KEY="$(openssl rand -hex 32)"

# Set secrets (test)
flyctl secrets set -a openmemory-test \
  OPENAI_API_KEY="sk-..." \
  AUTH_SECRET_KEY="$(openssl rand -hex 64)" \
  API_MASTER_KEY="$(openssl rand -hex 32)"

# First deployment
cd deploy-fly-io
./scripts/deploy.sh test
./scripts/deploy.sh production
```

### 2. Updating from Upstream

```bash
# On deploy branch
git fetch origin main

# Run pre-merge security check
./deploy-fly-io/hooks/pre-merge-check.sh main deploy

# Review the report in deploy-fly-io/docs/

# If checks pass, merge
git merge main

# Deploy to test first
./deploy-fly-io/scripts/deploy.sh test

# Test thoroughly, then deploy to production
./deploy-fly-io/scripts/deploy.sh production
```

### 3. Rolling Back

```bash
# List available versions
flyctl releases list -a openmemory-prod

# Rollback to specific version
./deploy-fly-io/scripts/rollback.sh production v123
```

## Authentication

The deployment uses a multi-layer authentication system:

### Authentication Methods

| Method | Use Case | Security Level |
|--------|----------|---------------|
| **JWT Bearer Token** | API clients, MCP connections | High (HS512) |
| **API Master Key** | Admin operations, token generation | Critical |
| **Signed Requests** | Server-to-server communication | High |

### Getting a Token

```bash
# Generate token using API Master Key
curl -X POST https://openmemory-prod.fly.dev/auth/token \
  -H "X-API-Key: your-master-key" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "my-user", "scopes": ["read", "write"]}'
```

### Using the Token

```bash
# MCP message with Bearer token
curl -X POST https://openmemory-prod.fly.dev/mcp/message \
  -H "Authorization: Bearer your-jwt-token" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "memory/add", "params": {...}}'
```

## MCP HTTP Transport

The deployment converts MCP from stdio to HTTP streamable transport:

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/mcp/message` | POST | Send single MCP message |
| `/mcp/batch` | POST | Send multiple messages |
| `/mcp/stream` | GET | SSE stream for responses |
| `/mcp/ws` | WS | WebSocket (alternative) |

### Example Usage

```python
import httpx

client = httpx.Client(
    base_url="https://openmemory-prod.fly.dev",
    headers={"Authorization": f"Bearer {token}"}
)

# Add memory
response = client.post("/mcp/message", json={
    "jsonrpc": "2.0",
    "id": "1",
    "method": "memory/add",
    "params": {
        "content": "User prefers dark mode",
        "user_id": "user123"
    }
})
```

## Database Backups

Fly Postgres handles backups automatically. To manage:

```bash
# Connect to database
flyctl postgres connect -a openmemory-db

# List backups
flyctl postgres barman list-backups -a openmemory-db

# Restore from backup
flyctl postgres barman restore -a openmemory-db <backup-id>
```

## Security Measures

### Claude AI Security Review

When `ANTHROPIC_API_KEY` is set, security checks include AI-powered code analysis using Claude.

**Setup:**
```bash
export ANTHROPIC_API_KEY='your-anthropic-api-key'
pip install anthropic
```

**What Claude Reviews:**

| Category | Examples |
|----------|----------|
| **Backdoors** | exec/eval with user input, hidden endpoints, reverse shells |
| **Data Exfiltration** | Secrets sent to external servers, credential harvesting |
| **Command Injection** | Unsanitized input to shell commands |
| **Vendor Lock-in** | Forced external service dependencies, undisablable telemetry |
| **Obfuscation** | Base64/hex encoded execution, intentionally confusing code |
| **Insecure Deserialization** | pickle.loads, yaml.load without SafeLoader |

**Verdicts:**

| Verdict | Meaning | Exit Code |
|---------|---------|-----------|
| `SAFE` | No security concerns | 0 |
| `SUSPICIOUS` | Needs human review | 1 |
| `DANGEROUS` | Block merge, critical issues | 2 |

**Manual Run:**
```bash
./hooks/claude_review.py --base main --target HEAD
```

**Review Reports:**
Claude review reports are saved to `docs/claude_review_*.json` with:
- Full analysis of each issue
- File locations and code snippets
- Severity assessments
- Recommendations

### Pre-Merge Checks

The `security-check.sh` script scans for:

1. **Suspicious Endpoints**: pastebin, ngrok, webhooks
2. **Data Exfiltration**: Base64-encoded secrets, credential sending
3. **Backdoors**: exec/eval with input, dangerous deserializers
4. **Vendor Lock-in**: mem0.ai API calls, undisablable telemetry
5. **Obfuscation**: Hex strings, unusually long lines

### Runtime Security

- Non-root container user
- Rate limiting with lockout
- Request signing verification
- Security headers (HSTS, XSS, etc.)
- Token revocation capability

### Network Security

- Force HTTPS
- HTTP/2 support
- No external network access (except configured endpoints)

## Monitoring

### Health Check

```bash
curl https://openmemory-prod.fly.dev/health
```

### Metrics

Prometheus metrics available at `/metrics`:

- `openmemory_requests_total` - Request count by method/endpoint/status
- `openmemory_request_latency_seconds` - Request latency histogram
- `openmemory_memory_operations_total` - Memory operation counts

### Logs

```bash
flyctl logs -a openmemory-prod
```

## Costs

| Environment | Configuration | Estimated Cost |
|-------------|--------------|----------------|
| Test | shared-cpu-1x, 512MB, 1GB storage | ~$2-5/month |
| Production | shared-cpu-2x, 1GB, 10GB storage | ~$10-20/month |

Note: Test environment uses auto-stop to minimize costs.

## Troubleshooting

### Common Issues

**1. Authentication Failures**

```bash
# Check if secrets are set
flyctl secrets list -a openmemory-prod

# Verify token
curl https://openmemory-prod.fly.dev/auth/verify \
  -H "Authorization: Bearer your-token"
```

**2. Volume Issues**

```bash
# Check volume status
flyctl volumes list -a openmemory-prod

# SSH into machine
flyctl ssh console -a openmemory-prod
ls -la /data/
```

**3. Deployment Failures**

```bash
# Check machine status
flyctl machines list -a openmemory-prod

# View detailed logs
flyctl logs -a openmemory-prod --instance MACHINE_ID
```

## File Structure

```
deploy-fly-io/
├── fly.toml                    # Production Fly.io config
├── fly-test.toml               # Test environment config
├── Dockerfile                  # Container build
├── api/
│   ├── requirements-extra.txt  # Additional dependencies
│   ├── auth_middleware.py      # Authentication system
│   ├── http_transport.py       # MCP HTTP transport
│   └── startup.py              # Application entrypoint
├── scripts/
│   ├── deploy.sh               # Deployment automation
│   ├── setup.sh                # Initial setup
│   ├── generate-secrets.sh     # Generate secrets
│   └── rollback.sh             # Version rollback
├── hooks/
│   ├── security-check.sh       # Security scanner
│   └── pre-merge-check.sh      # Pre-merge validation
└── docs/
    ├── DEPLOYMENT_STRATEGY.md  # This document
    └── SECURITY_EXCEPTIONS.md  # Documented false positives
```

## Provider Migration

This setup is designed to be portable. To migrate to another provider:

1. Keep `deploy-fly-io/` as reference
2. Create `deploy-{provider}/` with provider-specific configs
3. Reuse `api/` components (auth, transport, startup)
4. Update `hooks/` scripts for new deployment commands

The core application code remains unchanged; only deployment configuration differs.
