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
ENV_FILE="$PROJECT_ROOT/.env.local"

echo "🔍 Validating OpenMemory Environment"
echo "====================================="

# Check if .env.local exists
if [ ! -f "$ENV_FILE" ]; then
    print_error ".env.local file not found"
    print_info "Run 'make setup' to create the environment file"
    exit 1
fi

print_success ".env.local file found"

# Check required environment variables
REQUIRED_VARS=("OPENAI_API_KEY" "NEXT_PUBLIC_SUPABASE_URL" "NEXT_PUBLIC_SUPABASE_ANON_KEY" "SUPABASE_SERVICE_KEY")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^${var}=" "$ENV_FILE" || grep -q "^${var}=\s*$" "$ENV_FILE" || grep -q "^${var}=.*your.*key.*here" "$ENV_FILE" || grep -q "^${var}=.*auto-generated" "$ENV_FILE"; then
        MISSING_VARS+=("$var")
    fi
done

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
        echo "  2. Edit $ENV_FILE and update the OPENAI_API_KEY line"
    fi
    
    if [[ " ${MISSING_VARS[@]} " =~ " NEXT_PUBLIC_SUPABASE_URL " ]] || [[ " ${MISSING_VARS[@]} " =~ " NEXT_PUBLIC_SUPABASE_ANON_KEY " ]] || [[ " ${MISSING_VARS[@]} " =~ " SUPABASE_SERVICE_KEY " ]]; then
        print_info "To fix Supabase configuration:"
        echo "  1. Run 'make configure-env' to auto-extract Supabase keys"
        echo "  2. Or manually run 'npx supabase status' and copy the keys to $ENV_FILE"
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