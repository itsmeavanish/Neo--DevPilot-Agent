-- JARVIS Database Initialization
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Memory items table
CREATE TABLE IF NOT EXISTS memory_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384),
    project_id VARCHAR(255),
    file_path VARCHAR(500),
    language VARCHAR(50),
    tags TEXT[],
    metadata JSONB DEFAULT '{}',
    importance FLOAT DEFAULT 0.5,
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_items(type);
CREATE INDEX IF NOT EXISTS idx_memory_project ON memory_items(project_id);
CREATE INDEX IF NOT EXISTS idx_memory_created ON memory_items(created_at DESC);

-- Vector similarity search index (IVFFlat)
CREATE INDEX IF NOT EXISTS idx_memory_embedding 
ON memory_items USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Command history table
CREATE TABLE IF NOT EXISTS command_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    intent TEXT,
    tool_name VARCHAR(100) NOT NULL,
    tool_params JSONB NOT NULL,
    status VARCHAR(20) NOT NULL,
    output TEXT,
    error TEXT,
    exit_code INTEGER,
    device_id UUID,
    session_id UUID,
    task_id UUID,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cmd_history_tool ON command_history(tool_name);
CREATE INDEX IF NOT EXISTS idx_cmd_history_status ON command_history(status);
CREATE INDEX IF NOT EXISTS idx_cmd_history_created ON command_history(created_at DESC);

-- Project contexts table
CREATE TABLE IF NOT EXISTS project_contexts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_path VARCHAR(500) UNIQUE NOT NULL,
    name VARCHAR(255),
    language VARCHAR(50),
    framework VARCHAR(100),
    package_manager VARCHAR(50),
    file_tree JSONB,
    dependencies JSONB,
    scripts JSONB,
    summary TEXT,
    summary_embedding vector(384),
    scanned_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Semantic search function
CREATE OR REPLACE FUNCTION search_memory(
    query_embedding vector(384),
    match_type VARCHAR DEFAULT NULL,
    match_limit INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    type VARCHAR,
    content TEXT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id,
        m.type,
        m.content,
        1 - (m.embedding <=> query_embedding) AS similarity
    FROM memory_items m
    WHERE m.deleted_at IS NULL
      AND (match_type IS NULL OR m.type = match_type)
      AND m.embedding IS NOT NULL
    ORDER BY m.embedding <=> query_embedding
    LIMIT match_limit;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO jarvis;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO jarvis;
