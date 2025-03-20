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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

class SetupError(Exception):
    """Custom exception for setup errors"""
    pass

def check_system():
    """Check if running on a supported system"""
    if sys.platform not in ['darwin', 'linux']:
        raise SetupError("This package is only supported on macOS and Linux.")
    
    # Check if on Mac
    is_mac = sys.platform == 'darwin'
    if is_mac:
        # Check if on Apple Silicon
        is_apple_silicon = False
        try:
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], 
                                  capture_output=True, text=True, check=True)
            is_apple_silicon = 'Apple' in result.stdout
        except:
            pass
        
        logging.info(f"Detected macOS with {'Apple Silicon' if is_apple_silicon else 'Intel'} processor")
    else:
        logging.info("Detected Linux system")
    
    return is_mac

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
            subprocess.run("apt-get update", shell=True, check=True)
            subprocess.run("apt-get install -y build-essential cmake git curl python3 python3-pip", 
                          shell=True, check=True)
        except subprocess.CalledProcessError as e:
            logging.warning(f"Failed to install some dependencies: {str(e)}")
            logging.warning("Please manually install: build-essential, cmake, git, curl, python3")
    
    # Install Python dependencies
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "psycopg2-binary", "python-dotenv"], check=True)
    except subprocess.CalledProcessError as e:
        logging.warning(f"Failed to install Python dependencies: {str(e)}")
    
    logging.info("Dependencies installed successfully")

def install_llamacpp():
    """Install llama.cpp"""
    llamacpp_path = os.path.expanduser("~/Documents/llama.cpp")
    
    logging.info(f"Installing llama.cpp to {llamacpp_path}...")
    
    # Clone repository if it doesn't exist
    if not os.path.exists(llamacpp_path):
        try:
            subprocess.run(f"git clone https://github.com/ggerganov/llama.cpp.git {llamacpp_path}", 
                          shell=True, check=True)
        except subprocess.CalledProcessError as e:
            raise SetupError(f"Failed to clone llama.cpp: {str(e)}")
    else:
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
        subprocess.run("cmake .. -DLLAMA_NATIVE=ON", shell=True, check=True)
        subprocess.run("make -j4", shell=True, check=True)
    except subprocess.CalledProcessError as e:
        raise SetupError(f"Failed to build llama.cpp: {str(e)}")
    
    # Test installation
    main_executable = os.path.join(build_path, "bin", "main")
    if os.path.exists(main_executable):
        logging.info("llama.cpp installed successfully!")
    else:
        raise SetupError("llama.cpp installation failed. Executable not found.")
    
    # Return to original directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

def get_model_info():
    """Get model information from .env file"""
    # Load environment variables
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_file):
        dotenv.load_dotenv(env_file)
    
    # Get model path and name
    model_path = os.getenv('LLAMACPP_MODEL_PATH', '~/Documents/llama.cpp/models/gemma-4b.gguf')
    model_name = os.getenv('LLAMACPP_MODEL_NAME', 'gemma-4b.gguf')
    
    # Expand model path
    model_path = os.path.expanduser(model_path)
    
    return model_path, model_name

def download_model():
    """Download a large context window model"""
    model_path, model_name = get_model_info()
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
    
    # Find the best match for the model name in our dictionary
    best_match = None
    best_match_score = 0
    for known_model in model_urls.keys():
        # Simple fuzzy matching - count matching characters
        match_score = sum(c1 == c2 for c1, c2 in zip(model_name.lower(), known_model.lower()))
        if match_score > best_match_score:
            best_match = known_model
            best_match_score = match_score
    
    # If we found a reasonable match
    if best_match and best_match_score > len(best_match) / 2:
        download_url = model_urls[best_match]
        logging.info(f"Found matching model: {best_match}")
        logging.info(f"Downloading {best_match} (this may take a while)...")
        
        try:
            subprocess.run(f"curl -L {download_url} -o {model_path}", shell=True, check=True)
            logging.info(f"Model downloaded successfully to {model_path}!")
        except subprocess.CalledProcessError as e:
            raise SetupError(f"Failed to download model: {str(e)}")
    else:
        logging.warning(f"Unknown model: {model_name}. Please download it manually to {model_path}")
        logging.info("Recommended large context window models:")
        for model, url in model_urls.items():
            logging.info(f"  - {model}")

