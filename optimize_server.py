#!/usr/bin/env python3
"""
Web Framework Optimization Script

This script implements the recommended optimizations for the Flask/Gunicorn/Redis stack
while ensuring that we can revert to the previous working state if needed.
"""

import os
import sys
import shutil
import subprocess
import json
import time
from datetime import datetime
import argparse

# Configuration for backup and optimization
BACKUP_DIR = "./config_backups"
REQUIREMENTS_FILE = "./requirements.txt"
APP_FILE = "./app.py"
FLASK_LIMITER_CONFIG_FILE = "./travel_agent/config/limiter_config.py"

def create_backup(tag=None):
    """Create a backup of the current configuration files"""
    if not tag:
        tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    backup_path = os.path.join(BACKUP_DIR, tag)
    os.makedirs(backup_path, exist_ok=True)
    
    # Backup key files
    if os.path.exists(REQUIREMENTS_FILE):
        shutil.copy2(REQUIREMENTS_FILE, os.path.join(backup_path, os.path.basename(REQUIREMENTS_FILE)))
    
    if os.path.exists(APP_FILE):
        shutil.copy2(APP_FILE, os.path.join(backup_path, os.path.basename(APP_FILE)))
    
    # Create config directories if they don't exist
    os.makedirs(os.path.dirname(FLASK_LIMITER_CONFIG_FILE), exist_ok=True)
    
    # Save metadata about the current configuration
    metadata = {
        "backup_time": datetime.now().isoformat(),
        "tag": tag,
        "python_version": sys.version,
        "files_backed_up": [REQUIREMENTS_FILE, APP_FILE]
    }
    
    with open(os.path.join(backup_path, "metadata.json"), 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Backup created at {backup_path}")
    return backup_path

def restore_backup(tag):
    """Restore from a previous backup"""
    backup_path = os.path.join(BACKUP_DIR, tag)
    
    if not os.path.exists(backup_path):
        print(f"Backup {tag} not found")
        return False
    
    # Restore key files
    if os.path.exists(os.path.join(backup_path, os.path.basename(REQUIREMENTS_FILE))):
        shutil.copy2(os.path.join(backup_path, os.path.basename(REQUIREMENTS_FILE)), REQUIREMENTS_FILE)
    
    if os.path.exists(os.path.join(backup_path, os.path.basename(APP_FILE))):
        shutil.copy2(os.path.join(backup_path, os.path.basename(APP_FILE)), APP_FILE)
    
    print(f"Restored from backup {tag}")
    return True

def create_limiter_config():
    """Create an optimized Flask-Limiter configuration file"""
    config_dir = os.path.dirname(FLASK_LIMITER_CONFIG_FILE)
    os.makedirs(config_dir, exist_ok=True)
    
    config_content = """\"\"\"
Flask-Limiter optimized configuration for production
\"\"\"

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os

def init_limiter(app):
    \"\"\"Initialize the rate limiter with optimized Redis settings\"\"\"
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    limiter = Limiter(
        get_remote_address,
        app=app,
        storage_uri=redis_url,
        storage_options={
            "socket_connect_timeout": 30,
            "socket_timeout": 30,
            "retry_on_timeout": True,
            "health_check_interval": 30
        },
        strategy="moving-window",  # More precise than fixed-window
        default_limits=["100 per day", "20 per hour"],
        headers_enabled=True,      # Enable X-RateLimit headers
        swallow_errors=True,       # Don't fail if Redis is temporarily unavailable
    )
    return limiter
"""
    
    with open(FLASK_LIMITER_CONFIG_FILE, 'w') as f:
        f.write(config_content)
    
    print(f"Created optimized Flask-Limiter configuration at {FLASK_LIMITER_CONFIG_FILE}")

def optimize_gunicorn_config():
    """Create an optimized Gunicorn configuration file"""
    gunicorn_config_path = "./gunicorn_config.py"
    
    config_content = """\"\"\"
Gunicorn optimized configuration for production
\"\"\"

import multiprocessing

# Recommended formula: (2 * CPU cores) + 1
# For a server with 4 cores, that's 9 workers
workers = multiprocessing.cpu_count() * 2 + 1

# Use the recommended worker type for CPU-bound applications
worker_class = 'sync'

# For long-running requests, set a reasonable timeout
timeout = 60

# Bind to 0.0.0.0 to accept connections from any source
bind = '0.0.0.0:5001'  # Using port 5001 to avoid conflicts with AirPlay

# Configure logging
accesslog = 'access.log'
errorlog = 'error.log'
loglevel = 'info'

# Enable forwarded headers if behind a proxy
forwarded_allow_ips = '127.0.0.1'  # Adjust based on your proxy setup

# Graceful reload
graceful_timeout = 10
max_requests = 1000
max_requests_jitter = 50

# Preload application to save memory
preload_app = True
"""
    
    with open(gunicorn_config_path, 'w') as f:
        f.write(config_content)
    
    print(f"Created optimized Gunicorn configuration at {gunicorn_config_path}")

def test_application():
    """Test the application to ensure it's working correctly"""
    print("Testing application...")
    
    # Test 1: Check if Redis is running
    try:
        subprocess.run(["redis-cli", "ping"], capture_output=True, text=True, check=True)
        print("✅ Redis is running")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Redis is not running or redis-cli not found")
        return False
    
    # Test 2: Check if application starts
    try:
        # Start the app in the background for testing
        process = subprocess.Popen(
            ["python", APP_FILE],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Give it a moment to start
        time.sleep(2)
        
        # Check if process is still running (if it crashed, it would terminate)
        if process.poll() is None:
            print("✅ Application started successfully")
            
            # Make a request to the app
            try:
                health_check = subprocess.run(
                    ["curl", "-s", "http://localhost:5001/health"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                print(f"✅ Health check response: {health_check.stdout.strip()}")
            except subprocess.CalledProcessError:
                print("❌ Health check failed")
                
            # Terminate the app
            process.terminate()
            process.wait(timeout=5)
        else:
            stdout, stderr = process.communicate()
            print(f"❌ Application failed to start: {stderr.decode('utf-8')}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing application: {str(e)}")
        return False
    
    print("Application tests completed")
    return True

def main():
    parser = argparse.ArgumentParser(description="Optimize and test Flask/Gunicorn/Redis configuration")
    parser.add_argument('--optimize', action='store_true', help='Apply optimizations')
    parser.add_argument('--backup', action='store_true', help='Create a backup of current config')
    parser.add_argument('--restore', help='Restore from backup with given tag')
    parser.add_argument('--test', action='store_true', help='Test the application')
    args = parser.parse_args()
    
    # Create backup directory if it doesn't exist
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    if args.backup:
        create_backup()
        
    if args.restore:
        restore_backup(args.restore)
        
    if args.optimize:
        # First create a backup with a specific tag
        backup_tag = f"pre_optimization_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        create_backup(backup_tag)
        print(f"Created backup before optimization with tag: {backup_tag}")
        
        # Apply optimizations
        create_limiter_config()
        optimize_gunicorn_config()
        
        print("\nOptimizations applied. To revert, run:")
        print(f"python {sys.argv[0]} --restore {backup_tag}")
    
    if args.test:
        test_application()
    
    if not any([args.optimize, args.backup, args.restore, args.test]):
        parser.print_help()

if __name__ == "__main__":
    main()
