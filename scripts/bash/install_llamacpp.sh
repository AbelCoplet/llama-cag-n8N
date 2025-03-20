#!/bin/bash
# This script installs llama.cpp on Mac

# Source environment variables if available
if [ -f .env ]; then
  source .env
fi

# Default paths
LLAMACPP_PATH=${LLAMACPP_PATH:-~/Documents/llama.cpp}
LLAMACPP_PATH=$(eval echo $LLAMACPP_PATH)  # Expand tilde

echo "Installing llama.cpp to $LLAMACPP_PATH"

# Check if required tools are installed
if ! command -v git &> /dev/null; then
    echo "Error: git is not installed. Please install it first."
    exit 1
fi

if ! command -v cmake &> /dev/null; then
    echo "Error: cmake is not installed. Please install it first."
    echo "You can install it with: brew install cmake"
    exit 1
fi

# Clone repository if it doesn't exist
if [ ! -d "$LLAMACPP_PATH" ]; then
    echo "Cloning llama.cpp repository..."
    git clone https://github.com/ggerganov/llama.cpp.git "$LLAMACPP_PATH"
else
    echo "Directory already exists. Updating llama.cpp..."
    cd "$LLAMACPP_PATH"
    git pull
fi

# Build llama.cpp
echo "Building llama.cpp..."
cd "$LLAMACPP_PATH"
mkdir -p build
cd build

# Configure and build
cmake ..
make -j4

# Test if build was successful
if [ -f "./bin/main" ]; then
    echo "llama.cpp successfully installed!"
    echo "You can test it with: $LLAMACPP_PATH/build/bin/main -h"
else
    echo "Error: Build failed. Please check the output for errors."
    exit 1
fi

# Create models directory if it doesn't exist
mkdir -p "$LLAMACPP_PATH/models"

echo "Installation complete!"
echo "To download a model, run:"
echo "curl -L https://huggingface.co/google/gemma-7b-gguf/resolve/main/gemma-7b-q4_0.gguf -o $LLAMACPP_PATH/models/gemma-7b.gguf"