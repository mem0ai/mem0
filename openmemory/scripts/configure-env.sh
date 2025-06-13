#!/bin/bash

# OpenMemory Environment Configuration Script
# Extracts Supabase keys and updates both .env.local and api/.env

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
ENV_LOCAL_FILE="$PROJECT_ROOT/.env.local"
API_ENV_FILE="$PROJECT_ROOT/api/.env"
UI_ENV_FILE="$PROJECT_ROOT/ui/.env.local"

echo "🔧 Configuring OpenMemory Environment"
echo "======================================"

# Check if environment files exist
env_files_exist=false
if [ -f "$ENV_LOCAL_FILE" ]; then
    print_info "Found .env.local file"
    env_files_exist=true
fi

if [ -f "$API_ENV_FILE" ]; then
    print_info "Found api/.env file"
    env_files_exist=true
fi

if [ "$env_files_exist" = false ]; then
    print_error "No environment files found"
    print_info "Please run the setup script first to create environment files"
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
    echo "You may need to manually add these values to your environment files"
    rm -f "$TEMP_STATUS"
    exit 1
fi

# Function to update environment file
update_env_file() {
    local file_path="$1"
    local file_name="$2"
    
    if [ ! -f "$file_path" ]; then
        print_warning "$file_name not found, skipping"
        return
    fi
    
    # Create backup of current env file
    cp "$file_path" "$file_path.backup"
    print_info "Backup created: $file_path.backup"

    # Update the environment file
    print_info "Updating $file_name..."

    # Use a more robust replacement method
    python3 -c "
import re
import sys

env_file = '$file_path'
api_url = '$API_URL'
anon_key = '$ANON_KEY'
service_key = '$SERVICE_KEY'

# Read the file
with open(env_file, 'r') as f:
    content = f.read()

# Replace the values with both naming conventions
content = re.sub(r'^NEXT_PUBLIC_SUPABASE_URL=.*$', f'NEXT_PUBLIC_SUPABASE_URL={api_url}', content, flags=re.MULTILINE)
content = re.sub(r'^SUPABASE_URL=.*$', f'SUPABASE_URL={api_url}', content, flags=re.MULTILINE)
content = re.sub(r'^NEXT_PUBLIC_SUPABASE_ANON_KEY=.*$', f'NEXT_PUBLIC_SUPABASE_ANON_KEY={anon_key}', content, flags=re.MULTILINE)
content = re.sub(r'^SUPABASE_ANON_KEY=.*$', f'SUPABASE_ANON_KEY={anon_key}', content, flags=re.MULTILINE)
content = re.sub(r'^SUPABASE_SERVICE_KEY=.*$', f'SUPABASE_SERVICE_KEY={service_key}', content, flags=re.MULTILINE)

# Write back
with open(env_file, 'w') as f:
    f.write(content)

print('Environment file updated successfully')
"
    
    print_success "$file_name updated successfully"
}

# Function to update UI environment file (local development only)
update_ui_env_file() {
    local file_path="$1"
    
    if [ ! -f "$file_path" ]; then
        print_info "Creating UI .env.local file for local development..."
        # Create a basic UI env file if it doesn't exist
        cat > "$file_path" << EOF
# UI Local Development Environment
# Auto-generated for local Supabase integration

# API connection (points to local API backend)
NEXT_PUBLIC_API_URL=http://localhost:8765

# Supabase Local Configuration (Auto-updated)
NEXT_PUBLIC_SUPABASE_URL=$API_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY=$ANON_KEY

# Development Settings
NEXT_TELEMETRY_DISABLED=1
NODE_ENV=development
EOF
        print_success "Created ui/.env.local"
        return
    fi
    
    # Create backup of current env file
    cp "$file_path" "$file_path.backup"
    print_info "Backup created: $file_path.backup"

    # Update the UI environment file
    print_info "Updating ui/.env.local..."

    # Use Python to safely update the file
    python3 -c "
import re
import sys

env_file = '$file_path'
api_url = '$API_URL'
anon_key = '$ANON_KEY'

# Read the file
with open(env_file, 'r') as f:
    content = f.read()

# Update Supabase variables
content = re.sub(r'^NEXT_PUBLIC_SUPABASE_URL=.*$', f'NEXT_PUBLIC_SUPABASE_URL={api_url}', content, flags=re.MULTILINE)
content = re.sub(r'^NEXT_PUBLIC_SUPABASE_ANON_KEY=.*$', f'NEXT_PUBLIC_SUPABASE_ANON_KEY={anon_key}', content, flags=re.MULTILINE)

# Add variables if they don't exist
if 'NEXT_PUBLIC_SUPABASE_URL=' not in content:
    content += f'\n# Supabase Local Configuration\nNEXT_PUBLIC_SUPABASE_URL={api_url}\n'
if 'NEXT_PUBLIC_SUPABASE_ANON_KEY=' not in content:
    content += f'NEXT_PUBLIC_SUPABASE_ANON_KEY={anon_key}\n'

# Write back
with open(env_file, 'w') as f:
    f.write(content)

print('UI environment file updated successfully')
"
    
    print_success "ui/.env.local updated successfully"
}

