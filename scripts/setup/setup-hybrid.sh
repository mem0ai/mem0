#!/bin/bash
#
# Jean Memory Hybrid Setup Script
# This script configures Jean Memory to run locally while using cloud services for data storage
#

set -e  # Exit on error

# Store the absolute path to the project root directory
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check for flags
USE_EXISTING_ENV=false
SKIP_INTERACTIVE=false

# Process all arguments
for arg in "$@"; do
  if [[ "$arg" == "--use-existing-env" ]]; then
    USE_EXISTING_ENV=true
  elif [[ "$arg" == "--skip-interactive" ]]; then
    SKIP_INTERACTIVE=true
  fi
done

# ANSI color codes for pretty output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Banner
echo -e "${BLUE}"
echo "┌───────────────────────────────────────────────────┐"
echo "│             Jean Memory Hybrid Setup              │"
echo "│      Local Application + Cloud Data Services      │"
echo "└───────────────────────────────────────────────────┘"
echo -e "${NC}"

# Setup paths
ENV_TEMPLATE="${ROOT_DIR}/.env.template"
ENV_FILE="${ROOT_DIR}/.env"
API_DIR="${ROOT_DIR}/openmemory/api"
API_ENV_PATH="${API_DIR}/.env"
UI_DIR="${ROOT_DIR}/openmemory/ui"
UI_ENV_PATH="${UI_DIR}/.env.local"

# Check if required files and directories exist
echo -e "${YELLOW}Checking required files and directories...${NC}"

if [ ! -d "${ROOT_DIR}/openmemory" ]; then
  echo -e "${RED}Error: openmemory directory not found${NC}"
  exit 1
fi

if [ ! -f "$ENV_TEMPLATE" ]; then
  echo -e "${RED}Error: .env.template file not found${NC}"
  exit 1
fi

