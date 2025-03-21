# llama-cag-n8n: Comprehensive Project Overview

## Project Purpose

llama-cag-n8n is an implementation of Context-Augmented Generation (CAG) using llama.cpp and n8n. Unlike traditional Retrieval-Augmented Generation (RAG) systems that retrieve and reprocess document chunks for every query, CAG precomputes and caches the internal state of large context window models, enabling faster and more accurate responses without real-time retrieval overhead.

## System Architecture

The system consists of four main components:

1. **llama.cpp**: Local LLM inference engine that handles document processing and query generation
2. **n8n**: Workflow automation platform that orchestrates the document processing and query handling
3. **CAG Bridge**: Python service that connects n8n to llama.cpp scripts
4. **PostgreSQL**: Database for storing metadata (optional, used for advanced tracking)

## Core Components

### 1. llama.cpp Setup

- **Purpose**: Provides efficient LLM inference on consumer hardware
- **Configuration**: Located at `LLAMACPP_PATH` (default: ~/Documents/llama.cpp)
- **Key Scripts**:
  - `query_kv_cache.sh`: Loads a KV cache and answers queries
  - `create_kv_cache.sh`: Processes documents and creates KV caches

### 2. n8n Workflows

- **Document Processing Workflow**: Creates KV caches from documents
  - Reads documents, processes content, and creates KV caches
  - Triggered manually with document path and ID inputs
  
- **Query Workflow**: Handles user queries using KV caches
  - Takes user questions and returns answers based on cached knowledge
  - Uses the CAG Bridge service to communicate with llama.cpp

### 3. CAG Bridge Service

- **Purpose**: Connects n8n to llama.cpp scripts
- **Location**: `bridge/cag_bridge.py`
- **Endpoints**:
  - `/query`: Answers questions using loaded KV caches
  - `/create-cache`: Creates new KV caches from documents
  - `/health`: Reports health status of the system

### 4. Docker Configuration

- **Docker Compose**: Defines all services and their relationships
- **Key Services**:
  - `n8n`: Web interface and workflow engine
  - `db`: PostgreSQL database
  - `cag-bridge`: Connection between n8n and llama.cpp

## Data Flow and Operation

### KV Cache Creation Process:
1. User uploads document via n8n workflow
2. Document is processed to fit within context window
3. Processed document saved to temporary file
4. CAG Bridge calls llama.cpp to create KV cache
5. KV cache stored on disk for future queries

### Query Process:
1. User sends question via API endpoint
2. Query workflow receives question
3. CAG Bridge loads appropriate KV cache
4. llama.cpp generates answer based on cached context
5. Response returned to user

## Configuration

### Key Environment Variables:

- **llama.cpp Configuration**:
  - `LLAMACPP_PATH`: Path to llama.cpp installation
  - `LLAMACPP_MODEL_PATH`: Path to the model file
  - `LLAMACPP_KV_CACHE_DIR`: Directory for storing KV caches
  - `LLAMACPP_MAX_CONTEXT`: Maximum context size (default: 128000)

- **System Configuration**:
  - `N8N_PORT`: Port for n8n interface (default: 5678)
  - `CAG_BRIDGE_PORT`: Port for bridge service (default: 8000)
  - `DB_PASSWORD`: Database password

### Files and Directories:

- `/data/kv_caches`: KV cache storage (inside Docker)
- `/data/temp_chunks`: Temporary files during processing
- `/data/documents`: Document storage location

## Dependencies

1. **System Requirements**:
   - Docker & Docker Compose
   - Python 3.8+
   - 16GB+ RAM recommended (for 128K context models)
   - Git

2. **Software Dependencies**:
   - llama.cpp (compiled from source)
   - Large context window LLM model (e.g., Gemma-4B)
   - Docker images:
     - n8nio/n8n
     - postgres:14
     - python:3.9 (for bridge)

## Critical Files