def setup_project_folders():
    """Setup project folders"""
    # Load environment variables for paths
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_file):
        dotenv.load_dotenv(env_file)
    
    # Get paths from environment or use defaults
    kv_cache_dir = os.getenv('LLAMACPP_KV_CACHE_DIR', '~/cag_project/kv_caches')
    temp_dir = os.getenv('LLAMACPP_TEMP_DIR', '~/cag_project/temp_chunks')
    docs_dir = os.getenv('DOCUMENTS_FOLDER', '~/Documents/cag_documents')
    
    # Expand paths
    kv_cache_dir = os.path.expanduser(kv_cache_dir)
    temp_dir = os.path.expanduser(temp_dir)
    docs_dir = os.path.expanduser(docs_dir)
    project_path = os.path.dirname(kv_cache_dir)
    
    # Create folders
    folders = [
        project_path,
        os.path.join(project_path, "scripts"),
        kv_cache_dir,
        temp_dir,
        docs_dir
    ]
    
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
            logging.info(f"Created folder: {folder}")
    
    logging.info(f"Project folders created")
    
    # Copy scripts to project folder
    src_scripts = os.path.join(os.getcwd(), "scripts", "bash")
    dest_scripts = os.path.join(project_path, "scripts")
    
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
            os.chmod(dest, 0o755)  # Make executable
            logging.info(f"Copied script: {script}")
        else:
            logging.warning(f"Script not found: {src}")
    
    # Create default prompt cache for fallback queries
    default_prompt_path = os.path.join(kv_cache_dir, "default_prompt.bin")
    if not os.path.exists(default_prompt_path):
        logging.info(f"Creating default prompt KV cache at {default_prompt_path}")
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(default_prompt_path), exist_ok=True)
            
            # Create a temporary file with a generic prompt
            temp_prompt_file = os.path.join(temp_dir, "default_prompt.txt")
            os.makedirs(os.path.dirname(temp_prompt_file), exist_ok=True)
            
            with open(temp_prompt_file, 'w') as f:
                f.write("You are a helpful assistant that answers questions based on provided information.")
            
            # Get model path
            model_path = os.path.expanduser(os.getenv('LLAMACPP_MODEL_PATH', '~/Documents/llama.cpp/models/gemma-4b.gguf'))
            
            # Create KV cache using the script
            create_kv_cache_script = os.path.join(src_scripts, "create_kv_cache.sh")
            if os.path.exists(create_kv_cache_script):
                cmd = f"bash {create_kv_cache_script} {model_path} {temp_prompt_file} {default_prompt_path}"
                subprocess.run(cmd, shell=True, check=True)
                logging.info("Default prompt KV cache created successfully")
            else:
                logging.warning(f"Could not create default prompt KV cache: script not found at {create_kv_cache_script}")
            
            # Clean up temp file
            if os.path.exists(temp_prompt_file):
                os.remove(temp_prompt_file)
        except Exception as e:
            logging.warning(f"Failed to create default prompt KV cache: {str(e)}")
            logging.warning("System will still work but fallback queries may not function properly")
    
    # Create config file with settings optimized for large context
    config_path = os.path.join(project_path, "config.sh")
    with open(config_path, 'w') as f:
        f.write(f"""#!/bin/bash
# Configuration for llama-cag-n8n with large context window model

# Model paths
export LLAMACPP_PATH={os.path.expanduser("~/Documents/llama.cpp")}
export LLAMACPP_MODEL_PATH={os.path.expanduser(os.getenv('LLAMACPP_MODEL_PATH', '~/Documents/llama.cpp/models/gemma-4b.gguf'))}

# Project paths
export LLAMACPP_KV_CACHE_DIR={kv_cache_dir}
export LLAMACPP_TEMP_DIR={temp_dir}

# Large context window settings
export LLAMACPP_MAX_CONTEXT={os.getenv('LLAMACPP_MAX_CONTEXT', '128000')}
export LLAMACPP_GPU_LAYERS={os.getenv('LLAMACPP_GPU_LAYERS', '0')}
export LLAMACPP_THREADS={os.getenv('LLAMACPP_THREADS', '4')}
export LLAMACPP_BATCH_SIZE={os.getenv('LLAMACPP_BATCH_SIZE', '1024')}
""")
    
    os.chmod(config_path, 0o755)  # Make executable
    
    logging.info("Configuration file created and optimized for large context window models")

