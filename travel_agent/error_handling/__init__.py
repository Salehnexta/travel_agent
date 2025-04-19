"""
Enhanced error handling system for the travel agent application.
Provides centralized error tracking, logging, and fallback mechanisms.
"""

import logging
import os
import sys
import time
import traceback
import uuid
import json
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union, Tuple

# Set up file logging
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

ERROR_LOG_PATH = os.path.join(LOG_DIR, 'error.log')
DEBUG_LOG_PATH = os.path.join(LOG_DIR, 'debug.log')

# Configure root logger with rotating file handler
from logging.handlers import RotatingFileHandler

# Create formatters
VERBOSE_FORMATTER = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - [%(error_id)s] - %(message)s'
)
ERROR_FORMATTER = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - [%(error_id)s] - %(message)s\n'
    'Context: %(context)s\n'
    '%(traceback)s\n'
)

# Create handlers
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(VERBOSE_FORMATTER)
console_handler.setLevel(logging.INFO)

error_file_handler = RotatingFileHandler(
    ERROR_LOG_PATH, maxBytes=10*1024*1024, backupCount=5
)
error_file_handler.setFormatter(ERROR_FORMATTER)
error_file_handler.setLevel(logging.WARNING)

debug_file_handler = RotatingFileHandler(
    DEBUG_LOG_PATH, maxBytes=10*1024*1024, backupCount=5
)
debug_file_handler.setFormatter(VERBOSE_FORMATTER)
debug_file_handler.setLevel(logging.DEBUG)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(console_handler)
root_logger.addHandler(error_file_handler)
root_logger.addHandler(debug_file_handler)

# Component loggers
llm_logger = logging.getLogger('travel_agent.llm')
search_logger = logging.getLogger('travel_agent.search')
parameter_logger = logging.getLogger('travel_agent.parameter')
redis_logger = logging.getLogger('travel_agent.redis')
api_logger = logging.getLogger('travel_agent.api')
state_logger = logging.getLogger('travel_agent.state')
security_logger = logging.getLogger('travel_agent.security')

# Error ID format: ERROR-{COMPONENT}-{RANDOM}-{TIMESTAMP}
def generate_error_id(component: str = "general") -> str:
    """
    Generate a unique error ID that's both human readable and traceable.
    
    Args:
        component: The component where the error occurred
        
    Returns:
        A unique error ID string
    """
    random_part = uuid.uuid4().hex[:6].upper()
    timestamp = int(time.time())
    return f"E-{component[:3].upper()}-{random_part}-{timestamp}"

