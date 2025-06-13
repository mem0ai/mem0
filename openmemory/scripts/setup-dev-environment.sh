#!/bin/bash

# OpenMemory Development Environment Setup Script
# One-command setup for local development with minimal user input

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env.local"
ENV_TEMPLATE="$PROJECT_ROOT/env.local.example"

# Helper functions
print_header() {
    echo -e "\n${BLUE}$1${NC}"
    echo "=================================="
}

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

check_command() {
    if command -v "$1" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Main setup function
main() {
    print_header "🚀 OpenMemory One-Command Setup"
    
    echo "This script will set up your complete development environment."
    echo "You only need to provide your OpenAI API key - everything else is automatic!"
    echo ""
    
    # Check prerequisites
    print_header "📋 Checking Prerequisites"
    
    local missing_deps=()
    
    if ! check_command "node"; then
        missing_deps+=("Node.js (https://nodejs.org/)")
    else
        print_success "Node.js found: $(node --version)"
    fi
    
    if ! check_command "npm"; then
        missing_deps+=("npm (comes with Node.js)")
    else
        print_success "npm found: $(npm --version)"
    fi
    
    if ! check_command "python3" && ! check_command "python"; then
        missing_deps+=("Python 3.8+ (https://python.org/)")
    else
        local python_cmd="python3"
        if ! check_command "python3"; then
            python_cmd="python"
        fi
        print_success "Python found: $($python_cmd --version)"
    fi
    
    if ! check_command "docker"; then
        missing_deps+=("Docker Desktop (https://docker.com/products/docker-desktop)")
    else
        print_success "Docker found: $(docker --version)"
        
        # Check if Docker is running
        if ! docker info >/dev/null 2>&1; then
            print_error "Docker is installed but not running. Please start Docker Desktop."
            exit 1
        fi
        print_success "Docker is running"
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_error "Missing required dependencies:"
        printf '%s\n' "${missing_deps[@]}"
        echo ""
        echo "Please install the missing dependencies and run this script again."
        exit 1
    fi
    
    # Change to project directory
    cd "$PROJECT_ROOT"
    
    # Install dependencies
    print_header "📦 Installing Dependencies"
    
    if [ ! -f "package.json" ]; then
        print_error "package.json not found. Are you in the correct directory?"
        exit 1
    fi
    
    npm install --silent
    print_success "Supabase CLI installed"
    
    # Install Python dependencies
    if [ -d "api" ] && [ -f "api/requirements.txt" ]; then
        print_info "Installing Python dependencies..."
        cd api && pip install -r requirements.txt --quiet && cd ..
        print_success "Python dependencies installed"
    fi
    
    # Create environment file with user input
    print_header "🔑 API Key Configuration"
    
    echo "You need an OpenAI API key to use the AI features."
    echo "Get one from: https://platform.openai.com/api-keys"
    echo ""
    
    # Get OpenAI API Key (required)
    local openai_key=""
    while [ -z "$openai_key" ]; do
        read -p "Enter your OpenAI API key: " openai_key
        if [ -z "$openai_key" ]; then
            print_warning "OpenAI API key is required to continue."
        fi
    done
    
    # Get Gemini API Key (optional)
    echo ""
    echo "Gemini API key is optional but recommended for better AI responses."
    echo "Get one from: https://makersuite.google.com/app/apikey"
    read -p "Enter your Gemini API key (or press Enter to skip): " gemini_key
    
    # Create environment file from template
    cp "$ENV_TEMPLATE" "$ENV_FILE"
    
    # Update API keys
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/your_openai_api_key_here/$openai_key/" "$ENV_FILE"
        if [ -n "$gemini_key" ]; then
            sed -i '' "s/GEMINI_API_KEY=/GEMINI_API_KEY=$gemini_key/" "$ENV_FILE"
        fi
    else
        # Linux
        sed -i "s/your_openai_api_key_here/$openai_key/" "$ENV_FILE"
        if [ -n "$gemini_key" ]; then
            sed -i "s/GEMINI_API_KEY=/GEMINI_API_KEY=$gemini_key/" "$ENV_FILE"
        fi
    fi
    
    print_success "API keys configured"
    
    # Start Supabase and auto-configure
    print_header "🗄️ Starting Local Supabase"
    
    echo "Starting local Supabase services (this may take a moment)..."
    npx supabase start
    
    print_success "Supabase started successfully!"
    
    # Auto-extract and configure Supabase keys using dedicated script
    print_header "🔧 Auto-Configuring Supabase"
    
    echo "Running environment configuration script..."
    chmod +x "$PROJECT_ROOT/scripts/configure-env.sh"
    
    if "$PROJECT_ROOT/scripts/configure-env.sh"; then
        print_success "Environment automatically configured!"
    else
        print_error "Failed to configure environment automatically."
        echo "Please run 'make configure-env' manually after setup completes."
    fi
    
    # Start Qdrant
    print_header "🔍 Starting Qdrant Vector Database"
    
    echo "Starting Qdrant in Docker..."
    
    # Stop any existing Qdrant containers
    docker-compose down qdrant_db 2>/dev/null || true
    
    # Start Qdrant
    docker-compose up -d qdrant_db
    
    # Wait a moment for Qdrant to start
    sleep 3
    
    if docker ps | grep -q qdrant; then
        print_success "Qdrant started successfully!"
    else
        print_warning "Qdrant may not have started properly. Check Docker logs if needed."
    fi
    
    # Final verification
    print_header "🧪 Verifying Setup"
    
    # Check if services are responding
    echo "Checking service health..."
    
    # Check Supabase
    if curl -s "http://localhost:54321/health" >/dev/null; then
        print_success "Supabase API is responding"
    else
        print_warning "Supabase API not responding (may still be starting)"
    fi
    
    # Check Qdrant
    if curl -s "http://localhost:6333/health" >/dev/null; then
        print_success "Qdrant is responding"
    else
        print_warning "Qdrant not responding (may still be starting)"
    fi
    
    # Final success message
    print_header "🎉 Setup Complete!"
    
    echo "Your OpenMemory development environment is ready!"
    echo ""
    echo "🌐 Available services:"
    echo "   • Supabase Studio:  http://localhost:54323"
    echo "   • Qdrant Dashboard: http://localhost:6333/dashboard"
    echo ""
    echo "📁 Configuration saved to: $ENV_FILE"
    echo ""
    echo "🚀 Quick start:"
    echo "   make dev      # Start API and UI servers"
    echo "   make stop     # Stop all services"
    echo "   make status   # Check what's running"
    echo ""
    echo "💡 The API will run on http://localhost:8765"
    echo "💡 The UI will run on http://localhost:3000"
    echo ""
    echo "🔧 Useful commands:"
    echo "   make studio   # Open Supabase Studio"
    echo "   make logs     # View service logs"
    echo "   make clean    # Reset everything"
    echo ""
    
    # Ask if user wants to start development servers
    echo ""
    read -p "Start the development servers now? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        print_info "Starting development servers..."
        make dev
        echo ""
        print_success "Development environment is running!"
        echo "🎯 Open http://localhost:3000 to start using OpenMemory"
    else
        print_info "Setup complete! Run 'make dev' when ready to start developing."
    fi
}

# Run main function
main "$@" 