#!/usr/bin/env python3
"""
Setup script for llama-cag-n8n

This script handles the initial installation and configuration
of the llama-cag-n8n system including dependencies and downloading
a large context window model.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
import shutil
import logging
import dotenv
import re

# Load environment variables
dotenv.load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Define default paths relative to the project root
DEFAULT_LLAMACPP_PATH = 'models/llama.cpp'
DEFAULT_MODEL_PATH = 'models/gemma-4b.gguf'
DEFAULT_KV_CACHE_DIR = 'kv_caches'
DEFAULT_TEMP_DIR = 'temp_chunks'
DEFAULT_DOCUMENTS_FOLDER = 'documents'
DEFAULT_PROMPT = "You are a helpful assistant that answers questions based on provided information."

class SetupError(Exception):
    """Custom exception for setup errors"""
    pass

def check_system():
    """Check if running on a supported system and detect processor type"""
    if sys.platform not in ['darwin', 'linux']:
        raise SetupError("This package is only supported on macOS and Linux.")

    is_mac = sys.platform == 'darwin'
    if is_mac:
        try:
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                    capture_output=True, text=True, check=True)
            is_apple_silicon = 'Apple' in result.stdout
        except:
            is_apple_silicon = False  # Default to False if detection fails
        logging.info(f"Detected macOS with {'Apple Silicon' if is_apple_silicon else 'Intel'} processor")
    else:
        logging.info("Detected Linux system")
        is_apple_silicon = False # Not relevant on Linux

    return is_mac, is_apple_silicon

def install_dependencies(is_mac=True):
    """Install required dependencies"""
    logging.info("Installing required dependencies...")

    # Install Homebrew if not present (Mac only)
    if is_mac and not shutil.which('brew'):
        logging.info("Installing Homebrew...")
        try:
            subprocess.run('/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
                          shell=True, check=True)
        except subprocess.CalledProcessError as e:
            raise SetupError(f"Failed to install Homebrew: {str(e)}")

    # Install required tools on Mac
    if is_mac:
        try:
            # Check for existing tools
            to_install = []
            for tool in ['cmake', 'gcc', 'make', 'git', 'python3', 'curl']:
                if not shutil.which(tool):
                    to_install.append(tool)

            if to_install:
                logging.info(f"Installing tools: {', '.join(to_install)}")
                subprocess.run(f"brew install {' '.join(to_install)}", shell=True, check=True)
            else:
                logging.info("All required tools are already installed")
        except subprocess.CalledProcessError as e:
            raise SetupError(f"Failed to install dependencies: {str(e)}")
    else:
        # Linux dependencies
        try:
            # Check if apt-get is available
            if shutil.which('apt-get'):
                subprocess.run("apt-get update", shell=True, check=True)
                subprocess.run("apt-get install -y build-essential cmake git curl python3 python3-pip",
                              shell=True, check=True)
            else:
                logging.warning("apt-get not found. Please manually install: build-essential, cmake, git, curl, python3, python3-pip")
        except subprocess.CalledProcessError as e:
            logging.warning(f"Failed to install some dependencies: {str(e)}")
            logging.warning("Please manually install: build-essential, cmake, git, curl, python3")

    # Install Python dependencies
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "psycopg2-binary", "python-dotenv"], check=True)
    except subprocess.CalledProcessError as e:
        logging.warning(f"Failed to install Python dependencies: {str(e)}")

    logging.info("Dependencies installed successfully")

def install_llamacpp(llamacpp_path, no_native=False, update=False):
    """Install or update llama.cpp to the specified path"""

    logging.info(f"Installing llama.cpp to {llamacpp_path}...")

    # Clone repository if it doesn't exist, or update if requested
    if not os.path.exists(llamacpp_path):
        try:
            subprocess.run(f"git clone https://github.com/ggerganov/llama.cpp.git {llamacpp_path}",
                           shell=True, check=True)
        except subprocess.CalledProcessError as e:
            raise SetupError(f"Failed to clone llama.cpp: {str(e)}")
    elif update:
        logging.info("llama.cpp already exists, updating...")
        try:
            subprocess.run(f"cd {llamacpp_path} && git pull", shell=True, check=True)
        except subprocess.CalledProcessError as e:
            logging.warning(f"Failed to update llama.cpp: {str(e)}")

    # Build llama.cpp
    build_path = os.path.join(llamacpp_path, "build")
    if not os.path.exists(build_path):
        os.makedirs(build_path)

    try:
        os.chdir(build_path)
        cmake_command = "cmake .." if not no_native else "cmake .. -DLLAMA_NATIVE=OFF"
        subprocess.run(cmake_command, shell=True, check=True)
        subprocess.run(f"make -j{os.cpu_count() or 4}", shell=True, check=True)
    except subprocess.CalledProcessError as e:
        raise SetupError(f"Failed to build llama.cpp: {str(e)}")

    # Test installation
    main_executable = os.path.join(build_path, "bin", "main")
    if os.path.exists(main_executable):
        logging.info("llama.cpp installed successfully!")
    else:
        raise SetupError("llama.cpp installation failed. Executable not found.")

    # Return to the original directory
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def download_model(model_path, model_name):
    """Download a large context window model to the specified path"""
    models_dir = os.path.dirname(model_path)

    if not os.path.exists(models_dir):
        os.makedirs(models_dir)

    if os.path.exists(model_path):
        logging.info(f"Model already exists at {model_path}, skipping download.")
        return

    # Dictionary of common large context models and their download URLs
    model_urls = {
        "gemma-4b.gguf": "https://huggingface.co/bartowski/gemma-4b-GGUF/resolve/main/gemma-4b-q4_k_m.gguf",
        "deepseek-r1-7b.gguf": "https://huggingface.co/TheBloke/deepseek-r1-7B-GGUF/resolve/main/deepseek-r1-7b.Q4_K_M.gguf",
        "mistral-7b-instruct-v0.2.gguf": "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
        "llama3-8b.gguf": "https://huggingface.co/TheBloke/Llama-3-8B-GGUF/resolve/main/llama-3-8b.Q4_K_M.gguf"
    }

    # Find the best match for the model name
    best_match = None
    best_match_score = 0
    for known_model in model_urls.keys():
        match_score = sum(c1 == c2 for c1, c2 in zip(model_name.lower(), known_model.lower()))
        if match_score > best_match_score:
            best_match = known_model
            best_match_score = match_score

    if best_match and best_match_score > len(best_match) / 2:
        download_url = model_urls[best_match]
        logging.info(f"Found matching model: {best_match}")
        logging.info(f"Downloading {best_match} (this may take a while)...")

        try:
            subprocess.run(f"curl -L -C - -o {model_path} {download_url} --progress-bar --fail --retry 5 --retry-delay 5", 
                          shell=True, check=True)
            logging.info(f"Model downloaded successfully to {model_path}!")
        except subprocess.CalledProcessError as e:
            raise SetupError(f"Failed to download model: {str(e)}. Check your internet connection.")
    else:
        logging.warning(f"Unknown model: {model_name}. Please download it manually to {model_path}")
        logging.info("Recommended large context window models:")
        for model, url in model_urls.items():
            logging.info(f"  - {model} ({url})")

def setup_project_folders(kv_cache_dir, temp_dir, docs_dir):
    """Setup project folders relative to the project root"""
    project_root = os.getcwd()

    logging.info(f"Setting up project folders relative to: {project_root}")

    folders = [
        kv_cache_dir,
        temp_dir,
        docs_dir,
        os.path.join(project_root, "scripts", "bash")
    ]

    for folder in folders:
        full_path = os.path.join(project_root, folder)
        if not os.path.exists(full_path):
            os.makedirs(full_path)
            logging.info(f"Created folder: {full_path}")

    logging.info("Project folders created.")

    # Copy scripts to project folder
    src_scripts = os.path.join(project_root, "scripts", "bash")
    dest_scripts = os.path.join(project_root, "scripts", "bash")

    script_files = [
        "create_kv_cache.sh",
        "query_kv_cache.sh",
        "query_multiple_kv_caches.sh"
    ]

    for script in script_files:
        src = os.path.join(src_scripts, script)
        dest = os.path.join(dest_scripts, script)

        if os.path.exists(src):
            shutil.copy2(src, dest)
            os.chmod(dest, 0o755)
            logging.info(f"Copied script: {script}")
        else:
            logging.warning(f"Script not found: {src}")

    # Create default prompt cache
    default_prompt_path = os.path.join(project_root, kv_cache_dir, "default_prompt.bin")
    if not os.path.exists(default_prompt_path):
        logging.info(f"Creating default prompt KV cache at {default_prompt_path}")
        try:
            temp_prompt_file = os.path.join(project_root, temp_dir, "default_prompt.txt")
            with open(temp_prompt_file, 'w') as f:
                f.write(os.getenv('DEFAULT_PROMPT', DEFAULT_PROMPT))

            model_path = os.path.expanduser(os.getenv('LLAMACPP_MODEL_PATH', DEFAULT_MODEL_PATH))
            create_kv_cache_script = os.path.join(src_scripts, "create_kv_cache.sh")
            
            if os.path.exists(create_kv_cache_script):
                cmd = f"bash {create_kv_cache_script} \"{model_path}\" \"{temp_prompt_file}\" \"{default_prompt_path}\""
                subprocess.run(cmd, shell=True, check=True)
                logging.info("Default prompt KV cache created successfully.")
            else:
                logging.warning("Create KV cache script not found")

            os.remove(temp_prompt_file)
        except Exception as e:
            logging.warning(f"Failed to create default prompt KV cache: {str(e)}")

def setup_environment():
    """Setup environment variables"""
    env_example = os.path.join(os.getcwd(), '.env.example')
    env_path = os.path.join(os.getcwd(), '.env')

    if not os.path.exists(env_path):
        shutil.copy(env_example, env_path)
        logging.info("Created .env file from template")
        logging.info("⚠️ IMPORTANT: Edit the .env file to set passwords and secrets!")

    else:
        with open(env_path, 'r') as f:
            env_content = f.read()

        if any(x in env_content for x in [
            'DB_PASSWORD=your_secure_password_here',
            'N8N_ENCRYPTION_KEY=your-secure-encryption-key',
            'N8N_USER_MANAGEMENT_JWT_SECRET=your-jwt-secret']):
            logging.warning("⚠️ YOUR .env FILE CONTAINS DEFAULT VALUES THAT NEED TO BE CHANGED!")
