#!/bin/bash
# This script queries multiple KV caches and combines the results, optimized for large context window models
# Usage: ./query_multiple_kv_caches.sh <model_path> <query> <max_tokens> <cache_file1> [<cache_file2> ...]

# Source the config file if it exists
if [ -f ~/cag_project/config.sh ]; then
  source ~/cag_project/config.sh
fi

# Get parameters
MODEL_PATH=${1:-$LLAMACPP_MODEL_PATH}
QUERY=$2
MAX_TOKENS=${3:-1024}
shift 3

# Get threads and context size from environment or use defaults
THREADS=${LLAMACPP_THREADS:-4}
MAX_CONTEXT=${LLAMACPP_MAX_CONTEXT:-128000}

# Check we have at least one cache file
if [ $# -lt 1 ]; then
  echo "Error: At least one cache file must be provided"
  echo "Usage: ./query_multiple_kv_caches.sh <model_path> <query> <max_tokens> <cache_file1> [<cache_file2> ...]"
  exit 1
fi

if [ ! -f "$MODEL_PATH" ]; then
  echo "Error: Model file not found: $MODEL_PATH"
  exit 1
fi

# Create a temporary directory for working
TEMP_DIR=$(mktemp -d)
COMBINED_OUTPUT="$TEMP_DIR/combined_output.txt"
touch "$COMBINED_OUTPUT"

# Process each cache file
echo "Query: $QUERY"
echo "Using large context window model: $(basename "$MODEL_PATH")"
echo "Context size: $MAX_CONTEXT tokens"
echo "Using caches: $@"
echo "Processing individual caches..."

for CACHE_FILE in "$@"; do
  # Check the cache file exists
  if [ ! -f "$CACHE_FILE" ]; then
    echo "Warning: Cache file not found, skipping: $CACHE_FILE"
    continue
  fi
  
  # Get context from this cache (limited to smaller output)
  echo "- Processing cache: $CACHE_FILE"
  CACHE_OUTPUT="$TEMP_DIR/$(basename "$CACHE_FILE").txt"
  
  # Run llama.cpp with this KV cache, optimized for large context
  $LLAMACPP_PATH/build/bin/main \
    -m "$MODEL_PATH" \
    --load-kv-cache "$CACHE_FILE" \
    -p "$QUERY" \
    -n 512 \
    --ctx-size "$MAX_CONTEXT" \
    --threads "$THREADS" \
    --no-mmap \
    --memory-f32 \
    --temp 0.7 \
    --top-p 0.9 > "$CACHE_OUTPUT" 2>/dev/null
  
  # Record usage for tracking
  echo "TRACK_USAGE:$CACHE_FILE:$(date +%s)"
  
  # Add to combined output with separator
  echo "======= From $(basename "$CACHE_FILE") =======" >> "$COMBINED_OUTPUT"
  cat "$CACHE_OUTPUT" >> "$COMBINED_OUTPUT"
  echo "" >> "$COMBINED_OUTPUT"
done

# Generate a comprehensive final response using the first cache but with context from all
echo "Generating comprehensive response from large context window model..."
FIRST_CACHE=$1
PROMPT=$(cat <<EOF
Based on the following information extracted from large documents, please answer this query:

Query: $QUERY

Document Extracts:
$(cat "$COMBINED_OUTPUT")

Please provide a complete and accurate answer based only on the information above.
Reference specific sections if possible.
EOF
)

# Run llama.cpp with the first KV cache and our new prompt, optimized for large context
$LLAMACPP_PATH/build/bin/main \
  -m "$MODEL_PATH" \
  --load-kv-cache "$FIRST_CACHE" \
  --ctx-size "$MAX_CONTEXT" \
  --threads "$THREADS" \
  --no-mmap \
  --memory-f32 \
  --temp 0.7 \
  --repeat-penalty 1.1 \
  --top-p 0.9 \
  -p "$PROMPT" \
  -n "$MAX_TOKENS"

# Clean up
rm -rf "$TEMP_DIR"
