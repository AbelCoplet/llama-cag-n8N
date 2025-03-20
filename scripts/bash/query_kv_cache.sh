#!/bin/bash
# Enhanced script for querying using a previously created KV cache
# Usage: ./query_kv_cache.sh <model_path> <cache_file> <query> <max_tokens> [--temp <temperature>]

# Source the config file if it exists
if [ -f ~/cag_project/config.sh ]; then
  source ~/cag_project/config.sh
fi

# Get parameters
MODEL_PATH=${1:-$LLAMACPP_MODEL_PATH}
CACHE_FILE=$2
QUERY="$3"
MAX_TOKENS=${4:-1024}
TEMP_SETTING=${5:-"--temp 0.7"}

# Extract temperature value properly
if [[ $TEMP_SETTING == --temp* ]]; then
  TEMPERATURE=$(echo $TEMP_SETTING | sed 's/--temp //')
else
  TEMPERATURE=0.7
fi

# Get threads from environment or use default
THREADS=${LLAMACPP_THREADS:-4}

# Get maximum context size from environment
MAX_CONTEXT=${LLAMACPP_MAX_CONTEXT:-128000}

# Create unique ID for this query
QUERY_ID=$(date +%s%N | md5sum | head -c 8)

# Start time for performance tracking
START_TIME=$(date +%s)

# Create log file
LOG_FILE="/tmp/kv_query_${QUERY_ID}.log"
echo "=== STARTING KV CACHE QUERY ($QUERY_ID) ===" > "$LOG_FILE"
echo "Date: $(date)" >> "$LOG_FILE"
echo "Model: $MODEL_PATH" >> "$LOG_FILE"
echo "Cache: $CACHE_FILE" >> "$LOG_FILE"
echo "Query: $QUERY" >> "$LOG_FILE"
echo "Max tokens: $MAX_TOKENS" >> "$LOG_FILE"
echo "Temperature: $TEMPERATURE" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Check files exist
if [ ! -f "$CACHE_FILE" ]; then
  echo "Error: Cache file not found: $CACHE_FILE" | tee -a "$LOG_FILE"
  exit 1
fi

if [ ! -f "$MODEL_PATH" ]; then
  echo "Error: Model file not found: $MODEL_PATH" | tee -a "$LOG_FILE"
  exit 1
fi

# Check if cache has reasonable size (>1MB for large context)
MIN_SIZE=1000 # KB (1MB)
ACTUAL_SIZE=$(du -k "$CACHE_FILE" | cut -f1)
if [ "$ACTUAL_SIZE" -lt "$MIN_SIZE" ]; then
  echo "Warning: Cache file $CACHE_FILE seems too small for a large context model (size: ${ACTUAL_SIZE}KB)" | tee -a "$LOG_FILE"
fi

echo "Querying using KV cache: $CACHE_FILE"
echo "Using model: $MODEL_PATH"
echo "Context size: $MAX_CONTEXT tokens"
echo "Max response tokens: $MAX_TOKENS"
echo "Temperature: $TEMPERATURE"
echo "Query: $QUERY"

# Create a temporary file for the prompt (better handling of quotes/special chars)
TEMP_DIR=$(mktemp -d)
PROMPT_FILE="$TEMP_DIR/prompt.txt"
echo "$QUERY" > "$PROMPT_FILE"

# Run llama.cpp with the KV cache, optimized for large context
$LLAMACPP_PATH/build/bin/main \
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

RESULT=$?

# Performance stats
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
echo "" >> "$LOG_FILE"
echo "=== COMPLETED KV CACHE QUERY ===" >> "$LOG_FILE"
echo "Elapsed time: $ELAPSED seconds" >> "$LOG_FILE"
echo "Exit code: $RESULT" >> "$LOG_FILE"

# Record usage for tracking
echo "TRACK_USAGE:$CACHE_FILE:$(date +%s)" >> "$LOG_FILE"

# Clean up
rm -rf "$TEMP_DIR"

exit $RESULT