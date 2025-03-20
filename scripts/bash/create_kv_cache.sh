#!/bin/bash
# This script creates a KV cache from a document chunk, optimized for large context window models
# Usage: ./create_kv_cache.sh <model_path> <chunk_file> <cache_file>

# Source the config file if it exists
if [ -f ~/cag_project/config.sh ]; then
  source ~/cag_project/config.sh
fi

# Get parameters
MODEL_PATH=${1:-$LLAMACPP_MODEL_PATH}
CHUNK_FILE=$2
CACHE_FILE=$3

# Check files exist
if [ ! -f "$CHUNK_FILE" ]; then
  echo "Error: Chunk file not found: $CHUNK_FILE"
  exit 1
fi

if [ ! -f "$MODEL_PATH" ]; then
  echo "Error: Model file not found: $MODEL_PATH"
  exit 1
fi

# Create directory for cache if it doesn't exist
mkdir -p "$(dirname "$CACHE_FILE")"

# Get max context from environment or use default large context
MAX_CONTEXT=${LLAMACPP_MAX_CONTEXT:-128000}

# Calculate an appropriate context size based on chunk size
# For large context window models, we want to use as much context as possible
CHUNK_SIZE=$(wc -c < "$CHUNK_FILE")
TOKEN_ESTIMATE=$((CHUNK_SIZE / 4)) # Rough estimate: 4 chars per token
CTX_SIZE=$(( TOKEN_ESTIMATE < 2048 ? 2048 : TOKEN_ESTIMATE + 256 ))
CTX_SIZE=$(( CTX_SIZE > MAX_CONTEXT ? MAX_CONTEXT : CTX_SIZE )) # Cap at maximum context

# Get number of threads from environment or use default
THREADS=${LLAMACPP_THREADS:-4}

echo "Creating KV cache for document: $CHUNK_FILE"
echo "Using model: $MODEL_PATH"
echo "Output KV cache: $CACHE_FILE"
echo "Context size: $CTX_SIZE tokens (estimated from $CHUNK_SIZE bytes)"
echo "Using $THREADS threads"

# Run llama.cpp to create the KV cache with appropriate parameters for large context
$LLAMACPP_PATH/build/bin/main \
  -m "$MODEL_PATH" \
  -f "$CHUNK_FILE" \
  --save-kv-cache "$CACHE_FILE" \
  --max-tokens 1 \
  --ctx-size "$CTX_SIZE" \
  --threads "$THREADS" \
  --no-mmap \
  --memory-f32 \
  --batch-size 1024 2>&1

# Check if cache was created successfully
if [ -f "$CACHE_FILE" ]; then
  CACHE_SIZE=$(du -h "$CACHE_FILE" | cut -f1)
  echo "Success! KV cache created: $CACHE_SIZE"
  echo "Document is now stored in KV cache and ready for queries"
  exit 0
else
  echo "Error: Failed to create KV cache"
  exit 1
fi
