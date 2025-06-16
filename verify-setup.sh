#!/bin/bash

# Quick verification script for Jean Memory setup
# Run this after make setup to verify everything is working

echo "🔍 Verifying Jean Memory Setup"
echo "=============================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check 1: Virtual Environment
echo ""
print_info "Checking Python virtual environment..."
if [ -d ".venv" ] && [ -f ".venv/bin/python" ]; then
    VENV_VERSION=$(.venv/bin/python --version 2>&1)
    if [[ "$VENV_VERSION" == *"3.12."* ]]; then
        print_success "Python 3.12.x virtual environment: $VENV_VERSION"
    else
        print_error "Wrong Python version in virtual environment: $VENV_VERSION"
        exit 1
    fi
else
    print_error "Virtual environment not found or corrupted"
    exit 1
fi

# Check 2: Critical Python Dependencies
echo ""
print_info "Checking critical Python dependencies..."
if .venv/bin/python -c "import fastapi, uvicorn, sqlalchemy, mem0ai; print('✓ All critical imports successful')" >/dev/null 2>&1; then
    print_success "All critical Python dependencies available"
else
    print_error "Missing critical Python dependencies"
    echo "Run: .venv/bin/pip install -r openmemory/api/requirements.txt"
    exit 1
fi

# Check 3: Environment Files
echo ""
print_info "Checking environment configuration..."
ENV_FILES=(
    "openmemory/.env.local"
    "openmemory/api/.env"
)

for file in "${ENV_FILES[@]}"; do
    if [ -f "$file" ]; then
        print_success "Found: $file"
    else
        print_error "Missing: $file"
    fi
done

# Check 4: API Key Configuration
echo ""
print_info "Checking API key configuration..."
if [ -f "openmemory/.env.local" ]; then
    if grep -q "your_openai_api_key_here" "openmemory/.env.local"; then
        print_error "OPENAI_API_KEY still has placeholder value"
        echo "   Edit openmemory/.env.local and add your real OpenAI API key"
    else
        print_success "OPENAI_API_KEY appears to be configured"
    fi
fi

# Check 5: Docker Services
echo ""
print_info "Checking Docker services..."
if command -v docker >/dev/null 2>&1; then
    if docker info >/dev/null 2>&1; then
        print_success "Docker is running"
    else
        print_error "Docker is not running - start Docker Desktop"
    fi
else
    print_error "Docker not installed"
fi

# Check 6: Node.js Dependencies
echo ""
print_info "Checking Node.js setup..."
if [ -d "openmemory/ui/node_modules" ]; then
    print_success "UI dependencies installed"
else
    print_error "UI dependencies not installed - run: cd openmemory/ui && npm install"
fi

# Summary
echo ""
echo "🏁 Setup Verification Complete"
echo "=============================="
echo ""
print_info "Next steps (run in separate terminals):"
echo "  Terminal 1: make backend"
echo "  Terminal 2: make ui-local"
echo ""
print_info "Then visit:"
echo "  • UI: http://localhost:3000"
echo "  • API: http://localhost:8765/docs"
echo "  • Supabase: http://localhost:54323" 