def setup_environment():
    """Setup environment variables"""
    env_example = os.path.join(os.getcwd(), '.env.example')
    env_path = os.path.join(os.getcwd(), '.env')
    
    if not os.path.exists(env_path):
        shutil.copy(env_example, env_path)
        logging.info(f"Created .env file from template")
        logging.info("⚠️ IMPORTANT: You MUST edit the .env file to set passwords and secrets!")
        logging.info(f"Edit the file at: {env_path}")
    else:
        logging.info(".env file already exists")
        
        # Check if critical values are set
        with open(env_path, 'r') as f:
            env_content = f.read()
        
        # Check for default/example values that need to be changed
        if re.search(r'DB_PASSWORD=your_secure_password_here', env_content) or \
           re.search(r'N8N_ENCRYPTION_KEY=your-secure-encryption-key', env_content) or \
           re.search(r'N8N_USER_MANAGEMENT_JWT_SECRET=your-jwt-secret', env_content):
            logging.warning("⚠️ YOUR .env FILE CONTAINS DEFAULT VALUES THAT NEED TO BE CHANGED!")
            logging.warning("Please edit the .env file and set secure passwords and keys")
            logging.warning(f"File location: {env_path}")

def check_docker():
    """Check for Docker installation"""
    if not shutil.which('docker'):
        logging.warning("Docker not found. Please install Docker Desktop.")
        return False
    
    if not shutil.which('docker-compose') and not shutil.which('docker'):
        logging.warning("docker-compose not found. Please install Docker Desktop.")
        return False
    
    # Check if Docker is running
    try:
        subprocess.run(["docker", "info"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        logging.warning("Docker is not running. Please start Docker Desktop.")
        return False
    
    logging.info("Docker detected and running")
    return True

def provide_instructions():
    """Provide instructions for next steps"""
    logging.info("\n" + "="*80)
    logging.info("INSTALLATION COMPLETE - NEXT STEPS")
    logging.info("="*80)
    
    # Get model info
    model_path, model_name = get_model_info()
    
    logging.info(f"\n1. VERIFY YOUR .env FILE")
    logging.info("   Make sure you've set secure values for:")
    logging.info("   - DB_PASSWORD")
    logging.info("   - N8N_ENCRYPTION_KEY")
    logging.info("   - N8N_USER_MANAGEMENT_JWT_SECRET")
    
    logging.info(f"\n2. LARGE CONTEXT WINDOW MODEL")
    logging.info(f"   Model: {model_name}")
    logging.info(f"   Path: {model_path}")
    if not os.path.exists(os.path.expanduser(model_path)):
        logging.info("   ⚠️ Model not found! Download it before starting services.")
    
    logging.info("\n3. START SERVICES")
    logging.info("   Run: python start_services.py --profile cpu")
    
    logging.info("\n4. SET UP n8n (http://localhost:5678)")
    logging.info("   - Create a local account")
    logging.info("   - Import workflows from n8n/workflows/")
    logging.info("   - Configure PostgreSQL credentials (host: db, user: llamacag)")
    logging.info("   - Activate both workflows")
    
    logging.info("\n5. PROCESS DOCUMENTS")
    logging.info("   Place documents in your watch folder:")
    logging.info(f"   {os.path.expanduser(os.getenv('DOCUMENTS_FOLDER', '~/Documents/cag_documents'))}")
    
    logging.info("\nFor more details, refer to the README.md")
    logging.info("="*80)

def main():
    """Main function for llama-cag-n8n setup"""
    parser = argparse.ArgumentParser(description='Setup llama-cag-n8n with large context window model')
    parser.add_argument('--skip-deps', action='store_true', help='Skip dependency installation')
    parser.add_argument('--skip-llama', action='store_true', help='Skip llama.cpp installation')
    parser.add_argument('--skip-model', action='store_true', help='Skip model download')
    parser.add_argument('--update', action='store_true', help='Update existing installation')
    
    args = parser.parse_args()
    
    logging.info("==== llama-cag-n8n Installation ====")
    logging.info("Setting up system with large context window model support (128K tokens)")
    
    try:
        # Setup environment first
        setup_environment()
        
        # Check system
        is_mac = check_system()
        
        # Install dependencies
        if not args.skip_deps:
            install_dependencies(is_mac)
        
        # Install llama.cpp
        if not args.skip_llama:
            install_llamacpp()
        
        # Download model
        if not args.skip_model:
            download_model()
        
        # Setup project folders
        setup_project_folders()
        
        # Check Docker
        has_docker = check_docker()
        if not has_docker:
            logging.warning("Docker is required for n8n and database services")
        
        # Provide instructions
        provide_instructions()
        
    except SetupError as e:
        logging.error(f"Setup failed: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        sys.exit(1)
    
    logging.info("\n==== Installation Complete ====")
    logging.info("Your llama-cag-n8n system with large context window support is now ready to use!")

if __name__ == "__main__":
    main()
