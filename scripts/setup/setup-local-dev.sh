#!/usr/bin/env bash

# Jean Memory Local Development Setup
# This script sets up your local development environment for Jean Memory

set -e  # Exit immediately if a command fails

echo "🧠 Setting up Jean Memory development environment"

# Get the base directory
BASE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
API_DIR="${BASE_DIR}/openmemory/api"
UI_DIR="${BASE_DIR}/openmemory/ui"

# Create local environment files if they don't exist
setup_env_files() {
  echo "📄 Checking environment files..."
  
  # API environment setup
  if [ ! -f "${API_DIR}/.env" ]; then
    echo "Creating API .env file from example..."
    cp "${API_DIR}/.env.example" "${API_DIR}/.env"
    
    # Update the environment file for local development
    # Replace remote database connection with local database
    sed -i '' 's|postgresql://.*@db..*:5432/postgres|postgresql://jean_memory:memory_password@localhost:5432/jean_memory_db|g' "${API_DIR}/.env"
    
    # Use local Qdrant instead of remote
    sed -i '' 's|QDRANT_HOST=.*|QDRANT_HOST=localhost|g' "${API_DIR}/.env"
    sed -i '' 's|QDRANT_API_KEY=.*|QDRANT_API_KEY=|g' "${API_DIR}/.env"
    
    # Enable local auth mode with default user
    echo "\n# Local development auth" >> "${API_DIR}/.env"
    echo "USER_ID=default_user" >> "${API_DIR}/.env"
    
    echo "⚠️ Please edit ${API_DIR}/.env and add your API keys like GEMINI_API_KEY"
  else
    echo "✅ API .env file already exists"
  fi
  
  # UI environment setup
  if [ ! -f "${UI_DIR}/.env.local" ]; then
    echo "Creating UI .env.local file from example..."
    cp "${UI_DIR}/.env.example" "${UI_DIR}/.env.local"
    
    # Update for local development
    # Point to local API instead of production
    sed -i '' 's|NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=http://localhost:8765|g' "${UI_DIR}/.env.local"
    
    # Disable email verification for local dev
    echo "# Local development settings" >> "${UI_DIR}/.env.local"
    echo "NEXT_PUBLIC_DISABLE_EMAIL_VERIFICATION=true" >> "${UI_DIR}/.env.local"
    echo "NEXT_PUBLIC_IS_LOCAL_DEV=true" >> "${UI_DIR}/.env.local"
    echo "NEXT_PUBLIC_USER_ID=default_user" >> "${UI_DIR}/.env.local"
    
    echo "⚠️ Please edit ${UI_DIR}/.env.local and add required API keys"
  else
    echo "✅ UI .env.local file already exists"
  fi
}

# Wait for PostgreSQL to be ready
wait_for_postgres() {
  echo "⏳ Waiting for PostgreSQL to be ready..."
  
  # Default max retries
  max_retries=30
  retry_count=0
  
  while [ $retry_count -lt $max_retries ]
  do
    # Try to connect to postgres
    if docker exec jeanmemory_postgres_service pg_isready -U jean_memory -d jean_memory_db > /dev/null 2>&1; then
      echo "✅ PostgreSQL is ready!"
      return 0
    fi
    
    echo "Waiting for PostgreSQL to start... ($(($retry_count + 1))/$max_retries)"
    sleep 2
    retry_count=$(($retry_count + 1))
  done
  
  echo "❌ PostgreSQL did not become ready in time."
  return 1
}

# Run database migrations
run_migrations() {
  echo "🔎 Running database migrations..."
  
  # Wait for PostgreSQL to be ready before running migrations
  wait_for_postgres
  
  python3 run_migrations.py
}

# Check if Docker is running
check_docker() {
  if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker and try again."
    exit 1
  else
    echo "✅ Docker is running"
  fi
}

# Handle Docker services
handle_docker_services() {
  local mode=$1
  echo "🚀 Managing Docker services..."
  
  if [ ! -f "docker-compose.yml" ]; then
    echo "⚠️ Warning: docker-compose.yml not found. Cannot manage Docker services."
    return 1
  fi
  
  case "$mode" in
    "restart")
      echo "Stopping existing Docker services..."
      docker-compose down
      echo "Starting Docker services with persisted data..."
      docker-compose up -d
      echo "✅ Docker services restarted"
      ;;
    "fresh")
      echo "Stopping and removing existing Docker services and volumes..."
      docker-compose down -v
      echo "Starting Docker services with fresh data..."
      docker-compose up -d
      echo "✅ Fresh Docker services started"
      ;;
    "stop")
      echo "Stopping Docker services (keeping data volumes)..."
      docker-compose down
      echo "✅ Docker services stopped"
      ;;
    *)
      # Default to just ensuring services are running
      echo "Ensuring Docker services are running..."
      docker-compose up -d
      echo "✅ Docker services started/running"
      ;;
  esac
}

# Setup Qdrant collection
setup_qdrant() {
  echo "🔍 Setting up Qdrant collection..."
  # Wait for Qdrant to be available
  echo "Waiting for Qdrant to be ready..."
  sleep 5
  
  if [ -f "fix_qdrant_collection.py" ]; then
    python3 fix_qdrant_collection.py
  else
    echo "⚠️ Warning: fix_qdrant_collection.py not found. Skipping Qdrant setup."
  fi
}

