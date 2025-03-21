# Implementation Recommendations for llama-cag-n8n

Based on a comprehensive review of the codebase and system architecture, here are recommended implementations to address the identified areas for improvement.

## 1. Security Enhancements

### 1.1 Add Authentication to CAG Bridge

Implement a simple authentication mechanism for the CAG Bridge service:

```python
# Add to bridge/cag_bridge.py
import base64
import os

# Environment-based authentication
API_KEY = os.environ.get('CAG_BRIDGE_API_KEY', 'change-me-in-production')

class CAGHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Check authentication
        auth_header = self.headers.get('Authorization')
        if not auth_header or not self._validate_auth(auth_header):
            self.send_response(401)
            self.send_header('WWW-Authenticate', 'Basic realm="CAG Bridge"')
            self.end_headers()
            return
            
        # Existing POST handling code...
        
    def do_GET(self):
        # Health endpoint doesn't require authentication
        if self.path == '/health':
            # Existing health endpoint code...
            return
            
        # Other GET endpoints require authentication
        auth_header = self.headers.get('Authorization')
        if not auth_header or not self._validate_auth(auth_header):
            self.send_response(401)
            self.send_header('WWW-Authenticate', 'Basic realm="CAG Bridge"')
            self.end_headers()
            return
            
        # Existing GET handling code...
        
    def _validate_auth(self, auth_header):
        """Validate the Authorization header"""
        try:
            if auth_header.startswith('Bearer '):
                # API key authentication
                token = auth_header.split(' ')[1]
                return token == API_KEY
            elif auth_header.startswith('Basic '):
                # Basic authentication
                auth_decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
                username, password = auth_decoded.split(':')
                return username == 'cag' and password == API_KEY
            return False
        except Exception:
            return False
```

Update docker-compose.yml to include the API key:

```yaml
cag-bridge:
  # Existing configuration...
  environment:
    - CAG_BRIDGE_API_KEY=${CAG_BRIDGE_API_KEY:-change-me-in-production}
    # Other environment variables...
```

Add to .env.example:

```
# CAG Bridge Security
CAG_BRIDGE_API_KEY=change-me-in-production  # CHANGE THIS
```

### 1.2 Improve Default Credential Warnings

Update .env.example to make default credentials more obvious:

```
############
# Database Configuration (SECURITY CRITICAL)
############

DB_TYPE=postgres
DB_HOST=db
DB_PORT=5432
DB_NAME=llamacag
DB_USER=llamacag
DB_PASSWORD=your_secure_password_here  # ⚠️ SECURITY RISK: CHANGE THIS BEFORE USING! ⚠️

############
# n8n Configuration (SECURITY CRITICAL)
############

N8N_HOST=localhost
N8N_PORT=5678
N8N_PROTOCOL=http
N8N_ENCRYPTION_KEY=your-secure-encryption-key  # ⚠️ SECURITY RISK: CHANGE THIS BEFORE USING! ⚠️
N8N_USER_MANAGEMENT_JWT_SECRET=your-jwt-secret  # ⚠️ SECURITY RISK: CHANGE THIS BEFORE USING! ⚠️
```

### 1.3 Improve Docker Network Security

Update docker-compose.yml to use internal networks where appropriate:

```yaml
services:
  n8n:
    # Existing configuration...
    ports:
      - "${N8N_PORT:-5678}:5678"
    networks:
      - frontend
      - backend

  db:
    # Existing configuration...
    # Remove direct port exposure for production
    ports:
      - "${DB_PORT:-5432}:5432"
    networks:
      - backend
      
  cag-bridge:
    # Existing configuration...
    # Only expose to n8n, not directly to host
    ports:
      - "127.0.0.1:${CAG_BRIDGE_PORT:-8000}:8000"
    networks:
      - backend

networks:
  frontend:
    # External-facing network
  backend:
    # Internal-only network
    internal: true
```

Add production deployment option to start_services.py:

```python
parser.add_argument('--production', action='store_true', 
                    help='Start services in production mode with enhanced security')

# In start_services function:
if args.production:
    logging.info("Starting services in production mode with enhanced security")
    # Modify docker-compose command to use production override
    subprocess.run(['docker', 'compose', '-f', 'docker-compose.yml', '-f', 'docker-compose.prod.yml', 'up', '-d'], check=True)
else:
    # Development mode (existing code)
    subprocess.run(['docker', 'compose', 'up', '-d'], check=True)
```

