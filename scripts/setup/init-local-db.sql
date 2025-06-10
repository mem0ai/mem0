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
