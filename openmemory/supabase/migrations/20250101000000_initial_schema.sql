-- OpenMemory Initial Schema
-- Converted from Alembic migrations to Supabase format

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_vector extension for document chunks embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Create enums
CREATE TYPE memory_state AS ENUM ('active', 'paused', 'archived', 'deleted');

-- =====================================================
-- Core Tables
-- =====================================================

-- Users table (integrates with Supabase Auth)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL UNIQUE, -- Maps to Supabase auth.users.id
    name TEXT,
    email TEXT UNIQUE,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX ix_users_created_at ON users(created_at);
CREATE INDEX ix_users_email ON users(email);
CREATE INDEX ix_users_name ON users(name);
CREATE INDEX ix_users_user_id ON users(user_id);

-- Apps table
CREATE TABLE apps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT,
    metadata JSONB,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes and constraints
CREATE INDEX ix_apps_created_at ON apps(created_at);
CREATE INDEX ix_apps_is_active ON apps(is_active);
CREATE INDEX ix_apps_name ON apps(name);  
CREATE INDEX ix_apps_owner_id ON apps(owner_id);
-- Add unique constraint for owner_id + app_name combination
CREATE UNIQUE INDEX unique_owner_app_name ON apps(owner_id, name);

-- Documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    app_id UUID NOT NULL REFERENCES apps(id),
    title TEXT NOT NULL,
    source_url TEXT,
    document_type TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_documents_created ON documents(created_at);
CREATE INDEX idx_documents_type ON documents(document_type);
CREATE INDEX idx_documents_user_app ON documents(user_id, app_id);
CREATE INDEX ix_documents_app_id ON documents(app_id);
CREATE INDEX ix_documents_created_at ON documents(created_at);
CREATE INDEX ix_documents_user_id ON documents(user_id);

-- Document chunks table for efficient retrieval
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536), -- OpenAI text-embedding-3-small dimension
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for efficient retrieval
CREATE INDEX idx_document_chunks_document_id ON document_chunks(document_id);
CREATE INDEX idx_document_chunks_chunk_index ON document_chunks(chunk_index);

-- Memories table
CREATE TABLE memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    app_id UUID NOT NULL REFERENCES apps(id),
    content TEXT NOT NULL,
    vector TEXT, -- Stored as string for Qdrant compatibility
    metadata JSONB,
    state memory_state DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    archived_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ
);

-- Create indexes
CREATE INDEX idx_memory_app_state ON memories(app_id, state);
CREATE INDEX idx_memory_user_app ON memories(user_id, app_id);
CREATE INDEX idx_memory_user_state ON memories(user_id, state);
CREATE INDEX ix_memories_app_id ON memories(app_id);
CREATE INDEX ix_memories_archived_at ON memories(archived_at);
CREATE INDEX ix_memories_created_at ON memories(created_at);
CREATE INDEX ix_memories_deleted_at ON memories(deleted_at);
CREATE INDEX ix_memories_state ON memories(state);
CREATE INDEX ix_memories_user_id ON memories(user_id);

-- =====================================================
-- Association Tables
-- =====================================================

-- Document-memory associations
CREATE TABLE document_memories (
    document_id UUID NOT NULL REFERENCES documents(id),
    memory_id UUID NOT NULL REFERENCES memories(id),
    PRIMARY KEY (document_id, memory_id)
);

-- Create indexes
CREATE INDEX idx_document_memory ON document_memories(document_id, memory_id);
CREATE INDEX ix_document_memories_document_id ON document_memories(document_id);
CREATE INDEX ix_document_memories_memory_id ON document_memories(memory_id);

-- =====================================================
-- Supporting Tables
-- =====================================================

-- Categories table
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX ix_categories_created_at ON categories(created_at);
CREATE INDEX ix_categories_name ON categories(name);

-- Memory categories association
CREATE TABLE memory_categories (
    memory_id UUID NOT NULL REFERENCES memories(id),
    category_id UUID NOT NULL REFERENCES categories(id),
    PRIMARY KEY (memory_id, category_id)
);

