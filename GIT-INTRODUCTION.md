# llama-cag-n8n: A Comprehensive Guide

## What is This Repository?

llama-cag-n8n is an open-source implementation of Context-Augmented Generation (CAG) using llama.cpp and n8n, designed specifically to leverage large context window models (128K+ tokens) for document understanding and querying.

This guide explains what happens on your machine when you install this system, what services run, and potential issues you might encounter.

## What Makes This Special?

### Context-Augmented Generation vs. Traditional RAG

Most AI systems today use Retrieval-Augmented Generation (RAG), which:
1. Splits documents into small chunks (a few thousand tokens)
2. Creates embeddings for each chunk
3. Stores these in a vector database
4. When you ask a question, retrieves relevant chunks 
5. Combines chunks into a prompt
6. Sends everything to the LLM for a response

**The CAG approach is fundamentally different:**
1. We utilize large context window models (128K tokens) that can process massive documents
2. During document ingestion, we create and store KV (Key-Value) caches that capture the model's "state" after processing the document
3. When querying, we load these pre-computed KV caches - giving the model direct access to the document's content without reprocessing
4. This is like giving the model a "perfect memory" of the document

The result: faster, more accurate responses that better preserve the context and intention of your documents.

## What Happens When You Install This System?

### Installation Process

When you run `python setup.py` and `python start_services.py`, these things happen on your machine:

1. **Environment Setup**:
   - A `.env` file is created with your configuration
   - Project directories are created at the specified locations

2. **Software Installation**:
   - llama.cpp is cloned and compiled (if not already present)
   - A large context window model is downloaded (default: Gemma 4B)

3. **Docker Container Creation**:
   - Docker pulls necessary images (n8n, PostgreSQL)
   - Containers are created and started
   - Volumes are mounted for data persistence

4. **Service Configuration**:
   - Configuration files are created for all components
   - Scripts are made executable
   - Database schema is initialized

### Running Services

After installation, these services run on your machine:

1. **n8n** (Port 5678):
   - Low-code automation platform
   - Hosts the document processing and query workflows
   - Provides the web interface and API endpoints
   - Uses 2-8GB RAM depending on document size and model

2. **PostgreSQL** (Port 5432):
   - Database storing document metadata
   - Tracks KV cache locations
   - Logs queries and responses
   - Uses 512MB-1GB RAM

3. **llama.cpp**:
   - Not a continuously running service
   - Invoked by n8n when processing documents or handling queries
   - Memory usage varies by model size and document length
   - With 128K context: expects 4-16GB RAM depending on the model

### File Organization

The system creates and manages these directories:

1. **KV Cache Directory** (Default: `~/cag_project/kv_caches`):
   - Stores the KV cache files generated from documents
   - Each document gets its own subdirectory
   - These files can be large (100MB-2GB each)

2. **Temporary Directory** (Default: `~/cag_project/temp_chunks`):
   - Used during document processing
   - Files are deleted after processing

3. **Documents Directory** (Default: `~/Documents/cag_documents`):
   - Where you place documents to be processed
   - Monitored by the n8n workflow

## Hardware and Software Requirements

### Hardware Requirements

- **CPU**: 4+ cores recommended
- **RAM**: 16GB minimum for 128K context window models
- **Storage**: 20GB+ free space
- **GPU**: Optional, only used if on Linux with NVIDIA GPU

### Software Dependencies

- **Docker Desktop**: Required to run the containerized services
- **Python 3.8+**: For the setup and management scripts
- **Git**: For repository cloning and llama.cpp download
- **Bash**: For running the shell scripts
- **curl**: For downloading models and API usage

## Model Parameter Explanation

The system uses these parameters when running the model:

- **Temperature** (Set to 0.7): Controls randomness in responses
- **Top-p** (Set to 0.9): Controls diversity of token selection
- **Repeat Penalty** (Set to 1.1): Discourages repetition

These parameters are deliberately set to be relatively conservative because:

1. **In CAG, accuracy is paramount**: We want the model to stick closely to the information in the document rather than be creative
2. **Determinism is valuable**: You want consistent answers from the same document
3. **The goal is information retrieval**: Not creative writing or exploration

These settings can be adjusted in the script files if needed, but the current values work well for most document query scenarios.

## Known Limitations & Potential Issues

### Memory Usage
- **Large RAM Requirements**: 128K context models need substantial RAM (16GB+ recommended)
- **OOM Errors**: If your machine has insufficient memory, you may see "Out of Memory" errors
- **Solution**: Reduce `LLAMACPP_MAX_CONTEXT` in .env (e.g., to 64000 or 32000)

### Model Compatibility
- **Not All Models Support 128K**: Verify your model supports large context
- **Quantization Effects**: Heavily quantized models (Q4_0) may lose some context capability
- **Solution**: Stick with recommended models (Gemma 4B, DeepSeek, etc.)

### Document Size Limitations
- **Even 128K Has Limits**: ~100 pages of text maximum per KV cache
- **Extremely Large Documents**: Will still be split into chunks, albeit much larger ones
- **Solution**: For massive documents, consider logical splitting beforehand

### Performance Considerations
- **CPU Processing is Slow**: Creating KV caches for large documents can take minutes to hours
- **Querying is Faster**: But still takes a few seconds per query
- **Solution**: Use GPU if available; adjust thread count in .env to match your CPU

### Docker-Related Issues
- **Permission Problems**: May occur on some systems with volume mounts
- **Port Conflicts**: If ports 5678 or 5432 are already in use
- **Solution**: Adjust permissions or port mappings in docker-compose.yml

### Project Status Notice
- **Work in Progress**: This system is still being refined
- **Edge Cases**: Not all document types and query patterns have been tested
- **Feedback Welcome**: Please report issues and success stories

## Best Practices

1. **Start with Smaller Documents**: Test the system with 5-20 page documents first
2. **Monitor Memory Usage**: Watch RAM consumption during document processing
3. **Use Specific Queries**: Ask precise questions about document content
4. **Regular Maintenance**: Clean up unused KV caches to save disk space
5. **Security**: Change all default passwords in .env before using in any shared environment

## Acknowledgements

This project builds upon several remarkable technologies:
- [llama.cpp](https://github.com/ggerganov/llama.cpp) for enabling local inference with large context windows
- [n8n](https://n8n.io/) for the workflow automation capabilities
- The developers of large context window models like Gemma, DeepSeek, and others
