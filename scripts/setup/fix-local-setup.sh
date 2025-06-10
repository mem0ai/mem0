#!/bin/bash
# Fix script for Jean Memory local development setup issues

set -e

echo "🔧 Fixing Jean Memory Local Development Setup Issues"

# Get the base directory
BASE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 1. Create missing .env.template if it doesn't exist
if [ ! -f "${BASE_DIR}/.env.template" ]; then
    echo "📝 Creating missing .env.template file..."
    cat > "${BASE_DIR}/.env.template" << 'EOL'
# Jean Memory Environment Configuration Template
# Copy this file to .env and fill in your values

# ====================
# Supabase Configuration (Required for Hybrid Setup)
# ====================
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key-here
SUPABASE_SERVICE_KEY=your-service-key-here

# ====================
# Qdrant Configuration
# ====================
# For local Docker setup:
# QDRANT_HOST=localhost
# QDRANT_PORT=6333
# QDRANT_API_KEY=

# For Qdrant Cloud:
QDRANT_HOST=your-qdrant-cloud-host
QDRANT_PORT=6333
QDRANT_API_KEY=your-qdrant-api-key
MAIN_QDRANT_COLLECTION_NAME=jonathans_memory_main

# ====================
# OpenAI Configuration (Required)
# ====================
OPENAI_API_KEY=your-openai-api-key

# ====================
# Database Configuration
# ====================
# For local Docker setup:
# DATABASE_URL=postgresql://jean_memory:memory_password@localhost:5432/jean_memory_db

# For Supabase (auto-generated from SUPABASE_URL and SUPABASE_SERVICE_KEY):
DATABASE_URL=postgresql://postgres:YOUR_SUPABASE_SERVICE_KEY@db.YOUR_PROJECT_ID.supabase.co:5432/postgres

# ====================
# Local Development Configuration
# ====================
# Uncomment for local development without Supabase auth:
# USER_ID=default_user
EOL
    echo "✅ Created .env.template"
else
    echo "✅ .env.template already exists"
fi

# 2. Fix the API .env.example to include USER_ID for local dev
if [ -f "${BASE_DIR}/openmemory/api/.env.example" ]; then
    echo "📝 Updating API .env.example with local dev settings..."
    
    # Check if USER_ID is already in the file
    if ! grep -q "USER_ID=" "${BASE_DIR}/openmemory/api/.env.example"; then
        echo "" >> "${BASE_DIR}/openmemory/api/.env.example"
        echo "# Local Development Settings" >> "${BASE_DIR}/openmemory/api/.env.example"
        echo "# Uncomment the following line for local development without Supabase auth:" >> "${BASE_DIR}/openmemory/api/.env.example"
        echo "# USER_ID=default_user" >> "${BASE_DIR}/openmemory/api/.env.example"
        echo "✅ Added USER_ID to API .env.example"
    else
        echo "✅ USER_ID already in API .env.example"
    fi
fi

# 3. Create a proper local development .env if it doesn't exist
if [ ! -f "${BASE_DIR}/.env" ] || [ ! -s "${BASE_DIR}/.env" ]; then
    echo "📝 Creating local development .env file..."
    cat > "${BASE_DIR}/.env" << 'EOL'
# Jean Memory Local Development Configuration

# ====================
# Local Database Configuration
# ====================
DATABASE_URL=postgresql://jean_memory:memory_password@localhost:5432/jean_memory_db

# ====================
# Local Qdrant Configuration
# ====================
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=
MAIN_QDRANT_COLLECTION_NAME=jonathans_memory_main

# ====================
# OpenAI Configuration (Required)
# ====================
OPENAI_API_KEY=your-openai-api-key-here

# ====================
# Local Development Auth
# ====================
USER_ID=default_user

# ====================
# Placeholder Supabase Config (for compatibility)
# ====================
SUPABASE_URL=http://localhost:8000
SUPABASE_ANON_KEY=local-dev-anon-key
SUPABASE_SERVICE_KEY=local-dev-service-key
EOL
    echo "✅ Created local development .env file"
    echo "⚠️  Please edit ${BASE_DIR}/.env and add your OpenAI API key"
else
    echo "✅ .env file already exists"
fi

# 4. Create database initialization script
echo "📝 Creating database initialization script..."
cat > "${BASE_DIR}/init-local-db.sql" << 'EOL'
-- Jean Memory Local Database Initialization Script

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create alembic version table
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Insert initial version if not exists
INSERT INTO alembic_version (version_num) 
SELECT 'initial' 
WHERE NOT EXISTS (SELECT 1 FROM alembic_version WHERE version_num = 'initial');

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR NOT NULL UNIQUE,
    name VARCHAR,
    email VARCHAR UNIQUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create apps table
CREATE TABLE IF NOT EXISTS apps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES users(id),
    name VARCHAR NOT NULL,
    description VARCHAR,
    metadata JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_app_name UNIQUE (owner_id, name)
);

-- Create categories table
CREATE TABLE IF NOT EXISTS categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR UNIQUE NOT NULL,
    description VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create memories table
CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    app_id UUID NOT NULL REFERENCES apps(id),
    content VARCHAR NOT NULL,
    vector VARCHAR,
    metadata JSONB DEFAULT '{}',
    state VARCHAR DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMP WITH TIME ZONE,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Create memory_categories junction table
CREATE TABLE IF NOT EXISTS memory_categories (
    memory_id UUID REFERENCES memories(id),
    category_id UUID REFERENCES categories(id),
    PRIMARY KEY (memory_id, category_id)
);