-- Create indexes
CREATE INDEX idx_memory_category ON memory_categories(memory_id, category_id);
CREATE INDEX ix_memory_categories_category_id ON memory_categories(category_id);
CREATE INDEX ix_memory_categories_memory_id ON memory_categories(memory_id);

-- Access controls table
CREATE TABLE access_controls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject_type TEXT NOT NULL,
    subject_id UUID,
    object_type TEXT NOT NULL,
    object_id UUID,
    effect TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_access_object ON access_controls(object_type, object_id);
CREATE INDEX idx_access_subject ON access_controls(subject_type, subject_id);
CREATE INDEX ix_access_controls_created_at ON access_controls(created_at);
CREATE INDEX ix_access_controls_effect ON access_controls(effect);
CREATE INDEX ix_access_controls_object_id ON access_controls(object_id);
CREATE INDEX ix_access_controls_object_type ON access_controls(object_type);
CREATE INDEX ix_access_controls_subject_id ON access_controls(subject_id);
CREATE INDEX ix_access_controls_subject_type ON access_controls(subject_type);

-- Memory access logs table
CREATE TABLE memory_access_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    memory_id UUID NOT NULL REFERENCES memories(id),
    app_id UUID NOT NULL REFERENCES apps(id),
    accessed_at TIMESTAMPTZ DEFAULT NOW(),
    access_type TEXT NOT NULL,
    metadata JSONB
);

-- Create indexes
CREATE INDEX idx_access_app_time ON memory_access_logs(app_id, accessed_at);
CREATE INDEX idx_access_memory_time ON memory_access_logs(memory_id, accessed_at);
CREATE INDEX ix_memory_access_logs_access_type ON memory_access_logs(access_type);
CREATE INDEX ix_memory_access_logs_accessed_at ON memory_access_logs(accessed_at);
CREATE INDEX ix_memory_access_logs_app_id ON memory_access_logs(app_id);
CREATE INDEX ix_memory_access_logs_memory_id ON memory_access_logs(memory_id);

-- Memory status history table
CREATE TABLE memory_status_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    memory_id UUID NOT NULL REFERENCES memories(id),
    changed_by UUID NOT NULL REFERENCES users(id),
    old_state memory_state NOT NULL,
    new_state memory_state NOT NULL,
    changed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_history_memory_state ON memory_status_history(memory_id, new_state);
CREATE INDEX idx_history_user_time ON memory_status_history(changed_by, changed_at);
CREATE INDEX ix_memory_status_history_changed_at ON memory_status_history(changed_at);
CREATE INDEX ix_memory_status_history_changed_by ON memory_status_history(changed_by);
CREATE INDEX ix_memory_status_history_memory_id ON memory_status_history(memory_id);
CREATE INDEX ix_memory_status_history_new_state ON memory_status_history(new_state);
CREATE INDEX ix_memory_status_history_old_state ON memory_status_history(old_state);

-- Archive policies table
CREATE TABLE archive_policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    criteria_type TEXT NOT NULL,
    criteria_id UUID,
    days_to_archive INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_policy_criteria ON archive_policies(criteria_type, criteria_id);
CREATE INDEX ix_archive_policies_created_at ON archive_policies(created_at);
CREATE INDEX ix_archive_policies_criteria_id ON archive_policies(criteria_id);
CREATE INDEX ix_archive_policies_criteria_type ON archive_policies(criteria_type);

-- =====================================================
-- Row Level Security (RLS) Policies
-- =====================================================

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE apps ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE access_controls ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_access_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_status_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE archive_policies ENABLE ROW LEVEL SECURITY;

-- Users can only access their own data
CREATE POLICY "Users can view own data" ON users FOR SELECT USING (auth.uid()::text = user_id);
CREATE POLICY "Users can update own data" ON users FOR UPDATE USING (auth.uid()::text = user_id);

