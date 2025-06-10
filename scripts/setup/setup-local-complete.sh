#!/bin/bash
# Complete Local Development Setup for Jean Memory
# This script handles all known issues and ensures a smooth local setup

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🧠 Jean Memory Complete Local Development Setup${NC}"
echo -e "${BLUE}================================================${NC}"

# Get the base directory
BASE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$BASE_DIR"

# Step 1: Check prerequisites
echo -e "\n${YELLOW}Step 1: Checking prerequisites...${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker is installed and running${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python is installed${NC}"

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is not installed.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Node.js is installed${NC}"

# Step 2: Stop any conflicting services
echo -e "\n${YELLOW}Step 2: Stopping conflicting services...${NC}"

# Stop host PostgreSQL if running
if command -v brew &> /dev/null; then
    if brew services list | grep -q "postgresql.*started"; then
        echo "Stopping host PostgreSQL service..."
        brew services stop postgresql@14 2>/dev/null || brew services stop postgresql 2>/dev/null || true
        echo -e "${GREEN}✅ Host PostgreSQL stopped${NC}"
    fi
fi

# Kill any process using port 8765
if lsof -ti:8765 > /dev/null 2>&1; then
    echo "Killing process on port 8765..."
    kill -9 $(lsof -ti:8765) 2>/dev/null || true
fi

# Kill any process using port 3000
if lsof -ti:3000 > /dev/null 2>&1; then
    echo "Killing process on port 3000..."
    kill -9 $(lsof -ti:3000) 2>/dev/null || true
fi

echo -e "${GREEN}✅ Conflicting services stopped${NC}"

# Step 3: Setup environment files
echo -e "\n${YELLOW}Step 3: Setting up environment files...${NC}"

# Create .env.template if it doesn't exist
if [ ! -f ".env.template" ]; then
    cat > ".env.template" << 'EOL'
# Jean Memory Local Development Configuration

# Database Configuration
DATABASE_URL=postgresql://jean_memory:memory_password@127.0.0.1:5432/jean_memory_db

# Qdrant Configuration
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=
MAIN_QDRANT_COLLECTION_NAME=jonathans_memory_main

# OpenAI Configuration (Required)
OPENAI_API_KEY=your-openai-api-key-here

# Local Development Auth
USER_ID=00000000-0000-0000-0000-000000000001

# Placeholder Supabase Config (for compatibility)
SUPABASE_URL=http://localhost:8000
SUPABASE_ANON_KEY=local-dev-anon-key
SUPABASE_SERVICE_KEY=local-dev-service-key
EOL
    echo -e "${GREEN}✅ Created .env.template${NC}"
fi

# Setup API environment
API_ENV="${BASE_DIR}/openmemory/api/.env"
if [ ! -f "$API_ENV" ]; then
    cp "${BASE_DIR}/openmemory/api/.env.example" "$API_ENV" 2>/dev/null || cp ".env.template" "$API_ENV"
fi

# Update API .env for local development
echo -e "${YELLOW}Configuring API environment for local development...${NC}"
sed -i '' 's|DATABASE_URL=.*|DATABASE_URL=postgresql://jean_memory:memory_password@127.0.0.1:5432/jean_memory_db|' "$API_ENV"
sed -i '' 's|QDRANT_HOST=.*|QDRANT_HOST=localhost|' "$API_ENV"
sed -i '' 's|QDRANT_API_KEY=.*|QDRANT_API_KEY=|' "$API_ENV"

# Ensure USER_ID is set as a valid UUID
if ! grep -q "USER_ID=" "$API_ENV"; then
    echo "USER_ID=00000000-0000-0000-0000-000000000001" >> "$API_ENV"
else
    sed -i '' 's|USER_ID=.*|USER_ID=00000000-0000-0000-0000-000000000001|' "$API_ENV"
fi

# Setup UI environment
UI_ENV="${BASE_DIR}/openmemory/ui/.env.local"
if [ ! -f "$UI_ENV" ]; then
    cat > "$UI_ENV" << 'EOL'
# Jean Memory UI Local Development
NEXT_PUBLIC_API_URL=http://localhost:8765
NEXT_PUBLIC_SUPABASE_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_ANON_KEY=local-dev-anon-key
NEXT_PUBLIC_USER_ID=00000000-0000-0000-0000-000000000001
NEXT_PUBLIC_IS_LOCAL_DEV=true
NEXT_PUBLIC_DISABLE_EMAIL_VERIFICATION=true
EOL
fi

echo -e "${GREEN}✅ Environment files configured${NC}"

