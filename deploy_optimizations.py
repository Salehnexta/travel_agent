#!/usr/bin/env python3
"""
Deployment script for the travel agent application.
This script applies the optimizations and tests the application.
"""

import os
import sys
import subprocess
import time
import json
import shutil
from datetime import datetime

def create_backup():
    """Create a backup of the current configuration"""
    backup_dir = "./config_backups"
    tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, tag)
    
    os.makedirs(backup_path, exist_ok=True)
    
    # Files to backup
    files_to_backup = [
        "app.py",
        ".env"
    ]
    
    for file in files_to_backup:
        if os.path.exists(file):
            shutil.copy2(file, os.path.join(backup_path, os.path.basename(file)))
    
    metadata = {
        "backup_time": datetime.now().isoformat(),
        "tag": tag,
        "files_backed_up": files_to_backup
    }
    
    with open(os.path.join(backup_path, "metadata.json"), 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Backup created at {backup_path}")
    return backup_path

def check_redis():
    """Check if Redis is running"""
    try:
        result = subprocess.run(
            ["redis-cli", "ping"], 
            capture_output=True, 
            text=True
        )
        if "PONG" in result.stdout:
            print("✅ Redis is running")
            return True
        else:
            print("❌ Redis is not running properly")
            return False
    except Exception as e:
        print(f"❌ Error checking Redis: {str(e)}")
        return False

def test_app():
    """Test if the application starts correctly"""
    try:
        print("🔄 Starting application for testing...")
        
        # Start the app in the background
        process = subprocess.Popen(
            ["python", "app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Give it a moment to start
        time.sleep(3)
        
        # Check if it's still running
        if process.poll() is None:
            print("✅ Application started successfully")
            
            # Try to access the health endpoint
            health_result = subprocess.run(
                ["curl", "-s", "http://localhost:5001/health"],
                capture_output=True,
                text=True
            )
            
            if "healthy" in health_result.stdout:
                print("✅ Health check passed")
            else:
                print(f"❌ Health check failed: {health_result.stdout}")
            
            # Stop the app
            process.terminate()
            process.wait(timeout=5)
            return True
        else:
            stdout, stderr = process.communicate()
            print(f"❌ Application failed to start: {stderr.decode('utf-8')}")
            return False
    except Exception as e:
        print(f"❌ Error testing application: {str(e)}")
        return False

def test_gunicorn():
    """Test if the application starts with Gunicorn"""
    try:
        print("🔄 Testing application with Gunicorn...")
        
        # Start Gunicorn
        process = subprocess.Popen(
            ["gunicorn", "-c", "gunicorn_config.py", "app:app"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Give it a moment to start
        time.sleep(3)
        
        # Check if it's still running
        if process.poll() is None:
            print("✅ Gunicorn started successfully")
            
            # Try to access the health endpoint
            health_result = subprocess.run(
                ["curl", "-s", "http://localhost:5001/health"],
                capture_output=True,
                text=True
            )
            
            if "healthy" in health_result.stdout:
                print("✅ Gunicorn health check passed")
            else:
                print(f"❌ Gunicorn health check failed: {health_result.stdout}")
            
            # Stop Gunicorn
            process.terminate()
            process.wait(timeout=5)
            return True
        else:
            stdout, stderr = process.communicate()
            print(f"❌ Gunicorn failed to start: {stderr.decode('utf-8')}")
            return False
    except Exception as e:
        print(f"❌ Error testing Gunicorn: {str(e)}")
        return False

def main():
    print("=" * 60)
    print("Travel Agent Optimization Deployment")
    print("=" * 60)
    
    # Create backup
    backup_path = create_backup()
    print(f"Created backup at {backup_path}")
    
    # Check Redis
    if not check_redis():
        print("❌ Redis check failed. Please start Redis before continuing.")
        print("Run 'brew services start redis' or 'sudo systemctl start redis'")
        return False
    
    # Test Flask app
    if not test_app():
        print("❌ Flask app test failed. Optimizations may not be applied correctly.")
        return False
    
    # Test Gunicorn
    if not test_gunicorn():
        print("❌ Gunicorn test failed. Please check gunicorn_config.py")
        print(f"You can restore from backup at {backup_path}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ All tests passed! Optimizations successfully deployed.")
    print("=" * 60)
    print("\nTo run in production mode:")
    print("  gunicorn -c gunicorn_config.py app:app")
    print("\nTo restore from backup if needed:")
    print(f"  cp {backup_path}/app.py ./app.py")
    
    return True

if __name__ == "__main__":
    main()
