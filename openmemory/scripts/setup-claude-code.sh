#!/bin/bash

# OpenMemory Claude Code Setup Script
# This script helps you configure Claude Code to work with OpenMemory MCP server

set -e

# Default values
API_URL="${OPENAI_API_URL:-http://localhost:8765}"
USER_ID="${USER_ID:-user}"
PROJECT_NAME=""
MCP_FILE=".mcp.json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_help() {
    cat << EOF
OpenMemory Claude Code Setup Script

Usage: $0 [OPTIONS]

Options:
    -u, --user-id USER_ID    Set the user ID (default: user)
    -p, --project-name NAME  Set project name for app isolation (auto-detected if not provided)
    -a, --api-url URL        Set the API URL (default: http://localhost:8765)
    -f, --file FILE          Set the output file (default: .mcp.json)
    -h, --help              Show this help message

Examples:
    $0                                           # Auto-detect project name from current directory
    $0 --project-name jaipuria-intelligence     # Explicit project name (app: claude-code-jaipuria-intelligence)
    $0 --user-id john_doe --project-name myapp  # Full customization
    $0 -u jane -p web-app -a http://192.168.1.100:8765

Environment Variables:
    USER_ID                  Default user ID to use
    OPENAI_API_URL          Default API URL to use
EOF
}

# Function to auto-detect project name
detect_project_name() {
    local project_name=""

    # Method 1: Check package.json for name field
    if [[ -f "package.json" ]]; then
        # Try to extract name from package.json using grep and sed (more flexible regex)
        project_name=$(grep -E '"name"[[:space:]]*:' package.json 2>/dev/null | head -n1 | sed 's/.*"name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
        if [[ -n "$project_name" && "$project_name" != "null" && "$project_name" != "" ]]; then
            echo "$project_name"
            return
        fi
    fi

    # Method 2: Check git remote origin URL
    if command -v git >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1; then
        project_name=$(git remote get-url origin 2>/dev/null | sed 's|.*[:/]||; s|\.git$||; s|/$||')
        if [[ -n "$project_name" ]]; then
            echo "$project_name"
            return
        fi
    fi

    # Method 3: Use current directory name as fallback
    project_name=$(basename "$PWD")
    if [[ -n "$project_name" && "$project_name" != "." && "$project_name" != "/" ]]; then
        echo "$project_name"
        return
    fi

    # Fallback to empty string if all methods fail
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--user-id)
            USER_ID="$2"
            shift 2
            ;;
        -p|--project-name)
            PROJECT_NAME="$2"
            shift 2
            ;;
        -a|--api-url)
            API_URL="$2"
            shift 2
            ;;
        -f|--file)
            MCP_FILE="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Auto-detect project name if not provided
if [[ -z "$PROJECT_NAME" ]]; then
    PROJECT_NAME=$(detect_project_name)
    if [[ -n "$PROJECT_NAME" ]]; then
        print_info "Auto-detected project name: $PROJECT_NAME"
    fi
fi

# Generate app name
if [[ -n "$PROJECT_NAME" ]]; then
    APP_NAME="claude-code-$PROJECT_NAME"
    print_info "Using project-specific app name: $APP_NAME"
else
    APP_NAME="claude-code"
    print_info "Using default app name: $APP_NAME"
fi

print_info "Setting up Claude Code integration with OpenMemory MCP..."
print_info "User ID: $USER_ID"
print_info "Project name: ${PROJECT_NAME:-"(default)"}"
print_info "App name: $APP_NAME"
print_info "API URL: $API_URL"
print_info "Configuration file: $MCP_FILE"

# Check if .mcp.json already exists
if [[ -f "$MCP_FILE" ]]; then
    print_warning "Configuration file '$MCP_FILE' already exists!"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Setup cancelled."
        exit 0
    fi
fi

# Create the .mcp.json configuration
cat > "$MCP_FILE" << EOF
{
  "mcpServers": {
    "openmemory": {
      "type": "sse",
      "url": "$API_URL/mcp/$APP_NAME/sse/$USER_ID",
      "headers": {},
      "description": "OpenMemory MCP Server - Private, local-first memory layer for Claude Code${PROJECT_NAME:+ (Project: $PROJECT_NAME)}"
    }
  }
}
EOF

if [[ $? -eq 0 ]]; then
    print_success "Configuration file '$MCP_FILE' created successfully!"
else
    print_error "Failed to create configuration file!"
    exit 1
fi

print_info "Setup complete! Next steps:"
echo "1. Make sure your OpenMemory server is running at $API_URL"
echo "2. Open your project in Claude Code"
echo "3. Claude Code should automatically detect the .mcp.json file"
echo "4. Start using memory commands like 'Remember that I prefer...' or 'What do you remember about...'"

print_success "OpenMemory is now integrated with Claude Code!"