## 2. Error Handling Improvements

### 2.1 Enhance Bash Script Error Handling

Update all bash scripts to include robust error handling:

```bash
#!/bin/bash
# Improved error handling
set -e  # Exit on any error
set -u  # Treat unset variables as errors
set -o pipefail  # Handle errors in pipelines

# Function for cleanup on exit
cleanup() {
  # Get exit code
  EXIT_CODE=$?
  
  # Perform cleanup
  if [ -d "$TEMP_DIR" ]; then
    rm -rf "$TEMP_DIR"
  fi
  
  # Log exit
  if [ $EXIT_CODE -ne 0 ]; then
    echo "Script exited with error code $EXIT_CODE" >&2
  fi
  
  exit $EXIT_CODE
}

# Register cleanup function
trap cleanup EXIT

# Create temporary directory with secure permissions
TEMP_DIR=$(mktemp -d)
chmod 700 "$TEMP_DIR"

# Handle spaces in paths by quoting variables
MODEL_PATH="${1:-$LLAMACPP_MODEL_PATH}"
CACHE_FILE="$2"
QUERY="$3"
```

### 2.2 Improve Memory Management

Add memory usage estimation and warnings to create_kv_cache.sh:

```bash
# Add to create_kv_cache.sh

# Estimate memory requirements
TOKEN_ESTIMATE=$((CHUNK_SIZE / 4))
ESTIMATED_MEMORY_MB=$((TOKEN_ESTIMATE * 48 / 1024))  # Rough estimate: 48 bytes per token for KV cache
AVAILABLE_MEMORY_MB=$(free -m | awk '/^Mem:/{print $7}')

echo "Estimated memory requirement: ~${ESTIMATED_MEMORY_MB}MB for ${TOKEN_ESTIMATE} tokens"

if [ "$AVAILABLE_MEMORY_MB" -lt "$ESTIMATED_MEMORY_MB" ]; then
  echo "⚠️ WARNING: Available memory (${AVAILABLE_MEMORY_MB}MB) may be insufficient for this operation"
  echo "Consider reducing LLAMACPP_MAX_CONTEXT in .env file or processing a smaller document"
  
  # Ask for confirmation if interactive
  if [ -t 0 ]; then
    read -p "Continue anyway? [y/N] " CONTINUE
    if [[ ! $CONTINUE =~ ^[Yy]$ ]]; then
      echo "Operation cancelled by user"
      exit 1
    fi
  fi
fi
```

### 2.3 Improve Path Handling

Update all scripts to properly handle spaces in paths:

```bash
# Example improvement for query_kv_cache.sh
PROMPT_FILE="${TEMP_DIR}/prompt.txt"
echo "$QUERY" > "$PROMPT_FILE"

# Run llama.cpp with the KV cache, optimized for large context
"$LLAMACPP_PATH/build/bin/main" \
  -m "$MODEL_PATH" \
  --load-kv-cache "$CACHE_FILE" \
  -f "$PROMPT_FILE" \
  -n "$MAX_TOKENS" \
  --ctx-size "$MAX_CONTEXT" \
  --threads "$THREADS" \
  --no-mmap \
  --memory-f32 \
  --temp "$TEMPERATURE" \
  --repeat-penalty 1.1 \
  --top-p 0.9 2>> "$LOG_FILE"
```

## 3. Cross-Platform Compatibility

### 3.1 Enhance OS Detection and Configuration

Update setup.py and start_services.py with better platform-specific handling:

```python
# Add to setup.py or start_services.py

def detect_platform():
    """Detect platform and return configuration options"""
    import platform
    
    result = {
        'is_mac': False,
        'is_linux': False,
        'is_apple_silicon': False,
        'gpu_support': False,
        'recommended_threads': 1
    }
    
    system = platform.system().lower()
    
    if system == 'darwin':
        result['is_mac'] = True
        
        # Detect Apple Silicon
        try:
            processor = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                      capture_output=True, text=True, check=True).stdout
            result['is_apple_silicon'] = 'Apple' in processor
        except:
            # Default to false if detection fails
            pass
            
        # Mac-specific settings
        result['gpu_support'] = False  # No GPU support on Mac
        import multiprocessing
        result['recommended_threads'] = max(1, multiprocessing.cpu_count() - 1)
        
    elif system == 'linux':
        result['is_linux'] = True
        
        # Check for NVIDIA GPU
        try:
            nvidia_smi = subprocess.run(['nvidia-smi'], 
                                      capture_output=True, text=True, check=False)
            result['gpu_support'] = nvidia_smi.returncode == 0
        except:
            # nvidia-smi not found
            pass
            
        # Linux-specific settings
        import multiprocessing
        result['recommended_threads'] = max(1, multiprocessing.cpu_count() - 1)
    
    return result

platform_info = detect_platform()

# Use platform_info to adjust settings
if platform_info['is_mac'] and platform_info['is_apple_silicon']:
    logging.info("Detected Apple Silicon Mac - optimizing settings")
    os.environ['LLAMACPP_THREADS'] = str(platform_info['recommended_threads'])
    os.environ['LLAMACPP_GPU_LAYERS'] = '0'  # No GPU on Mac
elif platform_info['is_linux'] and platform_info['gpu_support']:
    logging.info("Detected Linux with NVIDIA GPU - enabling GPU acceleration")
    os.environ['LLAMACPP_GPU_LAYERS'] = '33'  # Default for GPU
else:
    logging.info(f"Using CPU-only mode with {platform_info['recommended_threads']} threads")
    os.environ['LLAMACPP_THREADS'] = str(platform_info['recommended_threads'])
    os.environ['LLAMACPP_GPU_LAYERS'] = '0'
```

### 3.2 Improve Path Handling Across Platforms

Update path handling in all scripts:

```python
# Example from start_services.py
def normalize_path(path):
    """Normalize path for current platform"""
    if path.startswith('~'):
        path = os.path.expanduser(path)
    
    # Convert to absolute path
    path = os.path.abspath(path)
    
    # Handle Windows paths
    if os.name == 'nt':
        # Convert to Windows-compatible Docker path if needed
        # e.g., C:\Users\name\path -> /c/Users/name/path
        if re.match(r'^[A-Za-z]:\\', path):
            drive, rest = path[0], path[3:]
            path = f"/{drive.lower()}{rest.replace('\\', '/')}"
    
    return path

# Use this function when setting up paths for Docker
model_path = normalize_path(env_vars.get('LLAMACPP_MODEL_PATH', '~/Documents/llama.cpp/models/gemma-4b.gguf'))
```

## 4. Documentation and Usability

### 4.1 Add API Documentation File

Create a new file DOCS/API.md:

```markdown
# CAG API Documentation

This document describes the API endpoints available in the llama-cag-n8n system.

## CAG Bridge Endpoints

The CAG Bridge service provides the following endpoints:

### Query Endpoint

**URL**: `/query`
**Method**: `POST`
**Authentication**: Bearer token or Basic auth

**Request Body**:
```json
{
  "query": "Your question about the documents?",
  "maxTokens": 1024,
  "temperature": 0.7
}
```

**Response**:
```json
{
  "success": true,
  "response": "The answer to your question...",
  "error": null,
  "query": "Your question about the documents?"
}
```

### Create Cache Endpoint

**URL**: `/create-cache`
**Method**: `POST`
**Authentication**: Bearer token or Basic auth

**Request Body**:
```json
{
  "documentId": "document-123",
  "tempFilePath": "/data/temp_chunks/document.txt",
  "kvCachePath": "/data/kv_caches/document_cache.bin",
  "estimatedTokens": 5000,
  "setAsMaster": false
}
```

**Response**:
```json
{
  "success": true,
  "documentId": "document-123",
  "kvCachePath": "/data/kv_caches/document_cache.bin",
  "kvCacheSize": 2500000,
  "contextSize": 5000,
  "error": null,
  "output": "Created KV cache successfully"
}
```

### Health Endpoint

**URL**: `/health`
**Method**: `GET`
**Authentication**: None (public)

**Response**:
```json
{
  "status": "healthy",
  "issues": [],
  "config": {
    "master_kv_cache": "/data/kv_caches/master_cache.bin",
    "model_path": "/usr/local/llamacpp/models/gemma-4b.gguf",
    "query_script": "/usr/local/bin/cag-scripts/query_kv_cache.sh",
    "create_script": "/usr/local/bin/cag-scripts/create_kv_cache.sh",
    "max_context": "128000",
    "threads": "4",
    "batch_size": "1024"
  }
}
```

## n8n Webhook Endpoints

The n8n workflows expose the following webhook endpoints:

### Query Webhook

**URL**: `http://localhost:5678/webhook/cag/query`
**Method**: `POST`
**Authentication**: None (secure this endpoint if exposed publicly)