# Create or update .env file
if [ "$USE_EXISTING_ENV" = true ] && [ -f "$ENV_FILE" ] && [ -s "$ENV_FILE" ]; then
  echo -e "${GREEN}Using existing .env file at ${ENV_FILE}${NC}"
  
  # Source the .env file to get the variables
  set -a  # Export all variables by default
  source "$ENV_FILE"
  set +a
  
  # Ensure we have all required variables from the file
  if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_ANON_KEY" ] || [ -z "$SUPABASE_SERVICE_KEY" ] || 
     [ -z "$QDRANT_HOST" ] || [ -z "$QDRANT_API_KEY" ] || [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}Error: Missing required environment variables in .env file${NC}"
    echo -e "${YELLOW}Please run the setup script without the --use-existing-env flag to enter all required information${NC}"
    exit 1
  fi
  
  # Set variables from the environment
  supabase_url="$SUPABASE_URL"
  supabase_anon_key="$SUPABASE_ANON_KEY"
  supabase_service_key="$SUPABASE_SERVICE_KEY"
  qdrant_host="$QDRANT_HOST"
  qdrant_port="${QDRANT_PORT:-6333}"
  qdrant_api_key="$QDRANT_API_KEY"
  qdrant_collection="${MAIN_QDRANT_COLLECTION_NAME:-jonathans_memory_main}"
  openai_api_key="$OPENAI_API_KEY"
  
  # Extract Supabase project ID from URL for database connection
  if [[ $supabase_url =~ https://([^.]+)\. ]]; then
    project_id=${BASH_REMATCH[1]}
    supabase_db_host="db.${project_id}.supabase.co"
    supabase_db_name="postgres"
    supabase_db_user="postgres"
    supabase_db_password="postgres"  # Default password, will be updated later if provided
  else
    echo -e "${YELLOW}Warning: Could not extract project ID from Supabase URL${NC}"
    echo -e "${YELLOW}Using default database connection parameters${NC}"
    supabase_db_host="db.supabase.co"
    supabase_db_name="postgres"
    supabase_db_user="postgres"
    supabase_db_password="postgres"
  fi
  
  echo -e "${GREEN}✓ Environment variables loaded from file${NC}"
else
  echo -e "${YELLOW}Setting up new environment configuration...${NC}"
  
  # Copy template if .env doesn't exist
  if [ ! -f "$ENV_FILE" ]; then
    cp "$ENV_TEMPLATE" "$ENV_FILE"
    echo -e "${GREEN}✓ Created $ENV_FILE from template${NC}"
  fi
  
  echo -e "${BLUE}Please provide the following credentials:${NC}"
  
  # Prompt for Supabase credentials
  read -p "Supabase URL: " supabase_url
  read -p "Supabase Anon Key: " supabase_anon_key
  read -p "Supabase Service Key: " supabase_service_key
  
  # Validate Supabase inputs
  while [ -z "$supabase_url" ] || [ -z "$supabase_anon_key" ] || [ -z "$supabase_service_key" ]; do
    echo -e "${RED}Error: All Supabase credentials are required${NC}"
    read -p "Supabase URL: " supabase_url
    read -p "Supabase Anon Key: " supabase_anon_key
    read -p "Supabase Service Key: " supabase_service_key
  done
  
  # Prompt for Qdrant credentials
  read -p "Qdrant Cloud Host: " qdrant_host
  read -p "Qdrant Port (default: 6333): " qdrant_port_input
  qdrant_port=${qdrant_port_input:-6333}
  read -p "Qdrant API Key: " qdrant_api_key
  read -p "Qdrant Collection Name (default: jonathans_memory_main): " qdrant_collection_input
  qdrant_collection=${qdrant_collection_input:-jonathans_memory_main}
  
  # Validate Qdrant inputs
  while [ -z "$qdrant_host" ] || [ -z "$qdrant_api_key" ]; do
    echo -e "${RED}Error: Qdrant host and API key are required${NC}"
    read -p "Qdrant Cloud Host: " qdrant_host
    read -p "Qdrant API Key: " qdrant_api_key
  done
  
  # Prompt for OpenAI API key
  read -p "OpenAI API Key: " openai_api_key
  
  # Validate OpenAI API key
  while [ -z "$openai_api_key" ]; do
    echo -e "${RED}Error: OpenAI API key is required${NC}"
    read -p "OpenAI API Key: " openai_api_key
  done
  
  # Prompt for Supabase database password
  read -p "Supabase Database Password (default: postgres): " db_password_input
  db_password=${db_password_input:-postgres}
  
  # Extract Supabase project ID from URL for database connection
  if [[ $supabase_url =~ https://([^.]+)\. ]]; then
    project_id=${BASH_REMATCH[1]}
    supabase_db_host="db.${project_id}.supabase.co"
    supabase_db_name="postgres"
    supabase_db_user="postgres"
    supabase_db_password="$db_password"
  else
    echo -e "${RED}Error: Invalid Supabase URL format${NC}"
    exit 1
  fi
fi

# Generate the database URL
database_url="postgresql://${supabase_db_user}:${supabase_db_password}@${supabase_db_host}:5432/${supabase_db_name}"

# Create the .env file with all configuration
echo -e "${YELLOW}Creating environment configuration files...${NC}"

# Update the main .env file with all variables
cat > "$ENV_FILE" << EOL
# Jean Memory Hybrid Setup Environment

# Supabase Configuration
SUPABASE_URL=${supabase_url}
SUPABASE_ANON_KEY=${supabase_anon_key}
SUPABASE_SERVICE_KEY=${supabase_service_key}

# Qdrant Configuration
QDRANT_HOST=${qdrant_host}
QDRANT_PORT=${qdrant_port}
QDRANT_API_KEY=${qdrant_api_key}
MAIN_QDRANT_COLLECTION_NAME=${qdrant_collection}

# OpenAI Configuration
OPENAI_API_KEY=${openai_api_key}

# Optional: LLM and Embedder Model Configuration
# Uncomment and modify these lines if you want to use different models
# LLM_MODEL_NAME=gpt-3.5-turbo
# EMBEDDER_MODEL_NAME=text-embedding-ada-002

# Database Connection String
DATABASE_URL=${database_url}
EOL

echo -e "${GREEN}✓ Environment configuration created${NC}"

# Copy the .env file to the API directory
echo -e "${YELLOW}Copying configuration to API directory...${NC}"
cp "$ENV_FILE" "$API_ENV_PATH"
echo -e "${GREEN}✓ Configuration copied to API directory${NC}"

# Setup Python virtual environment exactly as the Makefile expects it
echo -e "${YELLOW}Setting up Python environment...${NC}"
cd "${ROOT_DIR}/openmemory"

# Clean up any existing broken venv if needed
if [ -d "venv" ] && [ ! -f "venv/bin/activate" ]; then
  echo -e "${YELLOW}Found broken virtual environment, removing...${NC}"
  rm -rf venv
fi

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
  echo -e "${YELLOW}Creating new Python virtual environment...${NC}"
  python3 -m venv venv
  echo -e "${GREEN}✓ Virtual environment created${NC}"
else
  echo -e "${GREEN}✓ Using existing virtual environment${NC}"
fi

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install -r api/requirements.txt
echo -e "${GREEN}✓ Python dependencies installed${NC}"

# Run database migrations
echo -e "${YELLOW}Checking database migrations...${NC}"
cd "${ROOT_DIR}"
python_script="${ROOT_DIR}/run_migrations.py"

if [ -f "$python_script" ]; then
  echo -e "${YELLOW}Running database migrations...${NC}"
  python "$python_script"
  echo -e "${GREEN}✓ Database migrations completed${NC}"
else
  echo -e "${RED}Warning: run_migrations.py not found. Skipping migrations.${NC}"
fi

# Fix Qdrant collection (create payload index)
echo -e "${YELLOW}Setting up Qdrant collection...${NC}"
cd "${ROOT_DIR}"
qdrant_script="${ROOT_DIR}/fix_qdrant_collection.py"

if [ -f "$qdrant_script" ]; then
  echo -e "${YELLOW}Running Qdrant collection fix...${NC}"
  python "$qdrant_script"
  echo -e "${GREEN}✓ Qdrant collection setup completed${NC}"
else
  echo -e "${RED}Warning: fix_qdrant_collection.py not found. Skipping Qdrant setup.${NC}"
fi

# Install UI dependencies
echo -e "${YELLOW}Setting up UI dependencies...${NC}"
cd "${ROOT_DIR}/openmemory/ui"

# Check for existing node_modules
if [ -d "node_modules" ]; then
  echo -e "${YELLOW}Using existing node_modules. If you encounter issues, delete this folder and run setup again.${NC}"
else
  echo -e "${YELLOW}Installing npm packages...${NC}"
  # Try to use the same approach as in the Makefile
  if command -v pnpm >/dev/null 2>&1; then
    echo -e "${YELLOW}Using pnpm for installation...${NC}"
    pnpm install --no-frozen-lockfile
  else
    echo -e "${YELLOW}Using npm for installation...${NC}"
    npm install --legacy-peer-deps
  fi
fi

# Create UI environment file
echo -e "${YELLOW}Creating UI environment configuration...${NC}"
cat > "${UI_ENV_PATH}" << EOL
# Jean Memory UI Environment
NEXT_PUBLIC_API_URL=http://localhost:8765
NEXT_PUBLIC_SUPABASE_URL=${supabase_url}
NEXT_PUBLIC_SUPABASE_ANON_KEY=${supabase_anon_key}
NEXT_PUBLIC_USER_ID=default_user
EOL

echo -e "${GREEN}✓ UI environment configured${NC}"

# Return to project root
cd "${ROOT_DIR}"
echo -e "${GREEN}✓ UI dependencies installed${NC}"

# Successfully completed setup
echo -e "${GREEN}"
echo "┌───────────────────────────────────────────────────┐"
echo "│           Jean Memory Hybrid Setup Complete       │"
echo "└───────────────────────────────────────────────────┘"
echo -e "${NC}"

echo -e "${BLUE}Next Steps:${NC}"
echo -e "1. ${YELLOW}Start the API:${NC} cd ${ROOT_DIR} && bash jean-memory.sh start-api"
echo -e "2. ${YELLOW}Start the UI:${NC} cd ${ROOT_DIR} && bash jean-memory.sh start-ui"
echo -e "3. ${YELLOW}Access the application:${NC} http://localhost:3000"

echo -e "${BLUE}For help with other commands:${NC}"
echo -e "   ${YELLOW}bash jean-memory.sh help${NC}"

echo -e "${GREEN}Happy coding!${NC}"
