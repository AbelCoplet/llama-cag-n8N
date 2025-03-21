#!/usr/bin/env python3
"""
Simple HTTP server to bridge n8n and llama.cpp CAG
This allows n8n to execute the query_kv_cache.sh and create_kv_cache.sh scripts
"""

import os
import subprocess
import json
import logging
import shutil
from http.server import HTTPServer, BaseHTTPRequestHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CAG-Bridge")

# Configuration from environment variables
MASTER_KV_CACHE = os.environ.get('MASTER_KV_CACHE', '/data/kv_caches/master_cache.bin')
MODEL_PATH = os.environ.get('LLAMACPP_MODEL_PATH', '/usr/local/llamacpp/models/gemma-4b.gguf')
QUERY_SCRIPT_PATH = '/usr/local/bin/cag-scripts/query_kv_cache.sh'  # Path to query script
CREATE_SCRIPT_PATH = '/usr/local/bin/cag-scripts/create_kv_cache.sh'  # Path to create script
MAX_CONTEXT = os.environ.get('LLAMACPP_MAX_CONTEXT', '128000')
THREADS = os.environ.get('LLAMACPP_THREADS', '4')
BATCH_SIZE = os.environ.get('LLAMACPP_BATCH_SIZE', '1024')

# Verify file existence at startup
def check_files():
    issues = []
    
    # Check if the scripts exist
    if not os.path.exists(QUERY_SCRIPT_PATH):
        issues.append(f"Query script not found at: {QUERY_SCRIPT_PATH}")
        
    if not os.path.exists(CREATE_SCRIPT_PATH):
        issues.append(f"Create script not found at: {CREATE_SCRIPT_PATH}")
    
    # Check if the model exists
    if not os.path.exists(MODEL_PATH):
        issues.append(f"Model not found at: {MODEL_PATH}")
        
    # Check if master KV cache exists (only warn, not an error)
    if not os.path.exists(MASTER_KV_CACHE):
        logger.warning(f"Master KV cache not found at: {MASTER_KV_CACHE}. This is fine if you haven't created it yet.")
    
    return issues

class CAGHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/query':
            self.handle_query()
        elif self.path == '/create-cache':
            self.handle_create_cache()
        else:
            self.send_response(404)
            self.end_headers()
    
    def handle_query(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        try:
            # Parse JSON request
            data = json.loads(post_data)
            query = data.get('query', '')
            max_tokens = data.get('maxTokens', 1024)
            temperature = data.get('temperature', 0.7)
            
            # Format the query
            formatted_query = f"Answer this question based on your knowledge:\n\nQuestion: {query}\n\nAnswer:"
            
            # Build command
            temp_param = f"--temp {temperature}" if temperature is not None else ""
            command = f"{QUERY_SCRIPT_PATH} \"{MODEL_PATH}\" \"{MASTER_KV_CACHE}\" \"{formatted_query}\" {max_tokens} {temp_param}"
            
            logger.info(f"Executing query: {command}")
            
            # Execute command
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            
            stdout_text = stdout.decode('utf-8')
            stderr_text = stderr.decode('utf-8')
            
            # Log completion
            logger.info(f"Query completed with exit code: {process.returncode}")
            if stderr_text:
                logger.warning(f"Query stderr: {stderr_text}")
            
            # Send response
            response = {
                'success': process.returncode == 0,
                'response': stdout_text,
                'error': stderr_text if process.returncode != 0 else None,
                'query': query
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}", exc_info=True)
            error_response = {'success': False, 'error': str(e)}
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(error_response).encode('utf-8'))
    
    def handle_create_cache(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        try:
            # Parse JSON request
            data = json.loads(post_data)
            document_id = data.get('documentId', '')
            temp_file_path = data.get('tempFilePath', '')
            kv_cache_path = data.get('kvCachePath', '')
            estimated_tokens = data.get('estimatedTokens', 0)
            
            # Ensure the document ID is provided
            if not document_id:
                raise ValueError("documentId is required")
            
            # Ensure the temp file exists
            if not os.path.exists(temp_file_path):
                raise ValueError(f"Temp file not found at {temp_file_path}")
            
            # Make sure the KV cache directory exists
            kv_cache_dir = os.path.dirname(kv_cache_path)
            os.makedirs(kv_cache_dir, exist_ok=True)
            
            # Calculate context size based on estimated tokens (with some padding)
            context_size = min(max(estimated_tokens + 1000, 2048), int(MAX_CONTEXT))
            context_size = (context_size + 255) // 256 * 256  # Round to nearest 256
            
            # Build command to create KV cache
            command = f"{CREATE_SCRIPT_PATH} \"{MODEL_PATH}\" \"{temp_file_path}\" \"{kv_cache_path}\" {context_size} {THREADS} {BATCH_SIZE}"
            
            logger.info(f"Creating KV cache: {command}")
            
            # Execute command
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            
            stdout_text = stdout.decode('utf-8')
            stderr_text = stderr.decode('utf-8')
            
            # Log completion
            logger.info(f"KV cache creation completed with exit code: {process.returncode}")
            if stderr_text:
                logger.warning(f"KV cache stderr: {stderr_text}")
            
            # Get the size of the KV cache file if it was created
            kv_cache_size = None
            if process.returncode == 0 and os.path.exists(kv_cache_path):
                kv_cache_size = os.path.getsize(kv_cache_path)
                
                # If this is meant to be the master cache, create a symbolic link or copy
                if 'master' in document_id.lower() or data.get('setAsMaster', False):
                    try:
                        # Copy the file to master_cache.bin
                        master_dir = os.path.dirname(MASTER_KV_CACHE)
                        os.makedirs(master_dir, exist_ok=True)
                        shutil.copy2(kv_cache_path, MASTER_KV_CACHE)
                        logger.info(f"Set {kv_cache_path} as master KV cache at {MASTER_KV_CACHE}")
                    except Exception as e:
                        logger.error(f"Failed to set as master KV cache: {str(e)}")
            
            # Clean up temp file
            try:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    logger.info(f"Cleaned up temp file: {temp_file_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp file: {str(e)}")
            
            # Send response
            response = {
                'success': process.returncode == 0,
                'documentId': document_id,
                'kvCachePath': kv_cache_path,
                'kvCacheSize': kv_cache_size,
                'contextSize': context_size,
                'error': stderr_text if process.returncode != 0 else None,
                'output': stdout_text
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Error creating KV cache: {str(e)}", exc_info=True)
            error_response = {'success': False, 'error': str(e)}
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(error_response).encode('utf-8'))
            
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b"CAG Bridge Server Running")
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            # Check for issues
            issues = check_files()
            health_data = {
                'status': 'unhealthy' if issues else 'healthy',
                'issues': issues,
                'config': {
                    'master_kv_cache': MASTER_KV_CACHE,
                    'model_path': MODEL_PATH,
                    'query_script': QUERY_SCRIPT_PATH,
                    'create_script': CREATE_SCRIPT_PATH,
                    'max_context': MAX_CONTEXT,
                    'threads': THREADS,
                    'batch_size': BATCH_SIZE
                }
            }
            self.wfile.write(json.dumps(health_data).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def run_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, CAGHandler)
    
    # Check file existence at startup
    issues = check_files()
    if issues:
        for issue in issues:
            logger.warning(issue)
        logger.warning("Bridge started with issues. The service may not work correctly.")
    
    logger.info(f"Starting CAG Bridge Server on port {port}")
    logger.info(f"Using model: {MODEL_PATH}")
    logger.info(f"Using query script: {QUERY_SCRIPT_PATH}")
    logger.info(f"Using create script: {CREATE_SCRIPT_PATH}")
    logger.info(f"Master KV cache path: {MASTER_KV_CACHE}")
    logger.info(f"Context size: {MAX_CONTEXT}")
    logger.info(f"Threads: {THREADS}")
    logger.info(f"Batch size: {BATCH_SIZE}")
    logger.info("Bridge server is ready to accept requests")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    finally:
        httpd.server_close()
        logger.info("Server closed")

if __name__ == '__main__':
    run_server(int(os.environ.get('CAG_BRIDGE_PORT', '8000')))