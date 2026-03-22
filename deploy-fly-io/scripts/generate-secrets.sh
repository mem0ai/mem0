#!/bin/bash
# Generate secrets for OpenMemory

echo "=========================================="
echo "   OpenMemory Secrets"
echo "=========================================="
echo ""

OAUTH_CLIENT_SECRET=$(openssl rand -hex 32)
UI_PASSWORD=$(openssl rand -base64 16 | tr -d '=/+' | head -c 16)
SESSION_SECRET=$(openssl rand -hex 32)

cat << EOF
# OAuth (for Claude Desktop / MCP clients)
OAUTH_CLIENT_ID=openmemory
OAUTH_CLIENT_SECRET=${OAUTH_CLIENT_SECRET}

# UI Dashboard Login
UI_USERNAME=admin
UI_PASSWORD=${UI_PASSWORD}
SESSION_SECRET=${SESSION_SECRET}

# Claude Desktop / Claude.ai Connector Settings:
#   OAuth Client ID: openmemory
#   OAuth Client Secret: ${OAUTH_CLIENT_SECRET}

# UI Dashboard Login:
#   Username: admin
#   Password: ${UI_PASSWORD}

# Fly.io Secrets (after creating Postgres):
# flyctl secrets set -a openmemory-prod \\
#   OPENAI_API_KEY="sk-..." \\
#   OAUTH_CLIENT_ID="openmemory" \\
#   OAUTH_CLIENT_SECRET="${OAUTH_CLIENT_SECRET}" \\
#   UI_USERNAME="admin" \\
#   UI_PASSWORD="${UI_PASSWORD}" \\
#   SESSION_SECRET="${SESSION_SECRET}" \\
#   PG_HOST="openmemory-db.internal" \\
#   PG_PORT="5432" \\
#   PG_DB="openmemory" \\
#   PG_USER="postgres" \\
#   PG_PASSWORD="<from-postgres-attach>"

# GitHub Secrets (Settings > Secrets > Actions):
#   FLY_API_TOKEN: run 'flyctl tokens create deploy'
#   ANTHROPIC_API_KEY: from console.anthropic.com

# Local .env file:
OPENAI_API_KEY=sk-...
OAUTH_CLIENT_ID=openmemory
OAUTH_CLIENT_SECRET=${OAUTH_CLIENT_SECRET}
UI_USERNAME=admin
UI_PASSWORD=${UI_PASSWORD}
SESSION_SECRET=${SESSION_SECRET}
EOF

echo ""
echo "=========================================="
echo "Save these secrets securely!"
echo "=========================================="
