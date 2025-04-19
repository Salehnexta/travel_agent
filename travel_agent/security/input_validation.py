"""
Module for input validation and sanitization in the travel agent application.
Implements defense-in-depth approach with comprehensive input validation.
"""

import re
import logging
import html
from typing import Dict, Any, Optional, Union, List, Tuple
import json
from functools import wraps
from flask import request, jsonify, Response

# Configure logging
logger = logging.getLogger(__name__)

class InputValidator:
    """Validates and sanitizes user input to prevent injection attacks."""
    
    # Regular expressions for validation
    PATTERNS = {
        'session_id': re.compile(r'^[a-zA-Z0-9_-]{1,64}$'),
        'message': re.compile(r'^[\s\S]{1,2000}$'),  # Allow any characters but limit length
        'email': re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'),
        'alpha': re.compile(r'^[a-zA-Z]+$'),
        'alphanumeric': re.compile(r'^[a-zA-Z0-9]+$'),
        'numeric': re.compile(r'^[0-9]+$'),
        'airport_code': re.compile(r'^[A-Z]{3}$'),
    }
    
    @classmethod
    def validate_pattern(cls, value: str, pattern_name: str) -> bool:
        """
        Validate a string against a predefined pattern.
        
        Args:
            value: The string to validate
            pattern_name: Name of the pattern to validate against
            
        Returns:
            bool: True if valid, False otherwise
        """
        if pattern_name not in cls.PATTERNS:
            logger.warning(f"Unknown validation pattern: {pattern_name}")
            return False
            
        return bool(cls.PATTERNS[pattern_name].match(value))
    
    @classmethod
    def sanitize_html(cls, value: str) -> str:
        """
        Sanitize string by escaping HTML special characters.
        
        Args:
            value: String to sanitize
            
        Returns:
            Sanitized string
        """
        return html.escape(value)
    
    @classmethod
    def validate_json(cls, data: Any) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Validate that input is proper JSON and has expected structure.
        
        Args:
            data: Data to validate
            
        Returns:
            Tuple of (is_valid, parsed_data)
        """
        if not isinstance(data, dict):
            return False, None
            
        return True, data
    
    @classmethod
    def validate_message_request(cls, data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, str]]]:
        """
        Validate a message request.
        
        Args:
            data: Request data to validate
            
        Returns:
            Tuple of (is_valid, error_message, sanitized_data)
        """
        if not data or not isinstance(data, dict):
            return False, "Invalid request format", None
            
        # Check required fields
        if 'message' not in data:
            return False, "Message is required", None
            
        message = data.get('message', '')
        
        # Validate message
        if not isinstance(message, str):
            return False, "Message must be a string", None
            
        if not cls.validate_pattern(message, 'message'):
            return False, "Message format is invalid or too long", None
        
        # Sanitize inputs
        sanitized_message = cls.sanitize_html(message)
        
        # Return sanitized data
        return True, None, {'message': sanitized_message}
    
    @classmethod
    def validate_session_id(cls, session_id: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a session ID.
        
        Args:
            session_id: Session ID to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not session_id:
            return False, "Session ID is required"
            
        if not cls.validate_pattern(session_id, 'session_id'):
            return False, "Invalid session ID format"
            
        return True, None

# Flask validation decorators
def validate_json_request(f):
    """Decorator to validate that the request contains valid JSON."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            logger.warning("Request content type is not application/json")
            return jsonify({"error": "Content-Type must be application/json"}), 415
            
        try:
            data = request.get_json()
        except Exception as e:
            logger.warning(f"Invalid JSON in request: {str(e)}")
            return jsonify({"error": "Invalid JSON in request"}), 400
            
        is_valid, parsed_data = InputValidator.validate_json(data)
        if not is_valid:
            return jsonify({"error": "Invalid JSON structure"}), 400
            
        return f(*args, **kwargs)
    return decorated_function

def validate_message_request(f):
    """Decorator to validate message requests."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        data = request.get_json()
        
        is_valid, error, sanitized_data = InputValidator.validate_message_request(data)
        if not is_valid:
            return jsonify({"error": error}), 400
            
        # Replace request.json with sanitized data
        request.sanitized_data = sanitized_data
        
        return f(*args, **kwargs)
    return decorated_function

def validate_session_id(f):
    """Decorator to validate session IDs in URL parameters."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = kwargs.get('session_id')
        
        is_valid, error = InputValidator.validate_session_id(session_id)
        if not is_valid:
            return jsonify({"error": error}), 400
            
        return f(*args, **kwargs)
    return decorated_function