- **Scripts**:
  - `scripts/bash/create_kv_cache.sh`: Creates KV caches
  - `scripts/bash/query_kv_cache.sh`: Queries using KV caches
  - `scripts/bash/install_llamacpp.sh`: Installs llama.cpp

- **Configuration**:
  - `.env`: Environment variables
  - `docker-compose.yml`: Docker service configuration

- **Bridge**:
  - `bridge/cag_bridge.py`: Python service connecting n8n to llama.cpp

- **Workflows**:
  - `n8n/workflows/`: Contains n8n workflow definitions

## Operation Guide

### Creating KV Caches:
1. Import the Document Processing workflow
2. Run with Manual Trigger
3. Provide document path and document ID
4. View results to confirm successful KV cache creation

### Querying with CAG:
1. Send HTTP request to the query endpoint:
   ```
   curl -X POST http://localhost:5678/webhook/cag/query \
     -H "Content-Type: application/json" \
     -d '{"query": "Your question here?"}'
   ```
2. Response will be generated based on the cached knowledge

### Master KV Cache Approach:
- Process key documents into a single "master_document" KV cache
- All queries will use this unified knowledge base
- Updates require reprocessing and recreating the master cache

## Troubleshooting

### Common Issues:

1. **Memory Issues**:
   - **Symptoms**: OOM errors, system crashes
   - **Solution**: Reduce LLAMACPP_MAX_CONTEXT, use more quantized models

2. **KV Cache Problems**:
   - **Symptoms**: "File not found" errors, query failures
   - **Check**: Bridge health endpoint (`http://localhost:8000/health`)
   - **Solution**: Verify cache paths, reprocess documents

3. **Performance Issues**:
   - **Symptoms**: Slow processing, timeouts
   - **Solution**: Adjust LLAMACPP_THREADS, use GPU if available

4. **Workflow Connection Errors**:
   - **Symptoms**: n8n nodes not connecting, execution failures
   - **Solution**: Ensure proper node connections, check logs

### Diagnostic Commands:

```bash
# Check bridge logs
docker logs llamacag-bridge

# Check bridge health
curl http://localhost:8000/health

# Check n8n logs
docker logs llamacag-n8n

# List KV caches
ls -lah ~/cag_project/kv_caches/
```

## Directory Structure

```
llama-cag-n8n/
├── .env.example               # Template for environment variables
├── .env                       # Your environment configuration
├── bridge/                    # CAG bridge service
│   └── cag_bridge.py          # Python bridge between n8n and llama.cpp
├── database/
│   └── schema.sql             # Database schema for CAG system (optional)
├── docker-compose.yml         # Docker configuration
├── docs/
│   └── images/                # Documentation images
├── n8n/
│   └── workflows/             # n8n workflow definitions
├── scripts/
│   ├── bash/                  # Bash scripts for llama.cpp operations
│   │   ├── create_kv_cache.sh # Creates KV caches from documents
│   │   ├── query_kv_cache.sh  # Queries using KV caches
│   │   └── install_llamacpp.sh# Installs llama.cpp
│   └── python/                # Python utility scripts
├── setup.py                   # Installation script
└── start_services.py          # Service management script
```

## Technical Concepts

### KV Cache Explained:
- **What it is**: Key-Value cache of the model's internal state after processing a document
- **How it works**: Stores the attention patterns and internal representations
- **Benefits**: Allows the model to "remember" document content without reprocessing
- **Limitations**: Memory intensive, session-specific to the model

### CAG vs RAG:
- **RAG** (Retrieval-Augmented Generation):
  - Retrieves relevant chunks for each query
  - Reprocesses documents every time
  - More flexible but slower and potentially less accurate

- **CAG** (Context-Augmented Generation):
  - Precomputes and caches document processing
  - Loads cached state for queries
  - Faster responses with more consistent context awareness
  - Limited to documents that fit in the model's context window

---

This comprehensive overview should provide everything needed to understand the system architecture, components, and operation. For future iterations, this can serve as a complete map of the project structure and functionality.