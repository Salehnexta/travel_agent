"""
Security module for the travel agent application.
Provides integrated security features for input validation, rate limiting, and session management.
"""

import logging
from typing import Dict, Any
from flask import Flask
from redis import Redis

from travel_agent.security.input_validation import (
    InputValidator, validate_json_request, 
    validate_message_request, validate_session_id
)
from travel_agent.security.rate_limiter import RateLimiter, rate_limit
from travel_agent.security.session_security import SessionManager, require_valid_session

# Configure logging
logger = logging.getLogger(__name__)

class SecurityManager:
    """Integrated security manager for the travel agent application."""
    
    def __init__(self, app: Flask, redis_client: Redis):
        """
        Initialize security manager with Flask app and Redis client.
        
        Args:
            app: Flask application
            redis_client: Redis client for security features
        """
        self.app = app
        self.redis = redis_client
        
        # Initialize components
        self.input_validator = InputValidator()
        self.rate_limiter = RateLimiter(redis_client)
        self.session_manager = SessionManager(redis_client)
        
        # Log initialization
        logger.info("Security manager initialized")
        
    def secure_chat_endpoint(self, endpoint_function):
        """
        Apply security decorators to chat endpoint.
        
        Args:
            endpoint_function: Flask route function
            
        Returns:
            Decorated function
        """
        # Apply decorators in specific order
        # 1. Rate limiting - first line of defense
        # 2. JSON validation - basic format check
        # 3. Message validation - content validation
        # 4. Session validation - authentication check
        
        decorated = rate_limit(self.rate_limiter, key_type='endpoint', identifier=lambda: 'api/chat')(
            validate_json_request(
                validate_message_request(
                    validate_session_id(
                        require_valid_session(self.session_manager)(
                            endpoint_function
                        )
                    )
                )
            )
        )
        
        return decorated
    
    def apply_security(self):
        """Apply security features to Flask routes."""
        # Apply rate limiting to all routes
        @self.app.before_request
        def global_rate_limit():
            # Skip for static files
            if request.path.startswith('/static'):
                return None
                
            # Apply IP-based rate limiting
            is_limited, _ = self.rate_limiter.is_rate_limited('ip')
            if is_limited:
                return jsonify({'error': 'Rate limit exceeded'}), 429
            
            return None
