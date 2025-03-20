# llama-cag-n8n

WORK IN PROGRESS

A comprehensive implementation of Context-Augmented Generation (CAG) using llama.cpp and n8n, designed to leverage large context window models (128K+ tokens) for storing and querying entire documents.

## What is llama-cag-n8n?

This package provides a complete implementation of Context-Augmented Generation (CAG) using llama.cpp and n8n. Unlike traditional RAG systems that need to retrieve and reprocess document chunks for every query, CAG precomputes and stores Key-Value (KV) caches for entire large documents, offering:

- ✅ **Process massive documents** - Handle documents up to 128K tokens with large context window models
- ✅ **Faster responses** - No need to reprocess documents for each query
- ✅ **More accurate answers** - Direct access to the entire document context
- ✅ **Lower resource usage** - Only processes documents once
- ✅ **Works offline** - No need for external APIs
- ✅ **Mac compatible** - Optimized for Apple Silicon and Intel Macs

## Limitations

-PLACEHOLDER WORKFLOWS - RAG branch can be pulled as a template / actual Workflows need WORK
-TESTING REQUIRED

## Quick Start

### Step 1: Clone the repository

```bash
git clone https://github.com/username/llama-cag-n8n.git
cd llama-cag-n8n
```

### Step 2: Set up environment variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit the file with your preferred settings
nano .env
```

**CRITICAL: You MUST configure these values in your `.env` file:**

```
# Database credentials - CHANGE THESE!
DB_PASSWORD=your_secure_password_here

# n8n secrets - CHANGE THESE! (generate with: openssl rand -hex 16)
N8N_ENCRYPTION_KEY=your_secure_encryption_key
N8N_USER_MANAGEMENT_JWT_SECRET=your_jwt_secret

# LARGE CONTEXT WINDOW MODEL CONFIGURATION
LLAMACPP_MODEL_PATH=~/Documents/llama.cpp/models/gemma-4b.gguf
LLAMACPP_MODEL_NAME=gemma-4b.gguf
LLAMACPP_MAX_CONTEXT=128000  # 128K context window
```

### Step 3: Run the setup script

```bash
python setup.py
```

### Step 4: Start the services

```bash
python start_services.py --profile cpu
```

### Step 5: Set up n8n (http://localhost:5678/)
1. Create a local account
2. Import both workflows from n8n/workflows/
3. Configure the PostgreSQL credential:
   - Host: `db`
   - Database: `llamacag`
   - User: `llamacag`
   - Password: `your_secure_password_here` (from .env)
4. Activate both workflows

## Understanding CAG with Large Context Models

The key differentiator of this system is using large context window models (128K+ tokens) for Context-Augmented Generation:

1. **Entire Document Processing**: Rather than chunking documents into small pieces, we can process much larger sections or entire documents at once.

2. **KV Cache Storage**: The system creates and stores KV (Key-Value) caches that capture the model's state after processing the document. This is effectively "perfect memory" of the document content.

3. **Direct Query Against Document Context**: When querying, we load the pre-computed KV cache, giving the model complete access to the document's content without reprocessing.

4. **Compared to Traditional RAG**:
   - RAG: Chunks → Embeds → Vector DB → Retrieves chunks → Combines → Processes
   - CAG: Entire document → KV Cache → Direct access to full context

## Supported Large Context Window Models

For optimal results, use models with large context windows:

| Model | Context Size | Recommended For |
|-------|-------------|----------------|
| Gemma 4B | 128K tokens | General purpose, excellent performance/size ratio |
| DeepSeek v2 7B | 128K tokens | More powerful reasoning |
| Mistral Large 2 7B | 128K tokens | Strong reasoning capabilities |
| Llama 3 8B | 128K tokens | Strong overall performance |

The default configuration uses Gemma 4B but you can easily switch by changing the `LLAMACPP_MODEL_PATH` and `LLAMACPP_MODEL_NAME` in your `.env` file.

## Detailed Installation

### Prerequisites

- Python 3.8+
- Git
- Docker Desktop
- 16GB RAM recommended (8GB minimum)
- 20GB free disk space

### Step-by-Step Setup

#### 1. Clone the repository and navigate to it
```bash
git clone https://github.com/username/llama-cag-n8n.git
cd llama-cag-n8n
```

#### 2. Configure your environment
Copy and edit the .env file:
```bash
cp .env.example .env
nano .env
```

Required configurations:
```
# Database configuration
DB_PASSWORD=your_secure_password_here  # CHANGE THIS!

