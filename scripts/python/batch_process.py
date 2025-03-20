#!/usr/bin/env python3
"""
Batch process documents for llama-cag-n8n

This script processes multiple documents in a directory,
copying them to the watched folder for processing by n8n.
"""

import os
import sys
import argparse
import shutil
import time
from pathlib import Path
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('batch_process.log')
    ]
)

def load_env():
    """Load environment variables from .env file"""
    env_vars = {}
    env_path = Path('.env')
    
    if not env_path.exists():
        env_path = Path('../.env')
    
    if not env_path.exists():
        logging.warning("No .env file found. Using default paths.")
        return {
            'DOCUMENTS_FOLDER': os.path.expanduser('~/Documents/cag_documents')
        }
    
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key] = value.strip('"\'')
    
    return env_vars

def process_documents(source_dir, extension=None, limit=None, delay=2):
    """
    Process documents from source directory
    
    Args:
        source_dir: Source directory containing documents
        extension: Only process files with this extension
        limit: Maximum number of files to process
        delay: Delay between files in seconds
    """
    env_vars = load_env()
    target_dir = os.path.expanduser(env_vars.get('DOCUMENTS_FOLDER', '~/Documents/cag_documents'))
    
    # Ensure target directory exists
    os.makedirs(target_dir, exist_ok=True)
    
    # Find files to process
    source_path = Path(source_dir).expanduser()
    if not source_path.exists():
        logging.error(f"Source directory not found: {source_path}")
        return False
    
    # Get list of files with optional extension filter
    files = list(source_path.glob(f"*.{extension}" if extension else "*"))
    files = [f for f in files if f.is_file()]
    
    if not files:
        logging.warning(f"No matching files found in {source_path}")
        return False
    
    # Apply limit if specified
    if limit and len(files) > limit:
        logging.info(f"Limiting to {limit} files from {len(files)} available")
        files = files[:limit]
    
    logging.info(f"Found {len(files)} files to process")
    
    # Process each file
    for i, file_path in enumerate(files):
        try:
            logging.info(f"Processing [{i+1}/{len(files)}]: {file_path.name}")
            
            # Create target filename with timestamp to avoid conflicts
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            target_file = Path(target_dir) / f"{timestamp}_{file_path.name}"
            
            # Copy file to target directory
            shutil.copy2(file_path, target_file)
            logging.info(f"Copied to {target_file}")
            
            # Wait before processing next file
            if i < len(files) - 1:
                logging.info(f"Waiting {delay} seconds before next file...")
                time.sleep(delay)
                
        except Exception as e:
            logging.error(f"Error processing {file_path.name}: {str(e)}")
    
    logging.info(f"Batch processing complete. {len(files)} files copied to {target_dir}")
    return True

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Batch process documents for llama-cag-n8n')
    parser.add_argument('--dir', '-d', required=True, help='Source directory containing documents')
    parser.add_argument('--extension', '-e', help='Only process files with this extension')
    parser.add_argument('--limit', '-l', type=int, help='Maximum number of files to process')
    parser.add_argument('--delay', type=int, default=2, help='Delay between files in seconds')
    
    args = parser.parse_args()
    
    success = process_documents(
        args.dir,
        extension=args.extension,
        limit=args.limit,
        delay=args.delay
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()