# Setup virtual environment
setup_venv() {
  echo "🐍 Setting up Python virtual environment..."
  VENV_DIR="${API_DIR}/venv"
  
  # Check if venv exists
  if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    cd "${API_DIR}"
    python3 -m venv venv
    echo "✅ Virtual environment created at $VENV_DIR"
  else
    echo "✅ Virtual environment already exists at $VENV_DIR"
  fi
  
  # Activate virtual environment
  echo "Activating virtual environment..."
  source "${VENV_DIR}/bin/activate"
  cd "${BASE_DIR}"
  echo "✅ Virtual environment activated"
}

# Install requirements
install_requirements() {
  echo "📦 Installing Python requirements..."
  cd "${API_DIR}"
  pip install -r requirements.txt
  cd "${BASE_DIR}"
  echo "✅ Python requirements installed"
}

# Install UI dependencies
install_ui_dependencies() {
  echo "📦 Installing UI dependencies..."
  cd "${UI_DIR}"
  
  # Check if npm is installed
  if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed. Please install Node.js and npm."
    return 1
  fi
  
  echo "Installing UI dependencies with npm..."
  npm install --legacy-peer-deps
  
  cd "${BASE_DIR}"
  echo "✅ UI dependencies installed"
}

# Create convenience scripts for starting servers
create_start_scripts() {
  echo "📝 Creating convenience scripts for starting servers..."
  
  # Create API start script
  cat > "${BASE_DIR}/start-api.sh" << EOL
#!/usr/bin/env bash
source "${API_DIR}/venv/bin/activate"
cd "${API_DIR}"
echo "🚀 Starting API server on port 8765..."
uvicorn main:app --host 0.0.0.0 --port 8765 --reload
EOL
  chmod +x "${BASE_DIR}/start-api.sh"
  
  # Create UI start script
  cat > "${BASE_DIR}/start-ui.sh" << EOL
#!/usr/bin/env bash
cd "${UI_DIR}"
echo "🚀 Starting UI server..."
npm run dev
EOL
  chmod +x "${BASE_DIR}/start-ui.sh"
  
  echo "✅ Start scripts created: ./start-api.sh and ./start-ui.sh"
}

# Parse command line arguments
parse_args() {
  MODE="restart"  # Default mode - restart containers but keep data
  
  while [[ $# -gt 0 ]]; do
    case $1 in
      --fresh)
        MODE="fresh"
        shift
        ;;
      --clean)
        MODE="stop"
        shift
        ;;
      *)
        echo "Unknown option: $1"
        echo "Usage: $0 [--fresh] [--clean]"
        echo "  --fresh: Start with fresh databases (removes all existing data)"
        echo "  --clean: Stop containers and exit without starting anything"
        exit 1
        ;;
    esac
  done
  
  export MODE
}

# Main setup process
main() {
  echo "🚀 Starting setup process..."
  
  # Parse command line arguments
  parse_args "$@"
  
  # Check prerequisites
  check_docker
  
  # Handle Docker services based on mode
  handle_docker_services "$MODE"
  
  # If we're just cleaning up, exit here
  if [ "$MODE" = "stop" ]; then
    echo "Cleanup complete. Containers stopped and data preserved."
    return 0
  fi
  
  # Setup environment files
  setup_env_files
  
  # Setup virtual environment
  setup_venv
  
  # Install backend requirements
  install_requirements
  
  # Install UI dependencies
  install_ui_dependencies || echo "⚠️ UI dependency installation had issues. You may need to install them manually."
  
  # Run database migrations
  run_migrations
  
  # Setup Qdrant collection
  setup_qdrant
  
  # Create convenience scripts
  create_start_scripts
  
  echo "✨ Setup complete! You can now start your local development servers."
  echo ""
  echo "🚀 STARTING THE SERVERS:"
  echo "  1. To start the API server (backend):"
  echo "     ./start-api.sh"
  echo ""
  echo "  2. To start the UI server (frontend):"
  echo "     ./start-ui.sh"
  echo ""
  echo "📔 LOCAL DEVELOPMENT SERVICES:"
  echo "   - API Server: http://localhost:8765"
  echo "   - UI Server: http://localhost:3000"
  echo "   - PostgreSQL: localhost:5432 (User: jean_memory, Password: memory_password, DB: jean_memory_db)"
  echo "   - Qdrant: localhost:6333 (API), localhost:6334 (HTTP UI)"
  echo ""
  echo "💾 DATA PERSISTENCE & MAINTENANCE:"
  echo "   - Your data is saved in Docker volumes (postgres_data and qdrant_data)"
  echo "   - To restart containers without losing data: ./setup-local-dev.sh"
  echo "   - To start with fresh databases: ./setup-local-dev.sh --fresh"
  echo "   - To stop all containers: ./setup-local-dev.sh --clean"
  echo ""
  echo "⚠️ IMPORTANT REMINDERS: "
  echo "   1. The Life Assistant feature requires GEMINI_API_KEY to be set in both:"
  echo "      - /openmemory/api/.env (for the backend)"
  echo "      - /openmemory/ui/.env.local (for the frontend)"
  echo "   2. Email verification is disabled in local development"
  echo "   3. All data is stored locally in Docker containers and won't affect production"
  echo "   4. You must restart the servers after changing environment variables"
}

# Run the main function with all command line arguments
main "$@"
