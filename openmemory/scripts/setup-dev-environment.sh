#!/bin/bash

# OpenMemory Development Environment Setup Script
# This script helps new contributors set up the development environment

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
    print_header "🚀 OpenMemory Development Environment Setup"
    
    echo "This script will help you set up a complete local development environment"
    echo "that uses Supabase CLI for authentication and database management."
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
    
    # Install Supabase CLI
    print_header "📦 Installing Supabase CLI"
    
    if [ ! -f "package.json" ]; then
        print_error "package.json not found. Are you in the correct directory?"
        exit 1
    fi
    
    npm install
    print_success "Supabase CLI installed"
    
    # Create environment file
    print_header "🔧 Setting up Environment"
    
    if [ ! -f "$ENV_TEMPLATE" ]; then
        print_error "Environment template not found at $ENV_TEMPLATE"
        exit 1
    fi
    
    if [ -f "$ENV_FILE" ]; then
        print_warning "Environment file already exists at $ENV_FILE"
        read -p "Do you want to overwrite it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Keeping existing environment file"
        else
            cp "$ENV_TEMPLATE" "$ENV_FILE"
            print_success "Environment file updated"
        fi
    else
        cp "$ENV_TEMPLATE" "$ENV_FILE"
        print_success "Environment file created at $ENV_FILE"
    fi
    
    # Get OpenAI API Key
    print_header "🔑 API Key Configuration"
    
    echo "You'll need an OpenAI API key to use the AI features."
    echo "Get one from: https://platform.openai.com/api-keys"
    echo ""
    
    if grep -q "your_openai_api_key_here" "$ENV_FILE"; then
        read -p "Enter your OpenAI API key (or press Enter to set it later): " openai_key
        if [ -n "$openai_key" ]; then
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS
                sed -i '' "s/your_openai_api_key_here/$openai_key/" "$ENV_FILE"
            else
                # Linux
                sed -i "s/your_openai_api_key_here/$openai_key/" "$ENV_FILE"
            fi
            print_success "OpenAI API key configured"
        else
            print_warning "OpenAI API key not set. You'll need to edit $ENV_FILE later"
        fi
    else
        print_info "OpenAI API key appears to be already configured"
    fi
    
    # Start Supabase and get keys
    print_header "🗄️ Starting Local Supabase"
    
    echo "Starting local Supabase services..."
    npx supabase start
    
    print_success "Supabase started successfully!"
    echo ""
    
    # Extract Supabase configuration
    print_header "📝 Configuring Supabase Keys"
    
    echo "Extracting Supabase configuration..."
    
    # Get Supabase status in JSON format
    local supabase_status
    supabase_status=$(npx supabase status --output json)
    
    # Extract values using simple grep/sed (more portable than jq)
    local api_url
    local anon_key  
    local service_key
    
    api_url=$(echo "$supabase_status" | grep -o '"API URL":"[^"]*"' | cut -d'"' -f4)
    anon_key=$(echo "$supabase_status" | grep -o '"anon key":"[^"]*"' | cut -d'"' -f4)
    service_key=$(echo "$supabase_status" | grep -o '"service_role key":"[^"]*"' | cut -d'"' -f4)
    
    if [ -n "$api_url" ] && [ -n "$anon_key" ] && [ -n "$service_key" ]; then
        # Update environment file with Supabase keys
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s|NEXT_PUBLIC_SUPABASE_URL=.*|NEXT_PUBLIC_SUPABASE_URL=$api_url|" "$ENV_FILE"
            sed -i '' "s|NEXT_PUBLIC_SUPABASE_ANON_KEY=.*|NEXT_PUBLIC_SUPABASE_ANON_KEY=$anon_key|" "$ENV_FILE"
            sed -i '' "s|SUPABASE_SERVICE_KEY=.*|SUPABASE_SERVICE_KEY=$service_key|" "$ENV_FILE"
        else
            # Linux
            sed -i "s|NEXT_PUBLIC_SUPABASE_URL=.*|NEXT_PUBLIC_SUPABASE_URL=$api_url|" "$ENV_FILE"
            sed -i "s|NEXT_PUBLIC_SUPABASE_ANON_KEY=.*|NEXT_PUBLIC_SUPABASE_ANON_KEY=$anon_key|" "$ENV_FILE"
            sed -i "s|SUPABASE_SERVICE_KEY=.*|SUPABASE_SERVICE_KEY=$service_key|" "$ENV_FILE"
        fi
        
        print_success "Supabase keys automatically configured!"
    else
        print_warning "Could not automatically extract Supabase keys"
        echo "Please manually copy the keys from the output above to $ENV_FILE"
    fi
    
    # Start Qdrant
    print_header "🔍 Starting Qdrant Vector Database"
    
    echo "Starting Qdrant in Docker..."
    docker-compose up -d qdrant_db
    print_success "Qdrant started successfully!"
    
    # Final instructions
    print_header "🎉 Setup Complete!"
    
    echo "Your OpenMemory development environment is ready!"
    echo ""
    echo "🌐 Available services:"
    echo "   • Supabase Studio:  http://localhost:54323"
    echo "   • Qdrant Dashboard: http://localhost:6333/dashboard"
    echo ""
    echo "📁 Environment file: $ENV_FILE"
    echo ""
    echo "🚀 Next steps:"
    echo "   1. Run 'make dev' to start the full development environment"
    echo "   2. The API will be available at http://localhost:8765"
    echo "   3. The UI will be available at http://localhost:3000"
    echo ""
    echo "🔧 Useful commands:"
    echo "   • make dev      - Start development environment"
    echo "   • make stop     - Stop all services"
    echo "   • make status   - Check service status"
    echo "   • make studio   - Open Supabase Studio"
    echo "   • make clean    - Reset everything"
    echo ""
    echo "📚 For more help, see the documentation or run 'make help'"
    
    # Optional: Start the development environment
    echo ""
    read -p "Would you like to start the development environment now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Starting development environment..."
        make dev
    else
        print_info "Setup complete. Run 'make dev' when ready to start developing!"
    fi
}

# Run main function
main "$@" 