**Request Body**:
```json
{
  "query": "Your question about the documents?",
  "maxTokens": 1024,
  "temperature": 0.7
}
```

**Response**:
```json
{
  "query": "Your question about the documents?",
  "response": "The answer to your question...",
  "success": true,
  "error": null,
  "processedAt": "2025-03-21T10:15:30.123Z"
}
```
```

### 4.2 Add Troubleshooting Guide

Create a new file DOCS/TROUBLESHOOTING.md:

```markdown
# Troubleshooting Guide for llama-cag-n8n

This document provides solutions for common issues you might encounter when using the llama-cag-n8n system.

## Installation Issues

### Docker Not Running

**Symptoms**: 
- Error message: "Docker is not running"
- Command `docker ps` fails

**Solution**:
1. Start Docker Desktop if you're on macOS or Windows
2. On Linux, run `sudo systemctl start docker`
3. Verify Docker is running with `docker ps`

### llama.cpp Build Failures

**Symptoms**:
- Error messages during compilation
- Missing executable in `build/bin/main`

**Solutions**:
1. Make sure required dependencies are installed:
   - macOS: `brew install cmake gcc make`
   - Ubuntu: `apt install build-essential cmake`
2. Try the manual build process:
   ```bash
   cd ~/Documents/llama.cpp
   mkdir -p build
   cd build
   cmake ..
   make -j4
   ```
3. Check for specific error messages and ensure your compiler is up to date

## Document Processing Issues

### "Out of Memory" Errors

**Symptoms**:
- Process terminates with "Out of memory" or "Killed"
- High memory usage in system monitor

**Solutions**:
1. Reduce context window size in .env file:
   ```
   LLAMACPP_MAX_CONTEXT=64000  # Reduced from 128000
   ```
2. Use a smaller model (e.g., switch to Gemma 2B instead of 7B)
3. Split very large documents into smaller chunks
4. Increase system swap space

### KV Cache Creation Fails

**Symptoms**:
- Error message: "Failed to create KV cache"
- Missing or zero-sized cache files

**Solutions**:
1. Check log file in `/tmp/kvcache_*.log` for specific errors
2. Verify the document isn't empty or corrupted
3. Ensure temp directory has sufficient space
4. Check file permissions on KV cache directory

## Query Issues

### "Cache file not found" Error

**Symptoms**:
- Error message: "Cache file not found"
- Query fails to complete

**Solutions**:
1. Verify the cache file exists using `ls -la /path/to/kv_caches`
2. Check that the correct path is being provided
3. Run `python scripts/python/list_caches.py` to see all available caches
4. Reprocess the document if necessary

### Incomplete or Wrong Answers

**Symptoms**:
- Query produces irrelevant responses
- Missing information in responses

**Solutions**:
1. Try querying with a higher temperature (e.g., 0.8 instead of 0.7)
2. Ensure the document was properly processed
3. Check that master KV cache includes the relevant documents
4. Try more specific queries with key terms from the document

## Docker and Container Issues

### Container Won't Start

**Symptoms**:
- Container fails to start or stops immediately
- Error in Docker logs

**Solutions**:
1. Check container logs with `docker logs llamacag-n8n` (or other container name)
2. Verify port availability - ensure ports 5678 and 5432 aren't in use
3. Check that volumes are properly mounted
4. Ensure .env file contains all required variables

### Database Connection Errors

**Symptoms**:
- Error connecting to database
- n8n workflows fail with database errors

**Solutions**:
1. Verify PostgreSQL container is running: `docker ps | grep llamacag-db`
2. Check database logs: `docker logs llamacag-db`
3. Verify credentials in .env file match what's in docker-compose.yml
4. Try connecting manually to test:
   ```bash
   docker exec -it llamacag-db psql -U llamacag -d llamacag
   ```

