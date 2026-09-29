-- =========================================================================
-- College AI Chatbot - Supabase Database & pgvector Setup Script
-- Run this entire script in the Supabase Dashboard -> SQL Editor
-- =========================================================================

-- 1. Enable the pgvector extension for high-performance vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create the college_documents table to store verified campus knowledge
CREATE TABLE IF NOT EXISTS college_documents (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    keywords TEXT[] DEFAULT '{}',
    embedding VECTOR(768), -- 768 dimensions for Google text-embedding-004 / 1536 for OpenAI text-embedding-3-small
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- 3. Create index for fast vector cosine similarity search (HNSW or IVFFlat)
CREATE INDEX IF NOT EXISTS college_documents_embedding_idx 
ON college_documents 
USING hnsw (embedding vector_cosine_ops);

-- 4. Create chat_logs table to store student queries, AI answers, and feedback
CREATE TABLE IF NOT EXISTS chat_logs (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT,
    user_query TEXT NOT NULL,
    bot_response TEXT NOT NULL,
    category TEXT,
    sources JSONB DEFAULT '[]'::jsonb,
    feedback INT DEFAULT 0, -- 1 for thumbs up, -1 for thumbs down, 0 neutral
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- 5. Stored Procedure for Semantic Vector Search with Category Filtering
CREATE OR REPLACE FUNCTION match_documents (
    query_embedding VECTOR(768),
    match_threshold FLOAT DEFAULT 0.25,
    match_count INT DEFAULT 4,
    filter_category TEXT DEFAULT NULL
)
RETURNS TABLE (
    id TEXT,
    category TEXT,
    title TEXT,
    content TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        cd.id,
        cd.category,
        cd.title,
        cd.content,
        1 - (cd.embedding <=> query_embedding) AS similarity
    FROM college_documents cd
    WHERE 
        (filter_category IS NULL OR filter_category = '' OR cd.category = filter_category)
        AND (1 - (cd.embedding <=> query_embedding)) > match_threshold
    ORDER BY cd.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- 6. Enable Row Level Security (RLS) policies (Optional / Public read for student bot)
ALTER TABLE college_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_logs ENABLE ROW LEVEL SECURITY;

-- Allow public read access to documents
CREATE POLICY IF NOT EXISTS "Allow public read access to documents"
ON college_documents FOR SELECT
TO anon, authenticated
USING (true);

-- Allow service role and backend to insert/update documents
CREATE POLICY IF NOT EXISTS "Allow insert to documents"
ON college_documents FOR ALL
TO anon, authenticated
USING (true);

-- Allow insert and read for chat_logs
CREATE POLICY IF NOT EXISTS "Allow read/write chat_logs"
ON chat_logs FOR ALL
TO anon, authenticated
USING (true);