-- Create documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    app_id UUID NOT NULL REFERENCES apps(id),
    title VARCHAR NOT NULL,
    source_url VARCHAR,
    document_type VARCHAR NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create document_chunks table
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding FLOAT[],
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create document_memories junction table
CREATE TABLE IF NOT EXISTS document_memories (
    document_id UUID REFERENCES documents(id),
    memory_id UUID REFERENCES memories(id),
    PRIMARY KEY (document_id, memory_id)
);

-- Create access_controls table
CREATE TABLE IF NOT EXISTS access_controls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject_type VARCHAR NOT NULL,
    subject_id UUID,
    object_type VARCHAR NOT NULL,
    object_id UUID,
    effect VARCHAR NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create archive_policies table
CREATE TABLE IF NOT EXISTS archive_policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    criteria_type VARCHAR NOT NULL,
    criteria_id UUID,
    days_to_archive INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create memory_status_history table
CREATE TABLE IF NOT EXISTS memory_status_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    memory_id UUID NOT NULL REFERENCES memories(id),
    changed_by UUID NOT NULL REFERENCES users(id),
    old_state VARCHAR NOT NULL,
    new_state VARCHAR NOT NULL,
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create memory_access_logs table
CREATE TABLE IF NOT EXISTS memory_access_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    memory_id UUID NOT NULL REFERENCES memories(id),
    app_id UUID NOT NULL REFERENCES apps(id),
    accessed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    access_type VARCHAR NOT NULL,
    metadata JSONB DEFAULT '{}'
);

-- Create default user and app for local development
INSERT INTO users (user_id, name, email) 
VALUES ('default_user', 'Local Developer', 'local@example.com')
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO apps (owner_id, name, description, is_active)
SELECT id, 'default', 'Default app for local development', true
FROM users WHERE user_id = 'default_user'
ON CONFLICT DO NOTHING;

-- Create all necessary indexes
CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
CREATE INDEX IF NOT EXISTS idx_apps_owner_id ON apps(owner_id);
CREATE INDEX IF NOT EXISTS idx_apps_is_active ON apps(is_active);
CREATE INDEX IF NOT EXISTS idx_categories_name ON categories(name);
CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id);
CREATE INDEX IF NOT EXISTS idx_memories_app_id ON memories(app_id);
CREATE INDEX IF NOT EXISTS idx_memories_state ON memories(state);
CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at);
CREATE INDEX IF NOT EXISTS idx_memory_user_state ON memories(user_id, state);
CREATE INDEX IF NOT EXISTS idx_memory_app_state ON memories(app_id, state);
CREATE INDEX IF NOT EXISTS idx_memory_user_app ON memories(user_id, app_id);
CREATE INDEX IF NOT EXISTS idx_memory_category ON memory_categories(memory_id, category_id);
CREATE INDEX IF NOT EXISTS idx_document_memory ON document_memories(document_id, memory_id);
CREATE INDEX IF NOT EXISTS idx_access_subject ON access_controls(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_access_object ON access_controls(object_type, object_id);
CREATE INDEX IF NOT EXISTS idx_policy_criteria ON archive_policies(criteria_type, criteria_id);
CREATE INDEX IF NOT EXISTS idx_history_memory_state ON memory_status_history(memory_id, new_state);
CREATE INDEX IF NOT EXISTS idx_history_user_time ON memory_status_history(changed_by, changed_at);
CREATE INDEX IF NOT EXISTS idx_access_memory_time ON memory_access_logs(memory_id, accessed_at);
CREATE INDEX IF NOT EXISTS idx_access_app_time ON memory_access_logs(app_id, accessed_at);
EOL
echo "✅ Created database initialization script"

# 5. Create a helper script to initialize the local database
echo "📝 Creating database initialization helper..."
cat > "${BASE_DIR}/init-local-database.sh" << 'EOL'
#!/bin/bash
# Initialize the local PostgreSQL database for Jean Memory

echo "🗄️ Initializing local database..."

# Wait for PostgreSQL to be ready
max_retries=30
retry_count=0

while [ $retry_count -lt $max_retries ]; do
    if docker exec jeanmemory_postgres_service pg_isready -U jean_memory -d jean_memory_db > /dev/null 2>&1; then
        echo "✅ PostgreSQL is ready!"
        break
    fi
    echo "Waiting for PostgreSQL... ($((retry_count + 1))/$max_retries)"
    sleep 2
    retry_count=$((retry_count + 1))
done

if [ $retry_count -eq $max_retries ]; then
    echo "❌ PostgreSQL did not become ready in time"
    exit 1
fi

# Run the initialization SQL
echo "Running database initialization..."
docker exec -i jeanmemory_postgres_service psql -U jean_memory -d jean_memory_db < init-local-db.sql

if [ $? -eq 0 ]; then
    echo "✅ Database initialized successfully!"
else
    echo "❌ Database initialization failed"
    exit 1
fi
EOL
chmod +x "${BASE_DIR}/init-local-database.sh"
echo "✅ Created database initialization helper"

echo ""
echo "🎉 Fix script completed!"
echo ""
echo "Next steps:"
echo "1. Edit ${BASE_DIR}/.env and add your OpenAI API key"
echo "2. Run: ./setup-local-dev.sh --fresh"
echo "3. After Docker starts, run: ./init-local-database.sh"
echo "4. Then run: ./setup-local-dev.sh (without --fresh) to complete setup"
echo ""
echo "For hybrid setup with Supabase:"
echo "1. Copy .env.template to .env"
echo "2. Fill in your Supabase and Qdrant Cloud credentials"
echo "3. Run: ./jean-memory.sh setup" 