-- Apps policies
CREATE POLICY "Users can view own apps" ON apps FOR SELECT USING (owner_id IN (SELECT id FROM users WHERE user_id = auth.uid()::text));
CREATE POLICY "Users can create own apps" ON apps FOR INSERT WITH CHECK (owner_id IN (SELECT id FROM users WHERE user_id = auth.uid()::text));
CREATE POLICY "Users can update own apps" ON apps FOR UPDATE USING (owner_id IN (SELECT id FROM users WHERE user_id = auth.uid()::text));
CREATE POLICY "Users can delete own apps" ON apps FOR DELETE USING (owner_id IN (SELECT id FROM users WHERE user_id = auth.uid()::text));

-- Documents policies
CREATE POLICY "Users can view own documents" ON documents FOR SELECT USING (user_id IN (SELECT id FROM users WHERE user_id = auth.uid()::text));
CREATE POLICY "Users can create own documents" ON documents FOR INSERT WITH CHECK (user_id IN (SELECT id FROM users WHERE user_id = auth.uid()::text));
CREATE POLICY "Users can update own documents" ON documents FOR UPDATE USING (user_id IN (SELECT id FROM users WHERE user_id = auth.uid()::text));
CREATE POLICY "Users can delete own documents" ON documents FOR DELETE USING (user_id IN (SELECT id FROM users WHERE user_id = auth.uid()::text));

-- Document chunks policies
CREATE POLICY "Users can view own document chunks" ON document_chunks FOR SELECT USING (document_id IN (SELECT id FROM documents WHERE user_id IN (SELECT id FROM users WHERE user_id = auth.uid()::text)));
CREATE POLICY "Users can create own document chunks" ON document_chunks FOR INSERT WITH CHECK (document_id IN (SELECT id FROM documents WHERE user_id IN (SELECT id FROM users WHERE user_id = auth.uid()::text)));
CREATE POLICY "Users can update own document chunks" ON document_chunks FOR UPDATE USING (document_id IN (SELECT id FROM documents WHERE user_id IN (SELECT id FROM users WHERE user_id = auth.uid()::text)));
CREATE POLICY "Users can delete own document chunks" ON document_chunks FOR DELETE USING (document_id IN (SELECT id FROM documents WHERE user_id IN (SELECT id FROM users WHERE user_id = auth.uid()::text)));

-- Memories policies
CREATE POLICY "Users can view own memories" ON memories FOR SELECT USING (user_id IN (SELECT id FROM users WHERE user_id = auth.uid()::text));
CREATE POLICY "Users can create own memories" ON memories FOR INSERT WITH CHECK (user_id IN (SELECT id FROM users WHERE user_id = auth.uid()::text));
CREATE POLICY "Users can update own memories" ON memories FOR UPDATE USING (user_id IN (SELECT id FROM users WHERE user_id = auth.uid()::text));
CREATE POLICY "Users can delete own memories" ON memories FOR DELETE USING (user_id IN (SELECT id FROM users WHERE user_id = auth.uid()::text));

-- =====================================================
-- Functions and Triggers
-- =====================================================

-- Function to automatically update updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
CREATE TRIGGER update_apps_updated_at BEFORE UPDATE ON apps FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
CREATE TRIGGER update_memories_updated_at BEFORE UPDATE ON memories FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
CREATE TRIGGER update_categories_updated_at BEFORE UPDATE ON categories FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- =====================================================
-- Comments for Documentation
-- =====================================================

COMMENT ON TABLE users IS 'User accounts linked to Supabase Auth';
COMMENT ON TABLE apps IS 'Application instances owned by users';
COMMENT ON TABLE documents IS 'Full document content storage';
COMMENT ON TABLE document_chunks IS 'Document chunks with embeddings for retrieval';
COMMENT ON TABLE memories IS 'Individual memory entries with vector references';
COMMENT ON TABLE document_memories IS 'Association between documents and generated memories';
COMMENT ON TABLE categories IS 'Memory categorization system';
COMMENT ON TABLE memory_categories IS 'Memory-category associations';
COMMENT ON TABLE access_controls IS 'Fine-grained access control system';
COMMENT ON TABLE memory_access_logs IS 'Audit log for memory access';
COMMENT ON TABLE memory_status_history IS 'History of memory state changes';
COMMENT ON TABLE archive_policies IS 'Automated archiving rules'; 