## n8n Workflow Issues

### Workflow Import Fails

**Symptoms**:
- Error when importing workflows
- Workflows don't appear in n8n

**Solutions**:
1. Check n8n logs for specific error messages
2. Verify workflow JSON files are valid: `jq . n8n/workflows/*.json`
3. Import manually through n8n UI: Workflows → Import From File
4. Update n8n to latest version

### Credential Configuration Issues

**Symptoms**:
- Workflow runs but fails with credential errors
- Database nodes fail to connect

**Solutions**:
1. Set up PostgreSQL credential in n8n:
   - Host: `db` (not localhost)
   - Database: `llamacag`
   - User: `llamacag`
   - Password: Your DB_PASSWORD from .env
2. Test connection before saving

## Performance Optimization

### Slow Document Processing

**Symptoms**:
- Document processing takes a very long time
- High CPU usage during processing

**Solutions**:
1. Increase number of threads in .env: `LLAMACPP_THREADS=8`
2. Enable GPU acceleration if available (Linux NVIDIA only)
3. Process documents during off-peak hours
4. Consider using a more quantized model (Q4_0 instead of Q8_0)

### Slow Query Responses

**Symptoms**:
- Queries take a long time to respond
- Timeout errors

**Solutions**:
1. Use the master KV cache approach for frequently queried documents
2. Optimize the prompt format for more direct answers
3. Reduce max_tokens if full responses aren't needed
4. Consider using smaller, faster models for time-sensitive queries
```

### 4.3 Add Workflow Documentation

Create a new file DOCS/WORKFLOWS.md:

```markdown
# n8n Workflow Documentation

This document explains the workflows used in the llama-cag-n8n system and how to customize them for your needs.

## Document Processing Workflow

**Purpose**: Process documents and create KV caches

### Workflow Steps

1. **Trigger**
   - Manual trigger or file upload trigger
   - Configurable to watch a directory for new documents

2. **Set Document Parameters (Set Node)**
   - Sets essential parameters:
     - `documentPath`: Full path to your source document
     - `documentId`: A unique identifier for your document 
     - `kvCachePath`: Destination path for storing the KV cache
     - `tempFilePath`: Temporary storage path
     - `setAsMaster`: Boolean indicating if this KV cache should be the primary knowledge base

3. **Read Binary File (Read Binary File Node)**
   - Reads the document from the provided documentPath
   - Outputs binary data to pass to the next node

4. **Write Temp File (Write Binary File Node)**
   - Writes the binary data to a temporary location (tempFilePath)
   - Ensures a clear and accessible location for subsequent processing

5. **Create KV Cache (HTTP Request Node)**
   - Sends a JSON payload to the CAG Bridge endpoint (/create-cache)
   - JSON payload includes:
     - documentId
     - tempFilePath
     - kvCachePath
     - estimatedTokens
     - setAsMaster
   - The bridge processes the temporary file to create the KV cache

6. **Result (Set Node)**
   - Formats the response for display
   - Shows success/failure status and details

### Customization Options

- **Document Chunking**: For very large documents, enable the Document Size Check node
- **Document Optimization**: Connect to the Claude API node to optimize document content before processing
- **Metadata Extraction**: Add nodes to extract and store document metadata
- **Notification**: Add Email or Slack nodes to notify when processing completes

## Query Workflow

**Purpose**: Handle user queries using KV caches

### Workflow Steps

1. **Webhook Trigger**
   - Listens for incoming HTTP requests
   - Expects JSON body with query parameters

2. **Retrieve Context (PostgreSQL Node)**
   - Optional step for RAG-style retrieval
   - Queries the database to find relevant document chunks

3. **Query Processing**
   - Constructs the prompt with context and query
   - Calls the CAG Bridge to execute the query against the KV cache
   - Formats the response

4. **Response**
   - Returns the formatted response to the webhook

### Customization Options

- **Response Enhancement**: Add nodes to enhance responses with additional context
- **Citation Generation**: Add logic to include source citations in responses
- **Context Mixing**: Combine results from multiple KV caches for comprehensive answers
- **Caching**: Add caching nodes to store frequent queries for faster responses

