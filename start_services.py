#!/usr/bin/env python3
"""
Start llama-cag-n8n services

This script starts all services required for the llama-cag-n8n system,
optimized for large context window models up to 128K tokens.
"""

import os
import sys
import argparse
import subprocess
import time
from pathlib import Path
import shutil
import logging
import dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

def check_prerequisites():
    """Check if required tools are installed"""
    required_tools = ['docker', 'git']
    missing_tools = []
    
    for tool in required_tools:
        if shutil.which(tool) is None:
            missing_tools.append(tool)
    
    if missing_tools:
        logging.error(f"Missing required tools: {', '.join(missing_tools)}")
        logging.error("Please install them before continuing.")
        return False
    
    # Check Docker is running
    try:
        subprocess.run(["docker", "info"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        logging.error("Docker is not running. Please start Docker Desktop.")
        return False
    
    return True

def load_env_file():
    """Load environment variables from .env file"""
    env_path = Path('.env')
    if not env_path.exists():
        logging.warning(".env file not found. Creating from template...")
        try:
            shutil.copy('.env.example', '.env')
            logging.info("Created .env file from template.")
            logging.warning("⚠️ IMPORTANT: Please edit .env file with secure passwords and keys!")
            return {}
        except Exception as e:
            logging.error(f"Failed to create .env file: {str(e)}")
            return {}
    
    # Load variables into environment
    dotenv.load_dotenv(env_path)
    env_vars = {}
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key] = value.strip('"\'')
    
    return env_vars

def setup_project_folders(env_vars):
    """Ensure project folders exist"""
    folders = [
        env_vars.get('LLAMACPP_KV_CACHE_DIR', '~/cag_project/kv_caches'),
        env_vars.get('LLAMACPP_TEMP_DIR', '~/cag_project/temp_chunks'),
        env_vars.get('DOCUMENTS_FOLDER', '~/Documents/cag_documents')
    ]
    
    for folder in folders:
        folder_path = Path(os.path.expanduser(folder))
        if not folder_path.exists():
            logging.info(f"Creating folder: {folder_path}")
            try:
                folder_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logging.error(f"Failed to create folder {folder_path}: {str(e)}")
                continue
    
    return True

def check_llamacpp(env_vars):
    """Check if llama.cpp is installed, offer to install if not"""
    llamacpp_path = Path(os.path.expanduser(env_vars.get('LLAMACPP_PATH', '~/Documents/llama.cpp')))
    
    if not llamacpp_path.exists():
        logging.warning(f"llama.cpp not found at {llamacpp_path}")
        response = input("Would you like to install llama.cpp now? (y/n): ")
        
        if response.lower() == 'y':
            logging.info("Installing llama.cpp...")
            install_script = Path('./scripts/bash/install_llamacpp.sh')
            if install_script.exists():
                try:
                    subprocess.run(['bash', str(install_script)], check=True)
                    logging.info("llama.cpp installation complete")
                except subprocess.CalledProcessError as e:
                    logging.error(f"llama.cpp installation failed: {str(e)}")
                    return False
            else:
                logging.error(f"Installation script not found at {install_script}")
                return False
        else:
            logging.warning("Please install llama.cpp manually and update your .env file.")
            return False
    
    # Check for llama.cpp build
    build_path = llamacpp_path / 'build' / 'bin' / 'main'
    if not build_path.exists():
        logging.warning(f"llama.cpp executable not found at {build_path}")
        logging.warning("Please build llama.cpp manually or re-run the installation script.")
        return False
    
    return True

def check_model(env_vars):
    """Check if the model exists, offer to download if not"""
    model_path = Path(os.path.expanduser(env_vars.get('LLAMACPP_MODEL_PATH', '~/Documents/llama.cpp/models/gemma-4b.gguf')))
    model_name = env_vars.get('LLAMACPP_MODEL_NAME', 'gemma-4b.gguf')
    
    if not model_path.exists():
        logging.warning(f"Large context window model not found at {model_path}")
        response = input(f"Would you like to download the {model_name} model now? (y/n): ")
        
        if response.lower() == 'y':
            logging.info("Downloading model (this may take a while)...")
            model_dir = model_path.parent
            if not model_dir.exists():
                model_dir.mkdir(parents=True, exist_ok=True)
            
            # Dictionary of common large context window models and their download URLs
            model_urls = {
                "gemma-4b.gguf": "https://huggingface.co/bartowski/gemma-4b-GGUF/resolve/main/gemma-4b-q4_k_m.gguf",
                "deepseek-r1-7b.gguf": "https://huggingface.co/TheBloke/deepseek-r1-7B-GGUF/resolve/main/deepseek-r1-7b.Q4_K_M.gguf",
                "mistral-7b-instruct-v0.2.gguf": "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
                "llama3-8b.gguf": "https://huggingface.co/TheBloke/Llama-3-8B-GGUF/resolve/main/llama-3-8b.Q4_K_M.gguf"
            }
            
            # Find best match for model name
            best_match = None
            best_match_score = 0
            for known_model in model_urls.keys():
                match_score = sum(c1 == c2 for c1, c2 in zip(model_name.lower(), known_model.lower()))
                if match_score > best_match_score:
                    best_match = known_model
                    best_match_score = match_score
            
            if best_match and best_match_score > len(best_match) / 2:
                download_url = model_urls[best_match]
                try:
                    subprocess.run(['curl', '-L', download_url, '-o', str(model_path)], check=True)
                    logging.info("Model downloaded successfully!")
                except subprocess.CalledProcessError as e:
                    logging.error(f"Model download failed: {str(e)}")
                    logging.info("Please download a large context window model manually. Options:")
                    for model, url in model_urls.items():
                        logging.info(f"- {model}: {url}")
                    return False
            else:
                logging.error(f"Unknown model: {model_name}")
                logging.info("Please download a large context window model manually. Options:")
                for model, url in model_urls.items():
                    logging.info(f"- {model}: {url}")
                return False
        else:
            logging.warning("Please download the model manually and update your .env file.")
            return False
    
    logging.info(f"Using large context window model: {model_name}")
    return True

def create_config_sh(env_vars):
    """Create config.sh file for bash scripts, optimized for large context window models"""
    config_path = Path(os.path.expanduser('~/cag_project/config.sh'))
    config_dir = config_path.parent
    
    if not config_dir.exists():
        logging.info(f"Creating config directory: {config_dir}")
        config_dir.mkdir(parents=True, exist_ok=True)
    
    logging.info(f"Creating config file with large context window settings: {config_path}")
    
    with open(config_path, 'w') as f:
        f.write(f"""#!/bin/bash

# llama.cpp paths
export LLAMACPP_PATH={env_vars.get('LLAMACPP_PATH', '~/Documents/llama.cpp')}
export LLAMACPP_MODEL_PATH={env_vars.get('LLAMACPP_MODEL_PATH', '~/Documents/llama.cpp/models/gemma-4b.gguf')}

# Project paths
export LLAMACPP_KV_CACHE_DIR={env_vars.get('LLAMACPP_KV_CACHE_DIR', '~/cag_project/kv_caches')}
export LLAMACPP_TEMP_DIR={env_vars.get('LLAMACPP_TEMP_DIR', '~/cag_project/temp_chunks')}

# Large context window settings - 128K tokens
export LLAMACPP_MAX_CONTEXT={env_vars.get('LLAMACPP_MAX_CONTEXT', '128000')}
export LLAMACPP_GPU_LAYERS={env_vars.get('LLAMACPP_GPU_LAYERS', '0')}
export LLAMACPP_THREADS={env_vars.get('LLAMACPP_THREADS', '4')}
export LLAMACPP_BATCH_SIZE={env_vars.get('LLAMACPP_BATCH_SIZE', '1024')}
""")
    
    # Make executable
    os.chmod(config_path, 0o755)
    logging.info("Config file created with 128K context window settings")
    return True

def start_services(use_gpu=False):
    """Start services with docker-compose"""
    env_vars = load_env_file()
    
    # Additional env vars for GPU if requested
    if use_gpu and env_vars.get('CONFIG_PROFILE', 'cpu') == 'gpu-nvidia':
        env_vars['LLAMACPP_GPU_LAYERS'] = '33'  # Default for GPU
        logging.info("Starting services with GPU support for large context window model (NVIDIA only)")
    else:
        env_vars['LLAMACPP_GPU_LAYERS'] = '0'  # CPU only
        logging.info("Starting services with CPU only for large context window model")
    
    # Write env vars to environment for docker-compose
    for key, value in env_vars.items():
        os.environ[key] = value
    
    # Make sure scripts are executable
    script_dir = Path('./scripts/bash')
    if script_dir.exists():
        for script in script_dir.glob('*.sh'):
            os.chmod(script, 0o755)
    
    # Start services with docker-compose
    logging.info("Starting services with docker-compose...")
    try:
        subprocess.run(['docker', 'compose', 'up', '-d'], check=True)
        logging.info("Services started successfully!")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to start services: {str(e)}")
        return False
    
    # Wait for services to be fully up
    logging.info("Waiting for services to be ready...")
    time.sleep(5)
    
    model_name = env_vars.get('LLAMACPP_MODEL_NAME', 'gemma-4b.gguf')
    context_size = env_vars.get('LLAMACPP_MAX_CONTEXT', '128000')
    
    logging.info("\n" + "="*80)
    logging.info(f"LLAMA-CAG-N8N IS RUNNING WITH LARGE CONTEXT WINDOW MODEL")
    logging.info("="*80)
    logging.info(f"Model: {model_name}")
    logging.info(f"Context Size: {context_size} tokens")
    logging.info("\nAccess points:")
    logging.info("• n8n: http://localhost:5678")
    logging.info("• Database: localhost:5432")
    logging.info("\nNext steps:")
    logging.info("1. Import workflows from n8n/workflows/ to n8n")
    logging.info("2. Configure PostgreSQL credential in n8n (host: db)")
    logging.info("3. Place large documents in your watch folder:")
    logging.info(f"   {os.path.expanduser(env_vars.get('DOCUMENTS_FOLDER', '~/Documents/cag_documents'))}")
    logging.info("4. Use the API to query your documents")
    logging.info("="*80)
    
    return True

def stop_services():
    """Stop all services"""
    logging.info("Stopping services...")
    try:
        subprocess.run(['docker', 'compose', 'down'], check=True)
        logging.info("Services stopped successfully")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to stop services: {str(e)}")
        return False

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Start llama-cag-n8n services with large context window model support')
    parser.add_argument('--gpu', action='store_true', 
                        help='Enable GPU support (Linux with NVIDIA GPU only)')
    parser.add_argument('--stop', action='store_true', 
                        help='Stop all services')
    parser.add_argument('--profile', choices=['cpu', 'gpu-nvidia'], default='cpu',
                        help='Profile to use (default: cpu)')
    
    args = parser.parse_args()
    
    # Check if we just need to stop services
    if args.stop:
        success = stop_services()
        sys.exit(0 if success else 1)
    
    # Check prerequisites
    if not check_prerequisites():
        sys.exit(1)
    
    # Load environment variables
    env_vars = load_env_file()
    
    # Set context window to a large value by default if not already set
    if 'LLAMACPP_MAX_CONTEXT' not in env_vars:
        env_vars['LLAMACPP_MAX_CONTEXT'] = '128000'
        os.environ['LLAMACPP_MAX_CONTEXT'] = '128000'
    
    # Set gpu layers based on profile
    use_gpu = args.profile == 'gpu-nvidia' or args.gpu
    if use_gpu:
        os.environ['LLAMACPP_GPU_LAYERS'] = '33'
    
    # Setup project folders
    if not setup_project_folders(env_vars):
        sys.exit(1)
    
    # Create config.sh for bash scripts
    if not create_config_sh(env_vars):
        sys.exit(1)
    
    # Check llama.cpp installation
    if not check_llamacpp(env_vars):
        sys.exit(1)
    
    # Check model
    if not check_model(env_vars):
        sys.exit(1)
    
    # Start services
    success = start_services(use_gpu=use_gpu)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