# Step 4: Start Docker containers
echo -e "\n${YELLOW}Step 4: Starting Docker containers...${NC}"

# Stop and remove existing containers
docker-compose down -v 2>/dev/null || true

# Start fresh containers
docker-compose up -d

# Wait for containers to be ready
echo "Waiting for containers to start..."
sleep 5

# Verify containers are running
if ! docker ps | grep -q jeanmemory_postgres_service; then
    echo -e "${RED}❌ PostgreSQL container failed to start${NC}"
    docker-compose logs postgres_db
    exit 1
fi

if ! docker ps | grep -q jeanmemory_qdrant_service; then
    echo -e "${RED}❌ Qdrant container failed to start${NC}"
    docker-compose logs qdrant_db
    exit 1
fi

echo -e "${GREEN}✅ Docker containers started${NC}"

# Step 5: Setup Python environment
echo -e "\n${YELLOW}Step 5: Setting up Python environment...${NC}"

cd "${BASE_DIR}/openmemory"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r api/requirements.txt

echo -e "${GREEN}✅ Python environment ready${NC}"

# Step 6: Initialize database
echo -e "\n${YELLOW}Step 6: Initializing database...${NC}"

cd "$BASE_DIR"

# Wait for PostgreSQL to be ready
max_retries=30
retry_count=0
while [ $retry_count -lt $max_retries ]; do
    if docker exec jeanmemory_postgres_service pg_isready -U jean_memory -d jean_memory_db > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PostgreSQL is ready${NC}"
        break
    fi
    echo "Waiting for PostgreSQL... ($((retry_count + 1))/$max_retries)"
    sleep 2
    retry_count=$((retry_count + 1))
done

if [ $retry_count -eq $max_retries ]; then
    echo -e "${RED}❌ PostgreSQL did not become ready in time${NC}"
    exit 1
fi

# Create a simplified database schema for local development
cat > "${BASE_DIR}/init-local-db-simple.sql" << 'EOL'
-- Jean Memory Local Development Database Schema
-- Simplified schema focusing on core functionality

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop existing tables if they exist
DROP TABLE IF EXISTS memory_associations CASCADE;
DROP TABLE IF EXISTS memory_tags CASCADE;
DROP TABLE IF EXISTS memory_relations CASCADE;
DROP TABLE IF EXISTS memory_entities CASCADE;
DROP TABLE IF EXISTS memory_messages CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS memories CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS alembic_version CASCADE;

-- Create users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert default user with specific UUID
INSERT INTO users (id, email) VALUES 
    ('00000000-0000-0000-0000-000000000001', 'default@local.dev')
ON CONFLICT (id) DO NOTHING;

-- Create memories table
CREATE TABLE memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create messages table
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create memory_messages table
CREATE TABLE memory_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    memory_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(memory_id, message_id)
);

-- Create memory_entities table
CREATE TABLE memory_entities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    memory_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    entity_type VARCHAR(100) NOT NULL,
    entity_value TEXT NOT NULL,
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create memory_relations table
CREATE TABLE memory_relations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    memory_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create memory_tags table
CREATE TABLE memory_tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    memory_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    tag VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(memory_id, tag)
);

-- Create memory_associations table
CREATE TABLE memory_associations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    memory_id_1 UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    memory_id_2 UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    association_type VARCHAR(100),
    strength FLOAT DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(memory_id_1, memory_id_2)
);

-- Create alembic version table
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Insert initial version
INSERT INTO alembic_version (version_num) VALUES ('initial');