## Maintenance Workflow

**Purpose**: Perform system maintenance and cleanup

### Workflow Steps

1. **Scheduled Trigger**
   - Runs at specified intervals (default: daily)
   
2. **Cleanup Tasks**
   - Removes old temporary files
   - Identifies orphaned KV cache files
   - Updates database entries for failed processes
   
3. **Performance Monitoring**
   - Records system statistics
   - Tracks resource usage

### Customization Options

- **Retention Policy**: Adjust the age thresholds for cleanup
- **Notifications**: Add alerts for system health issues
- **Logging**: Enhance logging for better diagnostics
- **Backup**: Add nodes to perform database and KV cache backups
```

## 5. Performance Optimizations

### 5.1 Optimize Database Indexes

Add additional indexes to database/schema.sql:

```sql
-- Improved indexes for performance
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_document_type ON documents(document_type);
CREATE INDEX IF NOT EXISTS idx_document_registry_estimated_tokens ON cag_document_registry(estimated_tokens);
CREATE INDEX IF NOT EXISTS idx_query_log_query_type ON query_log(query_type);
CREATE INDEX IF NOT EXISTS idx_query_log_success ON query_log(success);

-- Improved function for looking up similar documents
CREATE OR REPLACE FUNCTION find_similar_documents(search_text TEXT)
RETURNS TABLE(document_id VARCHAR, chunk_id VARCHAR, relevance FLOAT) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        dr.document_id,
        dr.chunk_id,
        ts_rank_cd(to_tsvector('english', dr.section_title || ' ' || COALESCE(dr.chunk_text, '')), 
                  plainto_tsquery('english', search_text)) AS relevance
    FROM cag_document_registry dr
    WHERE dr.cag_status = 'cached'
    AND to_tsvector('english', dr.section_title || ' ' || COALESCE(dr.chunk_text, '')) @@ 
        plainto_tsquery('english', search_text)
    ORDER BY relevance DESC
    LIMIT 5;
END;
$$ LANGUAGE plpgsql;
```

### 5.2 Optimize Batch Processing

Improve batch_process.py with better parallelism:

```python
# Add to scripts/python/batch_process.py
import concurrent.futures
import tqdm

def process_document(file_path, target_dir, timestamp_prefix=None):
    """Process a single document"""
    try:
        # Create filename with timestamp to avoid conflicts
        timestamp = timestamp_prefix or datetime.now().strftime("%Y%m%d%H%M%S")
        target_file = Path(target_dir) / f"{timestamp}_{file_path.name}"
        
        # Copy file to target directory
        shutil.copy2(file_path, target_file)
        return True, file_path.name, str(target_file)
    except Exception as e:
        return False, file_path.name, str(e)

def process_documents_parallel(source_dir, extension=None, limit=None, max_workers=4):
    """Process documents in parallel"""
    env_vars = load_env()
    target_dir = os.path.expanduser(env_vars.get('DOCUMENTS_FOLDER', '~/Documents/cag_documents'))
    
    # Ensure target directory exists
    os.makedirs(target_dir, exist_ok=True)
    
    # Find files to process
    source_path = Path(source_dir).expanduser()
    if not source_path.exists():
        logging.error(f"Source directory not found: {source_path}")
        return False
    
    # Get list of files with optional extension filter
    files = list(source_path.glob(f"*.{extension}" if extension else "*"))
    files = [f for f in files if f.is_file()]
    
    if not files:
        logging.warning(f"No matching files found in {source_path}")
        return False
    
    # Apply limit if specified
    if limit and len(files) > limit:
        logging.info(f"Limiting to {limit} files from {len(files)} available")
        files = files[:limit]
    
    logging.info(f"Found {len(files)} files to process")
    
    # Create a timestamp prefix for this batch
    timestamp_base = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Process files in parallel
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Create a dict of futures to filenames for better reporting
        future_to_file = {
            executor.submit(process_document, file_path, target_dir, f"{timestamp_base}_{i}"): file_path
            for i, file_path in enumerate(files)
        }
        
        # Show progress bar
        for future in tqdm.tqdm(concurrent.futures.as_completed(future_to_file), total=len(files)):
            file_path = future_to_file[future]
            try:
                success, filename, result = future.result()
                if success:
                    logging.info(f"Processed: {filename} -> {result}")
                else:
                    logging.error(f"Failed to process {filename}: {result}")
                
                results.append((success, filename, result))
            except Exception as e:
                logging.error(f"Error processing {file_path.name}: {str(e)}")
                results.append((False, file_path.name, str(e)))
    
    # Summarize results
    successes = sum(1 for r in results if r[0])
    failures = sum(1 for r in results if not r[0])
    
    logging.info(f"Batch processing complete: {successes} succeeded, {failures} failed")
    logging.info(f"Files copied to {target_dir}")
    
    return successes > 0
