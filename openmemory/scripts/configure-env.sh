#!/bin/bash

# OpenMemory Environment Configuration Script
# Extracts Supabase keys and updates .env.local

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env.local"

echo "🔧 Configuring OpenMemory Environment"
echo "======================================"

# Check if .env.local exists
if [ ! -f "$ENV_FILE" ]; then
    print_error ".env.local file not found at $ENV_FILE"
    print_info "Please run 'make setup' first to create the environment file"
    exit 1
fi

# Check if Supabase is running
if ! npx supabase status >/dev/null 2>&1; then
    print_warning "Supabase is not running. Starting it now..."
    npx supabase start
    sleep 3
fi

print_info "Extracting Supabase configuration..."

# Get current status and extract keys
TEMP_STATUS="/tmp/supabase_status_$$.txt"
npx supabase status > "$TEMP_STATUS"

# Show the status for debugging
echo ""
echo "Current Supabase status:"
cat "$TEMP_STATUS"
echo ""

# Extract the keys using multiple parsing methods for reliability
API_URL=""
ANON_KEY=""
SERVICE_KEY=""

# Method 1: Standard parsing
API_URL=$(grep "API URL:" "$TEMP_STATUS" | sed 's/.*API URL: *//' | tr -d ' \t\r\n' || echo "")
ANON_KEY=$(grep "anon key:" "$TEMP_STATUS" | sed 's/.*anon key: *//' | tr -d ' \t\r\n' || echo "")
SERVICE_KEY=$(grep "service_role key:" "$TEMP_STATUS" | sed 's/.*service_role key: *//' | tr -d ' \t\r\n' || echo "")

# Method 2: If first method fails, try alternative parsing
if [ -z "$API_URL" ]; then
    API_URL=$(awk '/API URL:/ {print $NF}' "$TEMP_STATUS" | tr -d ' \t\r\n')
fi

if [ -z "$ANON_KEY" ]; then
    ANON_KEY=$(awk '/anon key:/ {print $NF}' "$TEMP_STATUS" | tr -d ' \t\r\n')
fi

if [ -z "$SERVICE_KEY" ]; then
    SERVICE_KEY=$(awk '/service_role key:/ {print $NF}' "$TEMP_STATUS" | tr -d ' \t\r\n')
fi

# Show what we extracted
echo "Extracted configuration:"
echo "  API URL: $API_URL"
echo "  Anon Key: ${ANON_KEY:0:20}..."
echo "  Service Key: ${SERVICE_KEY:0:20}..."
echo ""

# Validate that we got all required keys
if [ -z "$API_URL" ] || [ -z "$ANON_KEY" ] || [ -z "$SERVICE_KEY" ]; then
    print_error "Failed to extract one or more required Supabase keys!"
    echo ""
    echo "Missing:"
    [ -z "$API_URL" ] && echo "  - API URL"
    [ -z "$ANON_KEY" ] && echo "  - Anon Key"
    [ -z "$SERVICE_KEY" ] && echo "  - Service Key"
    echo ""
    echo "Please check that Supabase is running properly: npx supabase status"
    echo "You may need to manually add these values to $ENV_FILE"
    rm -f "$TEMP_STATUS"
    exit 1
fi

# Create backup of current env file
cp "$ENV_FILE" "$ENV_FILE.backup"
print_info "Backup created: $ENV_FILE.backup"

# Update the environment file
print_info "Updating environment file..."

# Use a more robust replacement method
python3 -c "
import re
import sys

env_file = '$ENV_FILE'
api_url = '$API_URL'
anon_key = '$ANON_KEY'
service_key = '$SERVICE_KEY'

# Read the file
with open(env_file, 'r') as f:
    content = f.read()

# Replace the values
content = re.sub(r'^NEXT_PUBLIC_SUPABASE_URL=.*$', f'NEXT_PUBLIC_SUPABASE_URL={api_url}', content, flags=re.MULTILINE)
content = re.sub(r'^NEXT_PUBLIC_SUPABASE_ANON_KEY=.*$', f'NEXT_PUBLIC_SUPABASE_ANON_KEY={anon_key}', content, flags=re.MULTILINE)
content = re.sub(r'^SUPABASE_SERVICE_KEY=.*$', f'SUPABASE_SERVICE_KEY={service_key}', content, flags=re.MULTILINE)

# Write back
with open(env_file, 'w') as f:
    f.write(content)

print('Environment file updated successfully')
"

# Verify the changes
echo ""
echo "Updated environment file contains:"
grep -E "^(NEXT_PUBLIC_SUPABASE_URL|NEXT_PUBLIC_SUPABASE_ANON_KEY|SUPABASE_SERVICE_KEY)=" "$ENV_FILE"
echo ""

print_success "Environment configuration completed!"
print_info "Your .env.local file has been updated with the current Supabase keys"

# Clean up
rm -f "$TEMP_STATUS"

echo ""
echo "🚀 Ready to start development!"
echo "Run 'make dev' to start the API and UI servers" 