# OpenMemory Fly.io Deployment

Self-hosted OpenMemory on Fly.io with OAuth for Claude Desktop/Claude.ai.

## Local Testing

```bash
cp deploy-fly-io/.env.example .env && vim .env  # Add OPENAI_API_KEY, NEON_CONNECTION_STRING, run generate-secrets.sh
set -a && source .env && set +a && docker compose -f deploy-fly-io/docker-compose.yml up --build
```

| Service | URL |
|---------|-----|
| UI | http://localhost:3000 |
| API | http://localhost:8765 |

## Neon Postgres Setup

1. Create account at [neon.tech](https://neon.tech)
2. Create project → copy **Connection string**
3. Run in SQL Editor: `CREATE EXTENSION vector;`
4. Add to `.env`: `NEON_CONNECTION_STRING="<your-connection-string>"` (quotes required)

## Fly.io Setup

### Prerequisites

```bash
flyctl auth login
./deploy-fly-io/scripts/generate-secrets.sh  # Generates OAuth + UI credentials → appends to .env
```

### Setup with Claude + Fly MCP Server

Configure Claude to manage Fly.io apps directly:

```bash
fly mcp server --claude
```

See [Fly MCP Server docs](https://fly.io/docs/flyctl/mcp-server/) for details.

Then ask Claude to:
1. Create apps `openmemory-prod` and `openmemory-test`
2. Set secrets from your `.env` file (OPENAI_API_KEY, NEON_CONNECTION_STRING, OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET, UI_USERNAME, UI_PASSWORD, SESSION_SECRET)
3. Deploy the app

### GitHub Secrets (for CI/CD)

| Secret | How to Get |
|--------|------------|
| `FLY_API_TOKEN` | `flyctl tokens create deploy` |
| `ANTHROPIC_API_KEY` | console.anthropic.com |

## Claude Desktop / Claude.ai

### Claude.ai (Web)

1. Go to [claude.ai](https://claude.ai) → Settings (gear icon) → **Connectors**
2. Click **Add Connector**
3. Fill in:

| Field | Value |
|-------|-------|
| Name | OpenMemory |
| URL | `https://openmemory-prod.fly.dev/mcp/` |
| OAuth Client ID | `openmemory` |
| OAuth Client Secret | Value from generate-secrets.sh |

4. Click **Add** → Complete OAuth flow when prompted
5. Start a new chat and type "remember that I prefer dark mode" to test

### Claude Desktop

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "openmemory": {
      "url": "https://openmemory-prod.fly.dev/mcp/",
      "oauth": {
        "client_id": "openmemory",
        "client_secret": "<from-generate-secrets>"
      }
    }
  }
}
```
Restart Claude Desktop after saving.

## Deploy

```bash
git push origin deploy                    # Auto-deploys to test
git tag v1.0.0 && git push origin v1.0.0  # Tag release
git tag -f latest-release v1.0.0 && git push origin latest-release --force  # Deploy to prod
```
