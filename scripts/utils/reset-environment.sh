#!/bin/bash
#
# Jean Memory Environment Reset Script
# This script backs up any existing environment files and creates a clean slate
# It also removes any virtual environment and installed dependencies
#

set -e  # Exit on error

# Store the absolute path to the project root directory
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ANSI color codes for pretty output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Banner
echo -e "${BLUE}"
echo "┌───────────────────────────────────────────────────┐"
echo "│           Jean Memory Environment Reset           │"
echo "│     Backup Current Config & Prepare Fresh Start   │"
echo "└───────────────────────────────────────────────────┘"
echo -e "${NC}"

# Define file paths
ROOT_ENV="${ROOT_DIR}/.env"
API_ENV="${ROOT_DIR}/openmemory/api/.env"
UI_ENV="${ROOT_DIR}/openmemory/ui/.env.local"
ENV_TEMPLATE="${ROOT_DIR}/.env.template"
BACKUPS_DIR="${ROOT_DIR}/env_backups"
PYTHON_VENV="${ROOT_DIR}/openmemory/venv"
NODE_MODULES_UI="${ROOT_DIR}/openmemory/ui/node_modules"

# Create backups directory if it doesn't exist
mkdir -p "${BACKUPS_DIR}"

# Generate timestamp for backups
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Function to backup an environment file
backup_env_file() {
  local file_path="$1"
  local file_name=$(basename "$file_path")
  
  if [ -f "$file_path" ]; then
    local backup_path="${BACKUPS_DIR}/${file_name}.${TIMESTAMP}.bak"
    echo -e "${YELLOW}Backing up ${file_path} to ${backup_path}${NC}"
    cp "$file_path" "$backup_path"
    echo -e "${GREEN}✓ Backup created${NC}"
    return 0
  else
    echo -e "${YELLOW}No ${file_path} file found to backup${NC}"
    return 1
  fi
}

# Backup existing environment files
echo -e "${YELLOW}Backing up existing environment files...${NC}"
backup_env_file "$ROOT_ENV"
backup_env_file "$API_ENV"
backup_env_file "$UI_ENV"

# Ask for confirmation before removing files
echo ""
echo -e "${YELLOW}This will remove all current .env files to prepare for a fresh setup.${NC}"
read -p "Do you want to continue? (y/n): " confirm

if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
  echo -e "${BLUE}Operation cancelled. Your environment files remain unchanged.${NC}"
  echo -e "${BLUE}You can find backups in the ${BACKUPS_DIR} directory.${NC}"
  exit 0
fi

# Remove environment files
echo ""
echo -e "${YELLOW}Removing environment files...${NC}"
[ -f "$ROOT_ENV" ] && rm "$ROOT_ENV" && echo -e "${GREEN}✓ Removed $ROOT_ENV${NC}"
[ -f "$API_ENV" ] && rm "$API_ENV" && echo -e "${GREEN}✓ Removed $API_ENV${NC}"
[ -f "$UI_ENV" ] && rm "$UI_ENV" && echo -e "${GREEN}✓ Removed $UI_ENV${NC}"

# Clean up virtual environment
echo ""
echo -e "${YELLOW}Checking for Python virtual environment...${NC}"
if [ -d "$PYTHON_VENV" ]; then
    echo -e "${YELLOW}Removing Python virtual environment...${NC}"
    rm -rf "$PYTHON_VENV"
    echo -e "${GREEN}✓ Removed Python virtual environment${NC}"
else
    echo -e "${YELLOW}No Python virtual environment found${NC}"
fi

# Clean up node_modules
echo ""
echo -e "${YELLOW}Checking for Node modules...${NC}"
if [ -d "$NODE_MODULES_UI" ]; then
    echo -e "${YELLOW}Removing Node modules...${NC}"
    rm -rf "$NODE_MODULES_UI"
    echo -e "${GREEN}✓ Removed Node modules${NC}"
else
    echo -e "${YELLOW}No Node modules found${NC}"
fi

# Create fresh .env from template
if [ -f "$ENV_TEMPLATE" ]; then
  echo -e "${YELLOW}Creating fresh $ROOT_ENV from template...${NC}"
  cp "$ENV_TEMPLATE" "$ROOT_ENV"
  echo -e "${GREEN}✓ Fresh $ROOT_ENV created${NC}"
else
  echo -e "${RED}Warning: $ENV_TEMPLATE not found. Cannot create fresh $ROOT_ENV${NC}"
fi

# Final instructions
echo ""
echo -e "${BLUE}"
echo "┌───────────────────────────────────────────────────┐"
echo "│              Environment Reset Complete           │"
echo "└───────────────────────────────────────────────────┘"
echo -e "${NC}"

echo -e "${GREEN}Your environment has been reset!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Edit the .env file with your new API keys"
echo "  2. Run ./setup-hybrid.sh to set up with your new environment"
echo ""
echo -e "${BLUE}Your previous configuration is backed up in the ${BACKUPS_DIR} directory.${NC}"
echo -e "${BLUE}You can restore it at any time by copying files back from there.${NC}"
