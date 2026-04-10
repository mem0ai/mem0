#!/bin/bash
set -e

API_URL="${API_URL:-http://localhost:8888}"
EMAIL="${EMAIL:-admin@mem0.dev}"
PASSWORD="${PASSWORD:-admin123456}"
NAME="${NAME:-Admin}"

echo "=== Mem0 Self-Hosted Seed ==="
echo "API: $API_URL"
echo ""

# Check if setup is needed
SETUP=$(curl -s "$API_URL/auth/setup-status")
NEEDS_SETUP=$(echo "$SETUP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('needsSetup', True))" 2>/dev/null || echo "True")

if [ "$NEEDS_SETUP" = "True" ]; then
  echo "Creating admin account..."
  REGISTER=$(curl -s -X POST "$API_URL/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"$NAME\", \"email\": \"$EMAIL\", \"password\": \"$PASSWORD\"}")
  echo "$REGISTER" | python3 -c "import sys,json; d=json.load(sys.stdin); print('  Admin created.' if 'access_token' in d else f'  Error: {d}')" 2>/dev/null
else
  echo "Admin already exists, logging in..."
fi

# Login
echo "Logging in..."
LOGIN=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\", \"password\": \"$PASSWORD\"}")
TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
  echo "  Login failed: $LOGIN"
  exit 1
fi
echo "  Logged in."

# Create API key
echo "Creating API key..."
KEY_RESP=$(curl -s -X POST "$API_URL/api-keys/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"label": "dev-seed-key"}')
API_KEY=$(echo "$KEY_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['key'])" 2>/dev/null)

echo ""
echo "=== Ready ==="
echo "Dashboard:  http://localhost:3000"
echo "Email:      $EMAIL"
echo "Password:   $PASSWORD"
echo "API Key:    $API_KEY"
echo ""
echo "Test it:"
echo "  curl -X POST $API_URL/memories \\"
echo "    -H 'X-API-Key: $API_KEY' \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"messages\": [{\"role\": \"user\", \"content\": \"I like hiking\"}], \"user_id\": \"test\"}'"
