-- Enhanced database schema for CAG document processing
-- Includes additional columns for document metadata, tracking, and processing status

-- Documents table - track overall document info
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) UNIQUE NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path TEXT,
    document_title VARCHAR(255),
    document_type VARCHAR(50),
    content_hash VARCHAR(64),
    page_count INTEGER,
    author VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    processed_at TIMESTAMP,
    total_chunks INTEGER,
    status VARCHAR(50) NOT NULL DEFAULT 'new',
    error_message TEXT
);

-- Enhanced document chunks/registry table
CREATE TABLE IF NOT EXISTS cag_document_registry (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL,
    chunk_id VARCHAR(255) UNIQUE NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    section_title VARCHAR(255),
    chunk_index INTEGER NOT NULL,
    total_chunks INTEGER NOT NULL,
    chunk_size_chars INTEGER,
    estimated_tokens INTEGER,
    content_hash VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMP,
    kv_cache_path TEXT,
    context_size INTEGER,
    cag_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    last_used TIMESTAMP,
    usage_count INTEGER DEFAULT 0,
    processing_meta JSONB,
    document_title VARCHAR(255),
    
    -- Add foreign key reference to documents table
    CONSTRAINT fk_document FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_document_registry_document_id ON cag_document_registry(document_id);
CREATE INDEX IF NOT EXISTS idx_document_registry_status ON cag_document_registry(cag_status);
CREATE INDEX IF NOT EXISTS idx_document_registry_last_used ON cag_document_registry(last_used);
CREATE INDEX IF NOT EXISTS idx_document_registry_content_hash ON cag_document_registry(content_hash);

-- Enhanced query log table
CREATE TABLE IF NOT EXISTS query_log (
    id SERIAL PRIMARY KEY,
    query_id VARCHAR(255) UNIQUE NOT NULL,
    query_text TEXT NOT NULL,
    response_text TEXT,
    query_type VARCHAR(50),
    document_sources TEXT[],
    document_ids TEXT[],
    chunks_used TEXT[],
    processed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    processing_time INTEGER,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    user_feedback VARCHAR(50),
    metadata JSONB
);

-- Create index for query performance
CREATE INDEX IF NOT EXISTS idx_query_log_processed_at ON query_log(processed_at);
CREATE INDEX IF NOT EXISTS idx_query_log_document_ids ON query_log USING GIN(document_ids);

-- Document processing error log
CREATE TABLE IF NOT EXISTS processing_errors (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255),
    chunk_id VARCHAR(255),
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    occurred_at TIMESTAMP NOT NULL DEFAULT NOW(),
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP,
    resolution_notes TEXT
);

-- Create index for error tracking
CREATE INDEX IF NOT EXISTS idx_processing_errors_document_id ON processing_errors(document_id);
CREATE INDEX IF NOT EXISTS idx_processing_errors_resolved ON processing_errors(resolved);

-- Processing statistics table for monitoring
CREATE TABLE IF NOT EXISTS processing_stats (
    id SERIAL PRIMARY KEY,
    record_date DATE NOT NULL DEFAULT CURRENT_DATE,
    documents_processed INTEGER DEFAULT 0,
    chunks_processed INTEGER DEFAULT 0,
    documents_failed INTEGER DEFAULT 0,
    chunks_failed INTEGER DEFAULT 0,
    avg_processing_time_ms INTEGER,
    total_cache_size_bytes BIGINT,
    metadata JSONB
);

-- Create unique index on date for stats
CREATE UNIQUE INDEX IF NOT EXISTS idx_processing_stats_date ON processing_stats(record_date);

-- Update function for tracking usage of KV caches
CREATE OR REPLACE FUNCTION update_kv_cache_usage() 
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_used = NOW();
    NEW.usage_count = OLD.usage_count + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for updating usage statistics
DROP TRIGGER IF EXISTS trg_update_kv_cache_usage ON cag_document_registry;
CREATE TRIGGER trg_update_kv_cache_usage
BEFORE UPDATE ON cag_document_registry
FOR EACH ROW
WHEN (NEW.cag_status = 'cached' AND OLD.cag_status = 'cached' AND OLD.last_used IS NOT NULL)
EXECUTE FUNCTION update_kv_cache_usage();

-- Function to log processing errors
CREATE OR REPLACE FUNCTION log_processing_error(
    doc_id VARCHAR(255),
    chk_id VARCHAR(255),
    err_type VARCHAR(100),
    err_message TEXT,
    stack TEXT DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO processing_errors (document_id, chunk_id, error_type, error_message, stack_trace)
    VALUES (doc_id, chk_id, err_type, err_message, stack);
END;
$$ LANGUAGE plpgsql;

-- Function to update document status based on chunk status
CREATE OR REPLACE FUNCTION update_document_status() 
RETURNS TRIGGER AS $$
DECLARE
    total_chunks INTEGER;
    completed_chunks INTEGER;
    failed_chunks INTEGER;
    doc_status VARCHAR(50);
BEGIN
    -- Get counts
    SELECT 
        COUNT(*), 
        COUNT(*) FILTER (WHERE cag_status = 'cached'),
        COUNT(*) FILTER (WHERE cag_status = 'failed')
    INTO total_chunks, completed_chunks, failed_chunks
    FROM cag_document_registry
    WHERE document_id = NEW.document_id;
    
    -- Determine document status
    IF failed_chunks > 0 AND completed_chunks = 0 THEN
        doc_status := 'failed';
    ELSIF completed_chunks = total_chunks THEN
        doc_status := 'cached';
    ELSIF completed_chunks > 0 THEN
        doc_status := 'partially_cached';
    ELSE
        doc_status := 'processing';
    END IF;
    
    -- Update document status
    UPDATE documents
    SET status = doc_status,
        processed_at = NOW(),
        total_chunks = total_chunks,
        updated_at = NOW()
    WHERE document_id = NEW.document_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for updating document status
DROP TRIGGER IF EXISTS trg_update_document_status ON cag_document_registry;
CREATE TRIGGER trg_update_document_status
AFTER UPDATE OF cag_status ON cag_document_registry
FOR EACH ROW
WHEN (NEW.cag_status IN ('cached', 'failed') AND OLD.cag_status = 'pending')
EXECUTE FUNCTION update_document_status();

-- Comments for implementers
COMMENT ON TABLE documents IS 'Main document metadata table tracking overall document information';
COMMENT ON TABLE cag_document_registry IS 'Registry of document chunks with KV cache paths and processing status';
COMMENT ON TABLE query_log IS 'Log of all queries processed by the CAG system';
COMMENT ON TABLE processing_errors IS 'Detailed log of processing errors for debugging and monitoring';
COMMENT ON TABLE processing_stats IS 'Daily statistics for system monitoring and performance tracking';