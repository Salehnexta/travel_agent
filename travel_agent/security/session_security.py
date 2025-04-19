"""
Session security module for the travel agent application.
Implements secure session management with token rotation and enhanced Redis storage.
"""

import logging
import secrets
import time
from typing import Dict, Any, Optional, Tuple
import json
from functools import wraps
import uuid
from flask import request, jsonify, g, session, Response
from redis import Redis

# Configure logging
logger = logging.getLogger(__name__)

class SessionManager:
    """
    Secure session management with Redis backend and token rotation.
    Implements defense-in-depth approach to protect session data.
    """
    
    def __init__(self, redis_client: Redis):
        """
        Initialize session manager with Redis client.
        
        Args:
            redis_client: Redis client for storing session data
        """
        self.redis = redis_client
        self.session_prefix = "travel_agent:session:"
        self.token_prefix = "travel_agent:token:"
        self.session_expiry = 60 * 60 * 24  # 24 hours
        self.token_expiry = 60 * 60 * 2     # 2 hours
    
    def create_session(self) -> Tuple[str, str]:
        """
        Create a new session with security token.
        
        Returns:
            Tuple of (session_id, access_token)
        """
        # Generate secure random IDs
        session_id = str(uuid.uuid4())
        access_token = secrets.token_urlsafe(32)
        
        # Store token with session reference
        token_key = f"{self.token_prefix}{access_token}"
        self.redis.set(token_key, session_id)
        self.redis.expire(token_key, self.token_expiry)
        
        # Create empty session
        session_key = f"{self.session_prefix}{session_id}"
        session_data = {
            "created_at": int(time.time()),
            "last_access": int(time.time()),
            "ip_address": request.remote_addr,
            "user_agent": request.headers.get("User-Agent", ""),
            "tokens": [access_token]
        }
        
        # Store session data
        self.redis.set(session_key, json.dumps(session_data))
        self.redis.expire(session_key, self.session_expiry)
        
        logger.info(f"Created new session: {session_id}")
        return session_id, access_token
    
    def validate_session(self, session_id: str, access_token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Validate session and token.
        
        Args:
            session_id: Session ID
            access_token: Access token
            
        Returns:
            Tuple of (is_valid, session_data)
        """
        # Check token validity
        token_key = f"{self.token_prefix}{access_token}"
        stored_session_id = self.redis.get(token_key)
        
        if not stored_session_id or stored_session_id.decode() != session_id:
            logger.warning(f"Invalid token for session: {session_id}")
            return False, None
        
        # Get session data
        session_key = f"{self.session_prefix}{session_id}"
        session_json = self.redis.get(session_key)
        
        if not session_json:
            logger.warning(f"Session not found: {session_id}")
            return False, None
        
        try:
            session_data = json.loads(session_json)
        except json.JSONDecodeError:
            logger.error(f"Corrupted session data for: {session_id}")
            return False, None
        
        # Verify token is in session tokens list
        if access_token not in session_data.get("tokens", []):
            logger.warning(f"Token not associated with session: {session_id}")
            return False, None
        
        # Update last access time
        session_data["last_access"] = int(time.time())
        self.redis.set(session_key, json.dumps(session_data))
        self.redis.expire(session_key, self.session_expiry)
        
        # Extend token expiry
        self.redis.expire(token_key, self.token_expiry)
        
        return True, session_data
    
    def rotate_token(self, session_id: str, old_token: str) -> Optional[str]:
        """
        Rotate session token for security.
        
        Args:
            session_id: Session ID
            old_token: Current token to invalidate
            
        Returns:
            New access token or None if session invalid
        """
        # Validate current session
        is_valid, session_data = self.validate_session(session_id, old_token)
        if not is_valid or not session_data:
            return None
        
        # Generate new token
        new_token = secrets.token_urlsafe(32)
        
        # Remove old token
        old_token_key = f"{self.token_prefix}{old_token}"
        self.redis.delete(old_token_key)
        
        # Store new token
        new_token_key = f"{self.token_prefix}{new_token}"
        self.redis.set(new_token_key, session_id)
        self.redis.expire(new_token_key, self.token_expiry)
        
        # Update session tokens list
        tokens = session_data.get("tokens", [])
        if old_token in tokens:
            tokens.remove(old_token)
        tokens.append(new_token)
        
        # Keep only the last 3 tokens
        if len(tokens) > 3:
            tokens = tokens[-3:]
        
        session_data["tokens"] = tokens
        
        # Update session
        session_key = f"{self.session_prefix}{session_id}"
        self.redis.set(session_key, json.dumps(session_data))
        self.redis.expire(session_key, self.session_expiry)
        
        logger.info(f"Rotated token for session: {session_id}")
        return new_token
    
    def invalidate_session(self, session_id: str) -> bool:
        """
        Invalidate a session and all its tokens.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if session was invalidated
        """
        # Get session data
        session_key = f"{self.session_prefix}{session_id}"
        session_json = self.redis.get(session_key)
        
        if not session_json:
            return False
        
        try:
            session_data = json.loads(session_json)
            # Delete all tokens
            for token in session_data.get("tokens", []):
                token_key = f"{self.token_prefix}{token}"
                self.redis.delete(token_key)
            
            # Delete session
            self.redis.delete(session_key)
            logger.info(f"Invalidated session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error invalidating session {session_id}: {str(e)}")
            return False

# Flask decorators for session security
def require_valid_session(session_manager: SessionManager):
    """
    Decorator to require valid session for Flask routes.
    
    Args:
        session_manager: SessionManager instance
        
    Returns:
        Decorated function
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get session ID and token from headers or request
            session_id = request.headers.get("X-Session-ID") or request.args.get("session_id")
            access_token = request.headers.get("X-Access-Token") or request.args.get("access_token")
            
            if not session_id or not access_token:
                return jsonify({"error": "Authentication required"}), 401
            
            # Validate session
            is_valid, session_data = session_manager.validate_session(session_id, access_token)
            if not is_valid:
                return jsonify({"error": "Invalid session"}), 401
            
            # Store session data in Flask g object for access in route
            g.session_id = session_id
            g.session_data = session_data
            
            # Call route handler
            response = f(*args, **kwargs)
            
            # Add new token to response headers for token rotation
            if isinstance(response, Response) and request.method != "GET":
                new_token = session_manager.rotate_token(session_id, access_token)
                if new_token:
                    response.headers["X-New-Access-Token"] = new_token
            
            return response
        return decorated_function
    return decorator