```

### 5.3 Implement Smarter KV Cache Management

Improve list_caches.py with better cache management:

```python
# Add to scripts/python/list_caches.py

def recommend_cache_cleanup(conn, min_days_unused=30, min_size_mb=100):
    """Recommend caches for cleanup based on usage and size"""
    cursor = conn.cursor()
    
    # Find caches that haven't been used in a while and are large
    cursor.execute("""
        SELECT 
            c.document_id, 
            c.kv_cache_path, 
            c.last_used,
            c.usage_count,
            d.document_title
        FROM cag_document_registry c
        JOIN documents d ON c.document_id = d.document_id
        WHERE c.cag_status = 'cached'
        AND (c.last_used IS NULL OR c.last_used < NOW() - INTERVAL %s DAY)
        ORDER BY c.last_used NULLS FIRST, c.usage_count
        LIMIT 20
    """, (min_days_unused,))
    
    results = cursor.fetchall()
    
    recommendations = []
    for doc_id, cache_path, last_used, usage_count, title in results:
        if not cache_path or not os.path.exists(os.path.expanduser(cache_path)):
            continue
            
        size_mb = os.path.getsize(os.path.expanduser(cache_path)) / (1024 * 1024)
        
        if size_mb >= min_size_mb:
            last_used_str = last_used.strftime('%Y-%m-%d') if last_used else 'Never'
            recommendations.append({
                'document_id': doc_id,
                'title': title,
                'cache_path': cache_path,
                'size_mb': size_mb,
                'last_used': last_used_str,
                'usage_count': usage_count or 0
            })
    
    return recommendations

def cleanup_unused_caches(dry_run=True, min_days_unused=30, min_size_mb=100):
    """Clean up unused caches"""
    env_vars = load_env()
    conn = get_db_connection(env_vars)
    
    if not conn:
        logging.error("Could not connect to database")
        return False
    
    recommendations = recommend_cache_cleanup(conn, min_days_unused, min_size_mb)
    
    if not recommendations:
        logging.info("No caches recommended for cleanup")
        return True
    
    total_space = sum(r['size_mb'] for r in recommendations)
    logging.info(f"Recommended for cleanup: {len(recommendations)} caches, {total_space:.2f}MB total")
    
    for rec in recommendations:
        path = os.path.expanduser(rec['cache_path'])
        logging.info(f"{'Would remove' if dry_run else 'Removing'}: {rec['document_id']} ({rec['title']}) - {rec['size_mb']:.2f}MB, last used: {rec['last_used']}")
        
        if not dry_run:
            try:
                os.remove(path)
                # Update database
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE cag_document_registry
                    SET kv_cache_path = NULL, cag_status = 'cleaned'
                    WHERE kv_cache_path = %s
                """, (rec['cache_path'],))
                conn.commit()
            except Exception as e:
                logging.error(f"Error removing {path}: {str(e)}")
    
    if conn:
        conn.close()
    
    return True
```

Add to main function:

```python
parser.add_argument('--cleanup', action='store_true', help='Clean up unused caches')
parser.add_argument('--dry-run', action='store_true', help='Dry run mode (don\'t actually delete)')
parser.add_argument('--min-days', type=int, default=30, help='Minimum days since last use for cleanup')
parser.add_argument('--min-size', type=int, default=100, help='Minimum size in MB for cleanup')

# In main function
if args.cleanup:
    success = cleanup_unused_caches(
        dry_run=args.dry_run,
        min_days_unused=args.min_days,
        min_size_mb=args.min_size
    )
    sys.exit(0 if success else 1)
```
