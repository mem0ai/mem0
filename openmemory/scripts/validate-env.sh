#!/bin/bash

# OpenMemory Environment Validation Script
# Checks if the environment is properly configured

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

echo "🔍 Validating OpenMemory Environment"
echo "====================================="

# Check if environment files exist
ENV_FILES_EXIST=false
if [ -f "$ENV_LOCAL_FILE" ]; then
    print_success ".env.local file found"
    ENV_FILES_EXIST=true
fi

if [ -f "$API_ENV_FILE" ]; then
    print_success "api/.env file found"
    ENV_FILES_EXIST=true
fi

if [ "$ENV_FILES_EXIST" = false ]; then
    print_error "No environment files found"
    print_info "Run 'make setup' to create the environment files"
    exit 1
fi

# Function to check if a variable exists in a file
check_var_in_file() {
    local var_name="$1"
    local file_path="$2"
    
    if [ ! -f "$file_path" ]; then
        return 1
    fi
    
    if grep -q "^${var_name}=" "$file_path" && \
       ! grep -q "^${var_name}=\s*$" "$file_path" && \
       ! grep -q "^${var_name}=.*your.*key.*here" "$file_path" && \
       ! grep -q "^${var_name}=.*auto-generated" "$file_path"; then
        return 0
    else
        return 1
    fi
}

# Check required environment variables
MISSING_VARS=()

# Check OPENAI_API_KEY in api/.env
if ! check_var_in_file "OPENAI_API_KEY" "$API_ENV_FILE"; then
    MISSING_VARS+=("OPENAI_API_KEY")
fi

# Check Supabase vars in .env.local
if ! check_var_in_file "NEXT_PUBLIC_SUPABASE_URL" "$ENV_LOCAL_FILE"; then
    MISSING_VARS+=("NEXT_PUBLIC_SUPABASE_URL")
fi

if ! check_var_in_file "NEXT_PUBLIC_SUPABASE_ANON_KEY" "$ENV_LOCAL_FILE"; then
    MISSING_VARS+=("NEXT_PUBLIC_SUPABASE_ANON_KEY")
fi

if ! check_var_in_file "SUPABASE_SERVICE_KEY" "$ENV_LOCAL_FILE"; then
    MISSING_VARS+=("SUPABASE_SERVICE_KEY")
fi

# Also check the API file for Supabase vars (fallback)
if ! check_var_in_file "SUPABASE_URL" "$API_ENV_FILE"; then
    if [[ " ${MISSING_VARS[@]} " =~ " NEXT_PUBLIC_SUPABASE_URL " ]]; then
        # Already marked as missing, that's fine
        true
    fi
else
    # Remove from missing if found in API file
    MISSING_VARS=("${MISSING_VARS[@]/NEXT_PUBLIC_SUPABASE_URL}")
fi

if [ ${#MISSING_VARS[@]} -eq 0 ]; then
    print_success "All required environment variables are configured"
else
    print_error "Missing or invalid environment variables:"
    for var in "${MISSING_VARS[@]}"; do
        echo "  - $var"
    done
    echo ""
    
    # Provide helpful suggestions
    if [[ " ${MISSING_VARS[@]} " =~ " OPENAI_API_KEY " ]]; then
        print_info "To fix OPENAI_API_KEY:"
        echo "  1. Get an API key from https://platform.openai.com/api-keys"
        echo "  2. Edit $API_ENV_FILE and update the OPENAI_API_KEY line"
    fi
    
    if [[ " ${MISSING_VARS[@]} " =~ " NEXT_PUBLIC_SUPABASE_URL " ]] || [[ " ${MISSING_VARS[@]} " =~ " NEXT_PUBLIC_SUPABASE_ANON_KEY " ]] || [[ " ${MISSING_VARS[@]} " =~ " SUPABASE_SERVICE_KEY " ]]; then
        print_info "To fix Supabase configuration:"
        echo "  1. Run 'make configure-env' to auto-extract Supabase keys"
        echo "  2. Or manually run 'npx supabase status' and copy the keys to $ENV_LOCAL_FILE"
    fi
    
    exit 1
fi

# Check if services are running
print_info "Checking service status..."

# Check Supabase
if npx supabase status >/dev/null 2>&1; then
    print_success "Supabase is running"
else
    print_warning "Supabase is not running (will be started automatically)"
fi

# Check Qdrant
if docker ps | grep -q qdrant; then
    print_success "Qdrant is running"
else
    print_warning "Qdrant is not running (will be started automatically)"
fi

print_success "Environment validation passed!"
echo ""
print_info "Your environment is properly configured and ready for development"
echo "Run 'make dev' to start the development servers" 