# n8n configuration 
N8N_ENCRYPTION_KEY=your_secure_encryption_key  # CHANGE THIS!
N8N_USER_MANAGEMENT_JWT_SECRET=your_jwt_secret  # CHANGE THIS!

# Large context window model configuration
LLAMACPP_MODEL_PATH=~/Documents/llama.cpp/models/gemma-4b.gguf
LLAMACPP_MODEL_NAME=gemma-4b.gguf
LLAMACPP_MAX_CONTEXT=128000  # 128K tokens
```

#### 3. Run the setup script
```bash
python setup.py
```
This script will:
- Install needed dependencies
- Install llama.cpp
- Download your chosen LLM model
- Set up project folders
- Create necessary configuration files

#### 4. Start the services
```bash
python start_services.py --profile cpu
```

#### 5. Configure n8n
1. Open http://localhost:5678/
2. Create a local account
3. Import both workflows:
   - Go to Workflows → Import from File
   - Select both files in n8n/workflows/
4. Configure PostgreSQL credential:
   - Host: `db`
   - Database: `llamacag` 
   - User: `llamacag`
   - Password: Your DB_PASSWORD from .env
5. Activate both workflows by clicking "Active" toggle

## Usage

### Processing Large Documents

To process documents with CAG:

1. Place documents (PDF, TXT, MD, HTML) in the watch folder:
   - Default location: `~/Documents/cag_documents`

2. The system will automatically:
   - Detect new documents
   - Extract text
   - Process with the large context window model
   - Create KV caches
   - Store metadata in the database

NOTE: The system is configured to handle documents up to the model's context length (128K tokens by default). For extremely large documents that exceed this limit, the system will still chunk them, but into much larger chunks than traditional RAG systems.

### Querying Documents

You can query your documents through the API endpoint:

```bash
curl -X POST http://localhost:5678/webhook/cag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Summarize the key points from the technical documentation",
    "documentSources": ["technical_manual.pdf"]
  }'
```

### Batch Processing Documents

For large document collections:

```bash
# Process all PDF files in a directory
python scripts/python/batch_process.py --dir /path/to/documents --extension pdf
```

### Managing KV Caches

To view your KV caches:

```bash
# List all KV caches
python scripts/python/list_caches.py

# List caches sorted by size
python scripts/python/list_caches.py --sort size
```

## Troubleshooting

### Common Issues

#### "Model exceeds memory capacity"
- If you're using a 128K token model but your system doesn't have enough RAM:
  - Try using a smaller model (like Gemma 2B) or a more quantized version (Q4_0)
  - Reduce LLAMACPP_MAX_CONTEXT in .env (e.g., to 64000)
  - Increase your system's swap space

#### "Document processing takes too long"
- Large context window models require more processing power
- For faster processing:
  - Use a GPU if available (use `--profile gpu-nvidia` when starting services)
  - Adjust LLAMACPP_THREADS in .env to match your CPU core count

#### "llama.cpp binary not found"
- Run `scripts/bash/install_llamacpp.sh` to install llama.cpp
- Check your LLAMACPP_PATH in .env

#### "Can't connect to database"
- Check that PostgreSQL is running with `docker ps`
- Verify credentials in .env

#### "Model not found"
- The setup script attempts to download Gemma 4B automatically
- If this fails, manually download your preferred model to the path specified in LLAMACPP_MODEL_PATH

### Stopping Services

To stop all services:
```bash
python start_services.py --stop
```

## Repository Structure

```
llama-cag-n8n/
├── .env.example               # Template for environment variables
├── database/
│   └── schema.sql             # Database schema for CAG system
├── docker-compose.yml         # Docker configuration 
├── docs/
│   └── images/                # Documentation images and diagrams
├── n8n/
│   └── workflows/             # Ready-to-import n8n workflows
├── scripts/
│   ├── bash/                  # Bash scripts for llama.cpp operations
│   └── python/                # Python utility scripts
├── setup.py                   # Installation script
└── start_services.py          # Service management script
```


## Acknowledgements

- [llama.cpp](https://github.com/ggerganov/llama.cpp) for enabling local LLM inference with large context windows
- [n8n](https://n8n.io/) for the workflow automation platform

