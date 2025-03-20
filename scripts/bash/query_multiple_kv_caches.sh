#!/bin/bash
# Enhanced script for querying multiple KV caches with better handling and formatting
# Usage: ./query_multiple_kv_caches.sh <model_path> <query> <max_tokens> [temperature] <cache_file1> [<cache_file2> ...]

# Source the config file if it exists
if [ -f ~/cag_project/config.sh ]; then
  source ~/cag_project/config.sh
fi

# Get parameters
MODEL_PATH=${1:-$LLAMACPP_MODEL_PATH}
QUERY="$2"
MAX_TOKENS=${3:-1024}
TEMP_SETTING=${4:-0.7}

# Check if fourth parameter is a temperature setting or a cache file
if [[ $TEMP_SETTING == --temp* ]]; then
  TEMPERATURE=$(echo $TEMP_SETTING | sed 's/--temp //')
  shift 4
else
  TEMPERATURE=0.7
  shift 3
fi

# Get threads and context size from environment or use defaults
THREADS=${LLAMACPP_THREADS:-4}
MAX_CONTEXT=${LLAMACPP_MAX_CONTEXT:-128000}

# Performance monitoring
START_TIME=$(date +%s)

# Check we have at least one cache file
if [ $# -lt 1 ]; then
  echo "Error: At least one cache file must be provided"
  echo "Usage: ./query_multiple_kv_caches.sh <model_path> <query> <max_tokens> [--temp <temperature>] <cache_file1> [<cache_file2> ...]"
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

# Create a unique run ID
RUN_ID=$(date +%s%N | md5sum | head -c 8)

# Log file for this operation
LOG_FILE="/tmp/multiple_kv_query_${RUN_ID}.log"

echo "=== STARTING MULTIPLE KV CACHE QUERY ($RUN_ID) ===" > "$LOG_FILE"
echo "Date: $(date)" >> "$LOG_FILE"
echo "Model: $MODEL_PATH" >> "$LOG_FILE"
echo "Query: $QUERY" >> "$LOG_FILE"
echo "Max tokens: $MAX_TOKENS" >> "$LOG_FILE"
echo "Temperature: $TEMPERATURE" >> "$LOG_FILE"
echo "Cache files: $@" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Process query
echo "Query: $QUERY"
echo "Using large context window model: $(basename "$MODEL_PATH")"
echo "Context size: $MAX_CONTEXT tokens"
echo "Max response tokens: $MAX_TOKENS"
echo "Temperature: $TEMPERATURE"
echo "Using $(echo $@ | wc -w) different context caches"

# Create separate output for citations
CITATION_FILE="$TEMP_DIR/citations.txt"
echo "Sources:" > "$CITATION_FILE"

# Process each cache file
echo "Processing individual caches..."

for CACHE_FILE in "$@"; do
  # Check the cache file exists
  if [ ! -f "$CACHE_FILE" ]; then
    echo "Warning: Cache file not found, skipping: $CACHE_FILE"
    continue
  fi
  
  # Extract cache info for citation
  CACHE_NAME=$(basename "$CACHE_FILE")
  DOCUMENT_NAME=$(echo "$CACHE_NAME" | sed 's/_chunk[0-9]*\.bin//')
  SECTION_ID=$(echo "$CACHE_NAME" | grep -o 'chunk[0-9]*' || echo "section")
  
  # Add to citations
  echo "- $DOCUMENT_NAME ($SECTION_ID)" >> "$CITATION_FILE"
  
  # Get context from this cache (limited to smaller output)
  echo "- Processing cache: $CACHE_FILE" | tee -a "$LOG_FILE"
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
    --temp "$TEMPERATURE" \
    --top-p 0.9 > "$CACHE_OUTPUT" 2>>"$LOG_FILE"
  
  # Record usage for tracking
  echo "TRACK_USAGE:$CACHE_FILE:$(date +%s)" >> "$LOG_FILE"
  
  # Add to combined output with separator
  echo "======= Information from $(basename "$CACHE_FILE") =======" >> "$COMBINED_OUTPUT"
  cat "$CACHE_OUTPUT" >> "$COMBINED_OUTPUT"
  echo "" >> "$COMBINED_OUTPUT"
done

# Generate comprehensive prompt with all context information
echo "Generating comprehensive response from large context window model..." | tee -a "$LOG_FILE"
FIRST_CACHE=$1
PROMPT=$(cat <<EOF
Based on the following information extracted from documents, please answer this query:

Query: $QUERY

Document Extracts:
$(cat "$COMBINED_OUTPUT")

Please provide a complete and accurate answer based only on the information above.
Reference specific sections if possible.
EOF
)

# Create a temporary prompt file (safer handling of quotes/special chars)
PROMPT_FILE="$TEMP_DIR/prompt.txt"
echo "$PROMPT" > "$PROMPT_FILE"

# Run llama.cpp with the first KV cache and the combined prompt
$LLAMACPP_PATH/build/bin/main \
  -m "$MODEL_PATH" \
  --load-kv-cache "$FIRST_CACHE" \
  --ctx-size "$MAX_CONTEXT" \
  --threads "$THREADS" \
  --no-mmap \
  --memory-f32 \
  --temp "$TEMPERATURE" \
  --repeat-penalty 1.1 \
  --top-p 0.9 \
  -f "$PROMPT_FILE" \
  -n "$MAX_TOKENS" | tee "$TEMP_DIR/final_output.txt"

# Append citations if final output doesn't already include them
if ! grep -q "Sources:" "$TEMP_DIR/final_output.txt"; then
  echo "" 
  cat "$CITATION_FILE"
fi

# Performance stats
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
echo "" >> "$LOG_FILE"
echo "=== COMPLETED MULTIPLE KV CACHE QUERY ===" >> "$LOG_FILE"
echo "Elapsed time: $ELAPSED seconds" >> "$LOG_FILE"

# Clean up
rm -rf "$TEMP_DIR"