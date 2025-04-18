"""
Flask-Limiter optimized configuration for production
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os

def init_limiter(app):
    """Initialize the rate limiter with optimized Redis settings"""
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
