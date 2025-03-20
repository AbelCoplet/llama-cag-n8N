#!/bin/bash
# This script queries using a previously created KV cache, optimized for large context window models
# Usage: ./query_kv_cache.sh <model_path> <cache_file> <query> <max_tokens>

# Source the config file if it exists
if [ -f ~/cag_project/config.sh ]; then
  source ~/cag_project/config.sh
fi

# Get parameters
MODEL_PATH=${1:-$LLAMACPP_MODEL_PATH}
CACHE_FILE=$2
QUERY=$3
MAX_TOKENS=${4:-1024}

# Get threads from environment or use default
THREADS=${LLAMACPP_THREADS:-4}

# Get maximum context size from environment
MAX_CONTEXT=${LLAMACPP_MAX_CONTEXT:-128000}

# Check files exist
if [ ! -f "$CACHE_FILE" ]; then
  echo "Error: Cache file not found: $CACHE_FILE"
  exit 1
fi

if [ ! -f "$MODEL_PATH" ]; then
  echo "Error: Model file not found: $MODEL_PATH"
  exit 1
fi

# Check if cache has reasonable size (>1MB for large context)
MIN_SIZE=1000 # KB (1MB)
ACTUAL_SIZE=$(du -k "$CACHE_FILE" | cut -f1)
if [ "$ACTUAL_SIZE" -lt "$MIN_SIZE" ]; then
  echo "Warning: Cache file $CACHE_FILE seems too small for a large context model (size: ${ACTUAL_SIZE}KB)"
fi

echo "Querying using KV cache: $CACHE_FILE"
echo "Using model: $MODEL_PATH"
echo "Context size: $MAX_CONTEXT tokens"
echo "Max response tokens: $MAX_TOKENS"
echo "Query: $QUERY"

# Run llama.cpp with the KV cache, optimized for large context
$LLAMACPP_PATH/build/bin/main \
  -m "$MODEL_PATH" \
  --load-kv-cache "$CACHE_FILE" \
  -p "$QUERY" \
  -n "$MAX_TOKENS" \
  --ctx-size "$MAX_CONTEXT" \
  --threads "$THREADS" \
  --no-mmap \
  --memory-f32 \
  --temp 0.7 \
  --repeat-penalty 1.1 \
  --top-p 0.9

# Record usage for tracking
echo "TRACK_USAGE:$CACHE_FILE:$(date +%s)"