# Update backend environment files
if [ -f "$ENV_LOCAL_FILE" ]; then
    update_env_file "$ENV_LOCAL_FILE" ".env.local"
fi

if [ -f "$API_ENV_FILE" ]; then
    update_env_file "$API_ENV_FILE" "api/.env"
fi

# Update UI environment file for local development
# This ensures Next.js can find the Supabase environment variables
update_ui_env_file "$UI_ENV_FILE"

# Sync API keys from main environment to UI environment
print_info "Syncing API keys to UI environment..."
if [ -f "$ENV_LOCAL_FILE" ]; then
    # Extract API keys from main environment file
    OPENAI_API_KEY=$(grep '^OPENAI_API_KEY=' "$ENV_LOCAL_FILE" | cut -d'=' -f2- | head -1)
    GEMINI_API_KEY=$(grep '^GEMINI_API_KEY=' "$ENV_LOCAL_FILE" | cut -d'=' -f2- | head -1)
    
    if [ -n "$OPENAI_API_KEY" ] && [ "$OPENAI_API_KEY" != "your_openai_api_key_here" ]; then
        # Update UI environment file with API keys
        python3 -c "
import re
import sys

env_file = '$UI_ENV_FILE'
openai_key = '$OPENAI_API_KEY'
gemini_key = '$GEMINI_API_KEY'

# Read the file
with open(env_file, 'r') as f:
    content = f.read()

# Update OpenAI API key
content = re.sub(r'^OPENAI_API_KEY=.*$', f'OPENAI_API_KEY={openai_key}', content, flags=re.MULTILINE)
content = re.sub(r'^NEXT_PUBLIC_OPENAI_API_KEY=.*$', f'NEXT_PUBLIC_OPENAI_API_KEY={openai_key}', content, flags=re.MULTILINE)

# Update Gemini API key if present
if gemini_key:
    content = re.sub(r'^GEMINI_API_KEY=.*$', f'GEMINI_API_KEY={gemini_key}', content, flags=re.MULTILINE)
    content = re.sub(r'^NEXT_PUBLIC_GEMINI_API_KEY=.*$', f'NEXT_PUBLIC_GEMINI_API_KEY={gemini_key}', content, flags=re.MULTILINE)

# Add keys if they don't exist
if 'OPENAI_API_KEY=' not in content:
    content += f'\nOPENAI_API_KEY={openai_key}\n'
if 'NEXT_PUBLIC_OPENAI_API_KEY=' not in content:
    content += f'NEXT_PUBLIC_OPENAI_API_KEY={openai_key}\n'
if gemini_key and 'GEMINI_API_KEY=' not in content:
    content += f'GEMINI_API_KEY={gemini_key}\n'
if gemini_key and 'NEXT_PUBLIC_GEMINI_API_KEY=' not in content:
    content += f'NEXT_PUBLIC_GEMINI_API_KEY={gemini_key}\n'

# Write back
with open(env_file, 'w') as f:
    f.write(content)

print('API keys synced to UI environment')
"
        print_success "API keys synced to UI environment"
    else
        print_info "No valid API keys found to sync"
    fi
fi

# Verify the changes
echo ""
echo "Configuration verification:"
if [ -f "$ENV_LOCAL_FILE" ]; then
    echo ""
    echo ".env.local contains:"
    grep -E "^(NEXT_PUBLIC_SUPABASE_URL|NEXT_PUBLIC_SUPABASE_ANON_KEY|SUPABASE_SERVICE_KEY)=" "$ENV_LOCAL_FILE" | head -3
fi

if [ -f "$API_ENV_FILE" ]; then
    echo ""
    echo "api/.env contains:"
    grep -E "^(SUPABASE_URL|SUPABASE_ANON_KEY|SUPABASE_SERVICE_KEY)=" "$API_ENV_FILE" | head -3
fi

if [ -f "$UI_ENV_FILE" ]; then
    echo ""
    echo "ui/.env.local contains:"
    grep -E "^(NEXT_PUBLIC_SUPABASE_URL|NEXT_PUBLIC_SUPABASE_ANON_KEY|OPENAI_API_KEY|NEXT_PUBLIC_OPENAI_API_KEY)=" "$UI_ENV_FILE" | head -4
fi

echo ""
print_success "Environment configuration completed!"
print_info "Your environment files have been updated with the current Supabase keys"
print_info "The UI can now connect to local Supabase for authentication"

# Clean up
rm -f "$TEMP_STATUS"

echo ""
echo "🚀 Ready to start development!"
echo "Run 'make dev' to start the API and UI servers" 