-- Create indexes
CREATE INDEX idx_memories_user_id ON memories(user_id);
CREATE INDEX idx_memories_created_at ON memories(created_at);
CREATE INDEX idx_messages_user_id ON messages(user_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_memory_messages_memory_id ON memory_messages(memory_id);
CREATE INDEX idx_memory_messages_message_id ON memory_messages(message_id);
CREATE INDEX idx_memory_entities_memory_id ON memory_entities(memory_id);
CREATE INDEX idx_memory_relations_memory_id ON memory_relations(memory_id);
CREATE INDEX idx_memory_tags_memory_id ON memory_tags(memory_id);
CREATE INDEX idx_memory_tags_tag ON memory_tags(tag);
CREATE INDEX idx_memory_associations_memory_id_1 ON memory_associations(memory_id_1);
CREATE INDEX idx_memory_associations_memory_id_2 ON memory_associations(memory_id_2);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO jean_memory;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO jean_memory;
EOL

# Initialize database schema
docker exec -i jeanmemory_postgres_service psql -U jean_memory -d jean_memory_db < "${BASE_DIR}/init-local-db-simple.sql"
echo -e "${GREEN}✅ Database schema initialized${NC}"

# Step 7: Setup Qdrant
echo -e "\n${YELLOW}Step 7: Setting up Qdrant...${NC}"

# Wait for Qdrant to be ready
max_retries=30
retry_count=0
while [ $retry_count -lt $max_retries ]; do
    if curl -s http://localhost:6333/collections > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Qdrant is ready${NC}"
        break
    fi
    echo "Waiting for Qdrant... ($((retry_count + 1))/$max_retries)"
    sleep 2
    retry_count=$((retry_count + 1))
done

if [ $retry_count -eq $max_retries ]; then
    echo -e "${YELLOW}⚠️  Qdrant did not respond in time, but continuing...${NC}"
fi

# Run Qdrant setup
cd "${BASE_DIR}/openmemory"
source venv/bin/activate
cd "$BASE_DIR"
python fix_qdrant_collection.py
echo -e "${GREEN}✅ Qdrant collection configured${NC}"

# Step 8: Install UI dependencies
echo -e "\n${YELLOW}Step 8: Installing UI dependencies...${NC}"

cd "${BASE_DIR}/openmemory/ui"
npm install --legacy-peer-deps
echo -e "${GREEN}✅ UI dependencies installed${NC}"

# Step 9: Create start scripts
echo -e "\n${YELLOW}Step 9: Creating start scripts...${NC}"

# Create API start script
cat > "${BASE_DIR}/start-api.sh" << 'EOL'
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/openmemory"
source venv/bin/activate
cd api
echo "🚀 Starting API server on http://localhost:8765"
python -m uvicorn main:app --host 0.0.0.0 --port 8765 --reload
EOL
chmod +x "${BASE_DIR}/start-api.sh"

# Create UI start script
cat > "${BASE_DIR}/start-ui.sh" << 'EOL'
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/openmemory/ui"
echo "🚀 Starting UI server on http://localhost:3000"
npm run dev
EOL
chmod +x "${BASE_DIR}/start-ui.sh"

# Create a combined start script
cat > "${BASE_DIR}/start-all.sh" << 'EOL'
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "🚀 Starting Jean Memory Local Development"
echo "========================================"

# Start API in background
echo "Starting API server..."
"$SCRIPT_DIR/start-api.sh" &
API_PID=$!

# Wait a bit for API to start
sleep 5

# Start UI
echo "Starting UI server..."
"$SCRIPT_DIR/start-ui.sh" &
UI_PID=$!

echo ""
echo "Services started:"
echo "- API: http://localhost:8765 (PID: $API_PID)"
echo "- UI: http://localhost:3000 (PID: $UI_PID)"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for interrupt
trap "echo 'Stopping services...'; kill $API_PID $UI_PID; exit" INT
wait
EOL
chmod +x "${BASE_DIR}/start-all.sh"

echo -e "${GREEN}✅ Start scripts created${NC}"

# Step 10: Final verification
echo -e "\n${YELLOW}Step 10: Running verification tests...${NC}"

cd "$BASE_DIR"

# Test database connection
if PGPASSWORD=memory_password psql -h 127.0.0.1 -U jean_memory -d jean_memory_db -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Database connection verified${NC}"
else
    echo -e "${RED}❌ Database connection failed${NC}"
fi

# Test Qdrant connection
if curl -s http://localhost:6333/collections > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Qdrant connection verified${NC}"
else
    echo -e "${RED}❌ Qdrant connection failed${NC}"
fi

# Deactivate virtual environment
deactivate

echo -e "\n${GREEN}🎉 Setup complete!${NC}"
echo -e "\n${BLUE}To start the application:${NC}"
echo -e "Option 1 - Start both services: ${YELLOW}./start-all.sh${NC}"
echo -e "Option 2 - Start separately:"
echo -e "  - In terminal 1: ${YELLOW}./start-api.sh${NC}"
echo -e "  - In terminal 2: ${YELLOW}./start-ui.sh${NC}"
echo -e "\n${BLUE}Access the application at:${NC}"
echo -e "- API: ${YELLOW}http://localhost:8765${NC}"
echo -e "- UI: ${YELLOW}http://localhost:3000${NC}"
echo -e "\n${BLUE}To verify everything is working:${NC}"
echo -e "${YELLOW}cd openmemory && source venv/bin/activate && cd .. && python test-complete-local-setup.py${NC}" 