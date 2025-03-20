#!/usr/bin/env python3
"""
List KV caches for llama-cag-n8n

This script lists all KV caches in the system, including
usage statistics from the database.
"""

import os
import sys
import argparse
import psycopg2
from pathlib import Path
from datetime import datetime, timedelta
import logging
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
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
            'LLAMACPP_KV_CACHE_DIR': os.path.expanduser('~/cag_project/kv_caches'),
            'DB_HOST': 'localhost',
            'DB_PORT': '5432',
            'DB_NAME': 'llamacag',
            'DB_USER': 'llamacag',
            'DB_PASSWORD': 'llamacag'
        }
    
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key] = value.strip('"\'')
    
    return env_vars

def get_db_connection(env_vars):
    """Get a database connection"""
    try:
        conn = psycopg2.connect(
            host=env_vars.get('DB_HOST', 'localhost'),
            port=env_vars.get('DB_PORT', '5432'),
            database=env_vars.get('DB_NAME', 'llamacag'),
            user=env_vars.get('DB_USER', 'llamacag'),
            password=env_vars.get('DB_PASSWORD', 'llamacag')
        )
        return conn
    except Exception as e:
        logging.error(f"Error connecting to database: {str(e)}")
        return None

def list_caches(sort_by='document', days=None, unused_only=False, format_json=False):
    """
    List KV caches in the system
    
    Args:
        sort_by: Sort by 'document', 'size', 'date', or 'usage'
        days: Only show caches used within this many days
        unused_only: Only show caches that have never been used
        format_json: Output in JSON format
    """
    env_vars = load_env()
    cache_dir = os.path.expanduser(env_vars.get('LLAMACPP_KV_CACHE_DIR', '~/cag_project/kv_caches'))
    
    # Get cache files from filesystem
    cache_path = Path(cache_dir)
    if not cache_path.exists():
        logging.error(f"Cache directory not found: {cache_path}")
        return False
    
    # Find all .bin files recursively
    cache_files = list(cache_path.glob("**/*.bin"))
    logging.info(f"Found {len(cache_files)} cache files in {cache_path}")
    
    # Get cache information from database
    conn = get_db_connection(env_vars)
    if not conn:
        logging.warning("Could not connect to database. Showing limited information.")
        db_info = {}
    else:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT kv_cache_path, document_id, file_name, chunk_id, 
                   last_used, usage_count, created_at, section_title
            FROM cag_document_registry
            WHERE kv_cache_path IS NOT NULL
        """)
        rows = cursor.fetchall()
        conn.close()
        
        # Create a lookup dictionary
        db_info = {}
        for row in rows:
            cache_path, doc_id, file_name, chunk_id, last_used, usage_count, created_at, section = row
            db_info[os.path.basename(cache_path)] = {
                'document_id': doc_id,
                'file_name': file_name,
                'chunk_id': chunk_id,
                'last_used': last_used,
                'usage_count': usage_count or 0,
                'created_at': created_at,
                'section': section
            }
    
    # Process and collect cache information
    cache_info = []
    for cache_file in cache_files:
        cache_name = cache_file.name
        size_bytes = cache_file.stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        
        # Get database info if available
        info = db_info.get(cache_name, {})
        doc_id = info.get('document_id', 'unknown')
        file_name = info.get('file_name', 'unknown')
        last_used = info.get('last_used')
        usage_count = info.get('usage_count', 0)
        created_at = info.get('created_at', mtime)
        section = info.get('section', '')
        
        # Skip if filtering by days and last_used is outside the range
        if days is not None and last_used:
            cutoff_date = datetime.now() - timedelta(days=days)
            if last_used < cutoff_date:
                continue
        
        # Skip if filtering for unused and this has been used
        if unused_only and usage_count > 0:
            continue
        
        cache_info.append({
            'cache_file': str(cache_file),
            'cache_name': cache_name,
            'document_id': doc_id,
            'file_name': file_name,
            'section': section,
            'size_mb': size_mb,
            'created_at': created_at,
            'last_used': last_used,
            'usage_count': usage_count
        })
    
    # Sort the results
    if sort_by == 'document':
        cache_info.sort(key=lambda x: (x['document_id'], x['file_name']))
    elif sort_by == 'size':
        cache_info.sort(key=lambda x: x['size_mb'], reverse=True)
    elif sort_by == 'date':
        cache_info.sort(key=lambda x: x['created_at'], reverse=True)
    elif sort_by == 'usage':
        cache_info.sort(key=lambda x: x['usage_count'], reverse=True)
    
    # Output the results
    if format_json:
        # Clean datetime objects for JSON serialization
        for cache in cache_info:
            if cache['created_at']:
                cache['created_at'] = cache['created_at'].isoformat()
            if cache['last_used']:
                cache['last_used'] = cache['last_used'].isoformat()
        print(json.dumps(cache_info, indent=2))
    else:
        # Print human-readable format
        print(f"{'Document':30} {'File':30} {'Section':20} {'Size (MB)':10} {'Usage':5} {'Last Used'}")
        print("-" * 120)
        for cache in cache_info:
            last_used = cache['last_used'].strftime('%Y-%m-%d') if cache['last_used'] else 'Never'
            print(f"{cache['document_id'][:30]:30} {cache['file_name'][:30]:30} {cache['section'][:20]:20} {cache['size_mb']:.2f}MB {cache['usage_count']:5} {last_used}")
        
        print("-" * 120)
        print(f"Total caches: {len(cache_info)} ({sum(c['size_mb'] for c in cache_info):.2f}MB)")
    
    return True

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='List KV caches for llama-cag-n8n')
    parser.add_argument('--sort', choices=['document', 'size', 'date', 'usage'], default='document',
                        help='Sort caches by document, size, date, or usage')
    parser.add_argument('--days', type=int, help='Only show caches used within this many days')
    parser.add_argument('--unused', action='store_true', help='Only show caches that have never been used')
    parser.add_argument('--json', action='store_true', help='Output in JSON format')
    
    args = parser.parse_args()
    
    success = list_caches(
        sort_by=args.sort,
        days=args.days,
        unused_only=args.unused,
        format_json=args.json
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()