# Enhanced error tracking with centralized reporting
class EnhancedErrorTracker:
    """
    Enhanced error tracking that provides comprehensive context and reporting.
    
    Features:
    - Unique error IDs with component context
    - Structured error logging with JSON formatting
    - Error severity classification
    - Client-friendly error messages
    - Integration with monitoring systems (placeholder)
    """
    
    # Error severity levels
    SEVERITY = {
        "CRITICAL": 5,  # System is unusable
        "ERROR": 4,     # Operation failed
        "WARNING": 3,   # Potentially problematic but operation continued
        "INFO": 2,      # Important information
        "DEBUG": 1      # Debug details
    }
    
    def __init__(self, component: str = "general"):
        """
        Initialize error tracker for a specific component.
        
        Args:
            component: The component name
        """
        self.component = component
        self.logger = logging.getLogger(f'travel_agent.{component}')
        
        # In-memory cache of recent errors for quick lookup
        # Limited to 100 most recent errors
        self.recent_errors = []
        self.max_recent_errors = 100
    
    def _format_error_context(self, error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format error context for structured logging.
        
        Args:
            error: The exception
            context: Additional context
            
        Returns:
            Structured error context
        """
        tb = traceback.format_exc() if error else ""
        
        # Default context with standardized fields
        error_context = {
            "component": self.component,
            "timestamp": datetime.now().isoformat(),
            "traceback": tb,
        }
        
        # Add error details if available
        if error:
            error_context.update({
                "error_type": type(error).__name__,
                "error_message": str(error),
            })
        
        # Add user-provided context
        if context:
            # Filter out any sensitive information like API keys
            safe_context = {
                k: ("***REDACTED***" if "key" in k.lower() or "token" in k.lower() else v)
                for k, v in context.items()
            }
            error_context["user_context"] = safe_context
        
        return error_context

    def track_error(self, 
                   error: Optional[Exception] = None, 
                   context: Dict[str, Any] = None,
                   severity: str = "ERROR",
                   user_message: str = None,
                   notify: bool = False) -> str:
        """
        Track an error with complete context for later analysis.
        
        Args:
            error: The exception that occurred (optional)
            context: Additional context information
            severity: Error severity (CRITICAL, ERROR, WARNING, INFO, DEBUG)
            user_message: User-friendly error message
            notify: Whether to trigger notifications
            
        Returns:
            error_id: Unique ID for the error
        """
        # Generate unique error ID
        error_id = generate_error_id(self.component)
        
        # Normalize severity
        severity = severity.upper()
        if severity not in self.SEVERITY:
            severity = "ERROR"
        
        # Format the error context
        error_context = self._format_error_context(error, context)
        error_context["error_id"] = error_id
        error_context["severity"] = severity
        
        # Create a user-friendly message if not provided
        if not user_message and error:
            user_message = f"An error occurred in the {self.component} component. Error ID: {error_id}"
        
        error_context["user_message"] = user_message
        
        # Store recent error
        self._store_recent_error(error_id, error_context)
        
        # Log with appropriate level
        log_level = getattr(logging, severity)
        self.logger.log(
            log_level,
            f"{error_context.get('error_type', 'Issue')}: {error_context.get('error_message', user_message)}",
            extra={
                "error_id": error_id,
                "context": json.dumps(error_context, default=str),
                "traceback": error_context.get("traceback", "")
            }
        )
        
        # Notification logic for critical errors
        if notify or severity == "CRITICAL":
            self._notify_error(error_id, error_context)
        
        return error_id
    
    def _store_recent_error(self, error_id: str, error_context: Dict[str, Any]) -> None:
        """
        Store recent error in memory for quick lookup.
        
        Args:
            error_id: The unique error ID
            error_context: Error context information
        """
        self.recent_errors.append((error_id, error_context))
        
        # Keep only the most recent errors
        if len(self.recent_errors) > self.max_recent_errors:
            self.recent_errors.pop(0)
    
    def get_error(self, error_id: str) -> Optional[Dict[str, Any]]:
        """
        Get error details by ID from recent errors cache.
        
        Args:
            error_id: The error ID to look up
            
        Returns:
            Error context or None if not found
        """
        for eid, context in self.recent_errors:
            if eid == error_id:
                return context
        return None
    
    def _notify_error(self, error_id: str, error_context: Dict[str, Any]) -> None:
        """
        Notify team of critical errors (placeholder for integration).
        
        Args:
            error_id: The error ID
            error_context: Error context
        """
        # Placeholder for notification system integration
        # This could send to Slack, email, or other alerting systems
        self.logger.critical(
            f"NOTIFICATION: Critical error {error_id} in {self.component}",
            extra={"error_id": error_id}
        )

# Enhanced retry decorator with fallback mechanisms
F = TypeVar('F', bound=Callable[..., Any])

def with_fallback(fallback_function: Optional[Callable[..., Any]] = None,
                 default_return_value: Any = None,
                 component: str = "general",
                 error_message: str = None):
    """
    Decorator to provide fallback mechanism for functions.
    If the function fails, it will try the fallback function or return a default value.
    
    Args:
        fallback_function: Alternative function to call if main function fails
        default_return_value: Default value to return if all else fails
        component: Component name for error tracking
        error_message: User-friendly error message
        
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracker = EnhancedErrorTracker(component)
            
            # Try the main function
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Log the error
                context = {
                    "function": func.__name__,
                    "args": str(args),
                    "kwargs": str(kwargs)
                }
                
                error_id = tracker.track_error(
                    error=e,
                    context=context,
                    user_message=error_message or f"Error in {func.__name__}"
                )
                
                # Try the fallback function if provided
                if fallback_function:
                    try:
                        tracker.logger.info(
                            f"Using fallback for {func.__name__} after error {error_id}",
                            extra={"error_id": error_id}
                        )
                        return fallback_function(*args, **kwargs)
                    except Exception as fallback_error:
                        # Log the fallback error
                        fallback_context = {
                            "original_error_id": error_id,
                            "function": fallback_function.__name__,
                            "args": str(args),
                            "kwargs": str(kwargs)
                        }
                        
                        fallback_error_id = tracker.track_error(
                            error=fallback_error,
                            context=fallback_context,
                            user_message=f"Fallback for {func.__name__} also failed"
                        )
                
                # Return default value if provided
                return default_return_value
        
        return wrapper
    
    return decorator

def retry_with_fallback(max_attempts: int = 3,
                        backoff_factor: float = 1.5,
                        fallback_function: Optional[Callable[..., Any]] = None,
                        default_return_value: Any = None,
                        component: str = "general",
                        error_message: str = None):
    """
    Decorator to retry a function with exponential backoff and fallback.
    
    Args:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Exponential backoff factor
        fallback_function: Alternative function to call if all retries fail
        default_return_value: Default value to return if all else fails
        component: Component name for error tracking
        error_message: User-friendly error message
        
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracker = EnhancedErrorTracker(component)
            last_error = None
            context = {
                "function": func.__name__,
                "args": str(args),
                "kwargs": str(kwargs),
                "max_attempts": max_attempts
            }
            
            # Try the main function with retries
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    
                    # Update context with attempt information
                    retry_context = {**context, "attempt": attempt}
                    
                    # Only log as error on final attempt
                    if attempt == max_attempts:
                        error_id = tracker.track_error(
                            error=e,
                            context=retry_context,
                            user_message=error_message or f"Error in {func.__name__} after {max_attempts} attempts"
                        )
                    else:
                        # Log retries as warnings
                        error_id = tracker.track_error(
                            error=e,
                            context=retry_context,
                            severity="WARNING",
                            user_message=f"Retrying {func.__name__} (attempt {attempt}/{max_attempts})"
                        )
                    
                    # Wait before retrying
                    if attempt < max_attempts:
                        wait_time = backoff_factor ** (attempt - 1)
                        time.sleep(wait_time)
            
            # All retries failed, try fallback
            if fallback_function:
                try:
                    tracker.logger.info(
                        f"Using fallback for {func.__name__} after {max_attempts} failed attempts",
                        extra={"error_id": error_id}
                    )
                    return fallback_function(*args, **kwargs)
                except Exception as fallback_error:
                    # Log the fallback error
                    fallback_context = {
                        "original_error": str(last_error),
                        "function": fallback_function.__name__,
                        "args": str(args),
                        "kwargs": str(kwargs)
                    }
                    
                    tracker.track_error(
                        error=fallback_error,
                        context=fallback_context,
                        user_message=f"Fallback for {func.__name__} also failed"
                    )
            
            # Return default value if provided
            return default_return_value
        
        return wrapper
    
    return decorator

# Create global instances for easy access
error_tracker = EnhancedErrorTracker()

# Custom exceptions for better error classification
class TravelAgentError(Exception):
    """Base exception for all travel agent errors."""
    def __init__(self, message: str, error_id: Optional[str] = None):
        self.error_id = error_id
        super().__init__(message)

class LLMError(TravelAgentError):
    """Error when interacting with LLM services."""
    pass

class SearchError(TravelAgentError):
    """Error when searching for travel information."""
    pass

class ParameterExtractionError(TravelAgentError):
    """Error when extracting parameters from user input."""
    pass

class RedisError(TravelAgentError):
    """Error when interacting with Redis."""
    pass

class StateError(TravelAgentError):
    """Error when managing conversation state."""
    pass

class SecurityError(TravelAgentError):
    """Error related to security features."""
    pass

# Convenience function for Flask error handlers
def handle_error(error: Exception, component: str = "api") -> Tuple[Dict[str, Any], int]:
    """
    Format error response for API endpoints.
    
    Args:
        error: The exception
        component: Component name
        
    Returns:
        JSON response and status code
    """
    tracker = EnhancedErrorTracker(component)
    
    context = {
        "type": type(error).__name__
    }
    
    # Add error_id if it's our custom exception
    if isinstance(error, TravelAgentError) and error.error_id:
        error_id = error.error_id
    else:
        error_id = tracker.track_error(error=error, context=context)
    
    # Determine status code based on error type
    if isinstance(error, LLMError):
        status_code = 502  # Bad Gateway
    elif isinstance(error, SearchError):
        status_code = 503  # Service Unavailable
    elif isinstance(error, ParameterExtractionError):
        status_code = 422  # Unprocessable Entity
    elif isinstance(error, RedisError):
        status_code = 500  # Internal Server Error
    elif isinstance(error, StateError):
        status_code = 500  # Internal Server Error
    elif isinstance(error, SecurityError):
        status_code = 403  # Forbidden
    else:
        status_code = 500  # Default to 500
    
    # Create user-friendly response
    response = {
        "error": type(error).__name__,
        "message": str(error),
        "error_id": error_id
    }
    
    return response, status_code
