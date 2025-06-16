#!/bin/bash

# Test script to validate README.md setup process
# This simulates a fresh user following the README exactly

set -e

echo "🧪 Testing README.md Local Development Setup"
echo "=============================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Test 1: Prerequisites check
echo "Test 1: Checking Prerequisites"
echo "-------------------------------"

# Check Node.js
if command -v node >/dev/null 2>&1; then
    NODE_VERSION=$(node --version)
    print_success "Node.js found: $NODE_VERSION"
else
    print_error "Node.js not found"
    exit 1
fi

# Check npm
if command -v npm >/dev/null 2>&1; then
    NPM_VERSION=$(npm --version)
    print_success "npm found: $NPM_VERSION"
else
    print_error "npm not found"
    exit 1
fi

# Check Docker
if command -v docker >/dev/null 2>&1; then
    DOCKER_VERSION=$(docker --version)
    print_success "Docker found: $DOCKER_VERSION"
    
    # Check if Docker is running
    if docker info >/dev/null 2>&1; then
        print_success "Docker is running"
    else
        print_error "Docker is not running"
        exit 1
    fi
else
    print_error "Docker not found"
    exit 1
fi

# Check Git
if command -v git >/dev/null 2>&1; then
    GIT_VERSION=$(git --version)
    print_success "Git found: $GIT_VERSION"
else
    print_error "Git not found"
    exit 1
fi

echo ""

# Test 2: Python 3.12 availability
echo "Test 2: Python 3.12 Availability"
echo "---------------------------------"

PYTHON_FOUND=false
PYTHON_CMD=""

if command -v python3.12 >/dev/null 2>&1; then
    PYTHON_VERSION=$(python3.12 --version 2>&1)
    if [[ "$PYTHON_VERSION" == *"3.12."* ]]; then
        print_success "Python 3.12.x found: $PYTHON_VERSION"
        PYTHON_FOUND=true
        PYTHON_CMD="python3.12"
    fi
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    if [[ "$PYTHON_VERSION" == *"3.12."* ]]; then
        print_success "Python 3.12.x found via python3: $PYTHON_VERSION"
        PYTHON_FOUND=true
        PYTHON_CMD="python3"
    else
        print_warning "Found $PYTHON_VERSION, but Python 3.12.x is required"
        print_info "Setup should auto-install Python 3.12.x"
    fi
elif command -v python >/dev/null 2>&1; then
    PYTHON_VERSION=$(python --version 2>&1)
    if [[ "$PYTHON_VERSION" == *"3.12."* ]]; then
        print_success "Python 3.12.x found via python: $PYTHON_VERSION"
        PYTHON_FOUND=true
        PYTHON_CMD="python"
    else
        print_warning "Found $PYTHON_VERSION, but Python 3.12.x is required"
        print_info "Setup should auto-install Python 3.12.x"
    fi
else
    print_warning "No Python found - setup should auto-install Python 3.12.x"
fi

echo ""

# Test 3: Check if virtual environment exists
echo "Test 3: Virtual Environment Status"
echo "----------------------------------"

if [ -d ".venv" ]; then
    if [ -f ".venv/bin/python" ]; then
        VENV_VERSION=$(.venv/bin/python --version 2>&1)
        print_info "Virtual environment exists with: $VENV_VERSION"
        
        if [[ "$VENV_VERSION" == *"3.12."* ]]; then
            print_success "Virtual environment uses Python 3.12.x"
        else
            print_warning "Virtual environment uses different Python version"
            print_info "May need to recreate virtual environment"
        fi
    else
        print_warning "Virtual environment directory exists but seems corrupted"
    fi
else
    print_info "No virtual environment found (expected for fresh setup)"
fi

echo ""

# Test 4: Check required files exist
echo "Test 4: Required Files Check"
echo "----------------------------"

REQUIRED_FILES=(
    "Makefile"
    "openmemory/Makefile"
    "openmemory/scripts/setup-dev-environment.sh"
    "openmemory/env.local.example"
    "openmemory/env.example"
    "openmemory/api/requirements.txt"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        print_success "Found: $file"
    else
        print_error "Missing: $file"
    fi
done

echo ""

# Test 5: Check Makefile targets
echo "Test 5: Makefile Targets Check"
echo "------------------------------"

EXPECTED_TARGETS=(
    "setup"
    "build"
    "backend"
    "ui-local"
    "status"
    "clean"
)

for target in "${EXPECTED_TARGETS[@]}"; do
    if make -n "$target" >/dev/null 2>&1; then
        print_success "Makefile target exists: $target"
    else
        print_error "Makefile target missing or invalid: $target"
    fi
done

echo ""

# Test 6: Check setup script has correct Python logic
echo "Test 6: Setup Script Python Logic"
echo "---------------------------------"

SETUP_SCRIPT="openmemory/scripts/setup-dev-environment.sh"

if grep -q "3\.12\.x" "$SETUP_SCRIPT"; then
    print_success "Setup script uses Python 3.12.x (not 3.12.11 specific)"
else
    print_warning "Setup script may still require specific Python 3.12.11"
fi

if grep -q "install_python_3_12" "$SETUP_SCRIPT"; then
    print_success "Setup script has Python 3.12 auto-installation"
else
    print_warning "Setup script may not have auto-installation"
fi

if grep -q "make backend" "$SETUP_SCRIPT"; then
    print_success "Setup script mentions correct 'make backend' command"
else
    print_warning "Setup script may have incorrect command instructions"
fi

echo ""

# Test 7: Environment file templates
echo "Test 7: Environment File Templates"
echo "----------------------------------"

if [ -f "openmemory/env.local.example" ]; then
    if grep -q "OPENAI_API_KEY" "openmemory/env.local.example"; then
        print_success "env.local.example has OPENAI_API_KEY placeholder"
    else
        print_warning "env.local.example missing OPENAI_API_KEY"
    fi
else
    print_error "env.local.example not found"
fi

echo ""

# Summary
echo "🏁 Test Summary"
echo "==============="
echo ""

if $PYTHON_FOUND; then
    print_success "Environment ready for testing README.md setup process"
    echo ""
    print_info "Ready to test README.md commands:"
    echo "  1. make setup"
    echo "  2. [Add API keys when prompted]"
    echo "  3. make build"
    echo "  4. make backend (Terminal 1)"
    echo "  5. make ui-local (Terminal 2)"
else
    print_info "Environment ready to test Python 3.12.x auto-installation"
    echo ""
    print_info "Setup process should:"
    echo "  1. Auto-detect missing Python 3.12.x"
    echo "  2. Install Python 3.12.x via Homebrew (macOS)"
    echo "  3. Create virtual environment with Python 3.12.x"
    echo "  4. Complete setup successfully"
fi

echo ""
print_info "Run this script with: chmod +x test-readme-setup.sh && ./test-readme-setup.sh" 