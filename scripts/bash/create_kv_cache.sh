#!/bin/bash
# Enhanced script for creating KV caches with better error handling and monitoring
# Usage: ./create_kv_cache.sh <model_path> <chunk_file> <cache_file> [ctx_size] [threads] [batch_size]

# Source the config file if it exists
if [ -f ~/cag_project/config.sh ]; then
  source ~/cag_project/config.sh
fi

# Get parameters
MODEL_PATH=${1:-$LLAMACPP_MODEL_PATH}
CHUNK_FILE=$2
CACHE_FILE=$3
CTX_SIZE=${4:-${LLAMACPP_MAX_CONTEXT:-128000}}
THREADS=${5:-${LLAMACPP_THREADS:-4}}
BATCH_SIZE=${6:-${LLAMACPP_BATCH_SIZE:-1024}}

# Log start time for performance monitoring
START_TIME=$(date +%s)

# Check files exist with better error reporting
if [ ! -f "$CHUNK_FILE" ]; then
  echo "Error: Chunk file not found: $CHUNK_FILE"
  exit 1
fi

if [ ! -f "$MODEL_PATH" ]; then
  echo "Error: Model file not found: $MODEL_PATH"
  echo "Tried looking for: $MODEL_PATH"
  echo "Current directory: $(pwd)"
  exit 1
fi

# Create directory for cache if it doesn't exist
mkdir -p "$(dirname "$CACHE_FILE")"

# Get file size to validate input
CHUNK_SIZE=$(wc -c < "$CHUNK_FILE")
if [ "$CHUNK_SIZE" -eq 0 ]; then
  echo "Error: Chunk file is empty: $CHUNK_FILE"
  exit 1
fi

# Estimate token count (approximate 4 chars per token)
TOKEN_ESTIMATE=$((CHUNK_SIZE / 4))

# If no context size provided, calculate an appropriate size
if [ -z "$4" ]; then
  # For large context window models, we want to use as much context as possible
  CTX_SIZE=$(( TOKEN_ESTIMATE < 2048 ? 2048 : TOKEN_ESTIMATE + 256 ))
  CTX_SIZE=$(( CTX_SIZE > LLAMACPP_MAX_CONTEXT ? LLAMACPP_MAX_CONTEXT : CTX_SIZE )) # Cap at maximum
fi

echo "Creating KV cache for document: $CHUNK_FILE"
echo "Using model: $MODEL_PATH"
echo "Output KV cache: $CACHE_FILE"
echo "Context size: $CTX_SIZE tokens (estimated from $CHUNK_SIZE bytes)"
echo "Using $THREADS threads and batch size $BATCH_SIZE"

# Create a unique ID for this run
RUN_ID=$(date +%s%N | md5sum | head -c 8)

# Create a log file for this operation
LOG_FILE="/tmp/kvcache_${RUN_ID}.log"

# Run llama.cpp with resource monitoring
(
echo "=== STARTING KV CACHE CREATION ($RUN_ID) ===" > "$LOG_FILE"
echo "Date: $(date)" >> "$LOG_FILE"
echo "Model: $MODEL_PATH" >> "$LOG_FILE"
echo "Input: $CHUNK_FILE" >> "$LOG_FILE"
echo "Output: $CACHE_FILE" >> "$LOG_FILE"
echo "Context: $CTX_SIZE tokens" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Monitor memory and CPU usage during processing (optional)
if command -v top >/dev/null 2>&1; then
  # Start memory monitoring in background
  (
    echo "=== RESOURCE MONITORING ===" >> "$LOG_FILE"
    while true; do
      top -b -n 1 | head -n 20 >> "$LOG_FILE" 2>&1
      sleep 5
    done
  ) & 
  MONITOR_PID=$!
  trap "kill $MONITOR_PID 2>/dev/null" EXIT
fi

# Run llama.cpp with enhanced parameters
# Added logging of stderr separately to better diagnose issues
$LLAMACPP_PATH/build/bin/main \
  -m "$MODEL_PATH" \
  -f "$CHUNK_FILE" \
  --save-kv-cache "$CACHE_FILE" \
  --max-tokens 1 \
  --ctx-size "$CTX_SIZE" \
  --threads "$THREADS" \
  --batch-size "$BATCH_SIZE" \
  --no-mmap \
  --memory-f32 2>> "$LOG_FILE"

RESULT=$?

# Stop resource monitoring if running
if [ -n "$MONITOR_PID" ]; then
  kill $MONITOR_PID 2>/dev/null || true
fi

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo "" >> "$LOG_FILE"
echo "=== COMPLETED KV CACHE CREATION ===" >> "$LOG_FILE"
echo "Elapsed time: $ELAPSED seconds" >> "$LOG_FILE"
echo "Exit code: $RESULT" >> "$LOG_FILE"

# Check if cache was created successfully
if [ -f "$CACHE_FILE" ]; then
  CACHE_SIZE=$(du -h "$CACHE_FILE" | cut -f1)
  echo "Success! KV cache created: $CACHE_SIZE in $ELAPSED seconds" | tee -a "$LOG_FILE"
  echo "Document is now stored in KV cache and ready for queries" | tee -a "$LOG_FILE"
  exit 0
else
  echo "Error: Failed to create KV cache after $ELAPSED seconds" | tee -a "$LOG_FILE"
  echo "Check detailed logs at: $LOG_FILE" | tee -a "$LOG_FILE"
  exit 1
fi
) 2>&1

# Pass through the exit code of the subshell
exit $?