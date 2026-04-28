#!/bin/bash
set -e

API_URL="${API_URL:-http://localhost:8888}"
DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:3000}"
EMAIL="${EMAIL:-admin@mem0.dev}"
PASSWORD="${PASSWORD:-$(python3 -c 'import secrets; print(secrets.token_urlsafe(16))')}"
NAME="${NAME:-Admin}"
OUTPUT="${OUTPUT:-text}"

echo "=== Mem0 Self-Hosted Seed ==="
echo "API: $API_URL"
echo ""

# Check if setup is needed
SETUP=$(curl -s "$API_URL/auth/setup-status")
NEEDS_SETUP=$(echo "$SETUP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('needsSetup', True))" 2>/dev/null || echo "True")

if [ "$NEEDS_SETUP" = "True" ]; then
  echo "Creating admin account..."
  REGISTER_PAYLOAD=$(NAME="$NAME" EMAIL="$EMAIL" PASSWORD="$PASSWORD" python3 -c 'import json, os; print(json.dumps({"name": os.environ["NAME"], "email": os.environ["EMAIL"], "password": os.environ["PASSWORD"]}))')
  REGISTER=$(curl -s -X POST "$API_URL/auth/register" \
    -H "Content-Type: application/json" \
    -d "$REGISTER_PAYLOAD")
  echo "$REGISTER" | python3 -c "import sys,json; d=json.load(sys.stdin); print('  Admin created.' if 'access_token' in d else f'  Error: {d}')" 2>/dev/null
else
  echo "Admin already exists, logging in..."
fi

# Login
echo "Logging in..."
LOGIN_PAYLOAD=$(EMAIL="$EMAIL" PASSWORD="$PASSWORD" python3 -c 'import json, os; print(json.dumps({"email": os.environ["EMAIL"], "password": os.environ["PASSWORD"]}))')
LOGIN=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "$LOGIN_PAYLOAD")
TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
  echo "  Login failed: $LOGIN"
  echo "  Admin exists but PASSWORD didn't match. Recover with:"
  echo "    make clean && make bootstrap                              (wipes data)"
  echo "    make reset-admin-password EMAIL=<email> PASSWORD=<pass>   (keeps data)"
  exit 1
fi
echo "  Logged in."

# Create API key
echo "Creating API key..."
KEY_RESP=$(curl -s -X POST "$API_URL/api-keys" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"label": "dev-seed-key"}')
API_KEY=$(echo "$KEY_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['key'])" 2>/dev/null)

if [ -z "$API_KEY" ]; then
  echo "  API key creation failed: $KEY_RESP"
  exit 1
fi

if [ "$OUTPUT" = "json" ]; then
  DASHBOARD_URL="$DASHBOARD_URL" API_URL="$API_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" API_KEY="$API_KEY" python3 -c 'import json, os; print(json.dumps({"dashboard_url": os.environ["DASHBOARD_URL"], "api_url": os.environ["API_URL"], "email": os.environ["EMAIL"], "password": os.environ["PASSWORD"], "api_key": os.environ["API_KEY"]}))'
  exit 0
fi

echo ""
echo "=== Ready ==="
echo "Dashboard:  $DASHBOARD_URL"
echo "Email:      $EMAIL"
echo "Password:   $PASSWORD"
echo "API Key:    $API_KEY"
echo ""

if ! grep -qE '^(OPENAI|ANTHROPIC|GOOGLE)_API_KEY=.' .env 2>/dev/null; then
  echo "!! No LLM provider API key set in server/.env."
  echo "   Set OPENAI_API_KEY (or ANTHROPIC_API_KEY / GOOGLE_API_KEY), then:"
  echo "     docker compose up -d --force-recreate mem0"
  echo "   The curl below will return provider_auth_failed until you do."
  echo ""
fi

echo "Test it:"
echo "  curl -X POST $API_URL/memories \\"
echo "    -H 'X-API-Key: $API_KEY' \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"messages\": [{\"role\": \"user\", \"content\": \"I like hiking\"}], \"user_id\": \"seed-\$(date +%s)\"}'"
