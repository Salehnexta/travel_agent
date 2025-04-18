"""
Gunicorn optimized configuration for production
"""

import multiprocessing

# Recommended formula: (2 * CPU cores) + 1
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
