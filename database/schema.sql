-- Schema for the CAG/RAG system

-- Document registry for CAG documents
CREATE TABLE IF NOT EXISTS cag_document_registry (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL,
    chunk_id VARCHAR(255) UNIQUE NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    section_title TEXT,
    chunk_index INTEGER NOT NULL,
    total_chunks INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL,
    processed_at TIMESTAMP,
    cag_status VARCHAR(50) DEFAULT 'pending', -- pending, cached, failed
    error_message TEXT,
    kv_cache_path TEXT,
    chunk_summary TEXT,
    page_number INTEGER,
    last_used TIMESTAMP,
    usage_count INTEGER DEFAULT 0
);

-- Store document analysis results
CREATE TABLE IF NOT EXISTS document_analysis (
    id SERIAL PRIMARY KEY,
    chunk_id VARCHAR(255) UNIQUE NOT NULL,
    document_id VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    analysis TEXT NOT NULL,
    processed_at TIMESTAMP NOT NULL,
    needs_ocr BOOLEAN DEFAULT FALSE,
    ocr_processed BOOLEAN DEFAULT FALSE,
    summarized BOOLEAN DEFAULT FALSE,
    document_summary TEXT
);

-- Log document processing errors
CREATE TABLE IF NOT EXISTS processing_errors (
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    error_message TEXT NOT NULL,
    error_step VARCHAR(100) NOT NULL,
    error_type VARCHAR(50),
    processing_path VARCHAR(100),
    timestamp TIMESTAMP NOT NULL
);

-- Log user queries and responses
CREATE TABLE IF NOT EXISTS query_log (
    id SERIAL PRIMARY KEY,
    query_id VARCHAR(255) UNIQUE NOT NULL,
    query_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    query_type VARCHAR(50) NOT NULL, -- cag, rag
    document_sources JSONB, -- Array of document sources used
    processed_at TIMESTAMP NOT NULL,
    processing_time INTEGER NOT NULL -- in milliseconds
);

-- Store detailed query classification information
CREATE TABLE IF NOT EXISTS query_classification_details (
    id SERIAL PRIMARY KEY,
    query_id VARCHAR(255) NOT NULL REFERENCES query_log(query_id),
    classification_type VARCHAR(50) NOT NULL, -- cag, rag
    classification_reason TEXT,
    confidence VARCHAR(50), -- high, medium, low, very low
    was_fallback BOOLEAN DEFAULT FALSE,
    original_classification VARCHAR(50)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_cag_document_registry_document_id ON cag_document_registry(document_id);
CREATE INDEX IF NOT EXISTS idx_cag_document_registry_status ON cag_document_registry(cag_status);
CREATE INDEX IF NOT EXISTS idx_document_analysis_document_id ON document_analysis(document_id);
CREATE INDEX IF NOT EXISTS idx_query_log_query_type ON query_log(query_type);
CREATE INDEX IF NOT EXISTS idx_query_log_processed_at ON query_log(processed_at);