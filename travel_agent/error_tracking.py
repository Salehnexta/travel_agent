"""
Error tracking system for the travel agent application.
This module provides centralized error logging, tracking, and monitoring.
"""

import logging
import os
import sys
import time
import traceback
import uuid
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Union

# Setup base logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('travel_agent_errors.log')
    ]
)

# Create loggers for different components
redis_logger = logging.getLogger('travel_agent.redis')
llm_logger = logging.getLogger('travel_agent.llm')
api_logger = logging.getLogger('travel_agent.api')
state_logger = logging.getLogger('travel_agent.state')
validation_logger = logging.getLogger('travel_agent.validation')

# Setup error ID generator
def generate_error_id() -> str:
    """Generate a unique error ID for tracking"""
    return f"ERR-{uuid.uuid4().hex[:8].upper()}-{int(time.time())}"

class ErrorTracker:
    """Centralized error tracking and reporting"""
    
    def __init__(self, component: str = "general"):
        self.component = component
        self.logger = logging.getLogger(f'travel_agent.{component}')
    
    def track_error(self, 
                  error: Exception, 
                  context: Dict[str, Any] = None, 
                  level: str = "error") -> str:
        """
        Track an error with context information
        
        Args:
            error: The exception that occurred
            context: Additional context information
            level: Logging level (debug, info, warning, error, critical)
            
        Returns:
            error_id: Unique ID for the error
        """
        error_id = generate_error_id()
        
        # Default context
        error_context = {
            "error_id": error_id,
            "component": self.component,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat(),
        }
        
        # Add user context if provided
        if context:
            error_context.update(context)
        
        # Add traceback information
        error_context["traceback"] = traceback.format_exc()
        
        # Log the error with the appropriate level
        log_method = getattr(self.logger, level.lower())
        log_method(f"Error {error_id}: {error}", extra={"error_context": error_context})
        
        return error_id

# Decorator for tracking errors in functions
F = TypeVar('F', bound=Callable[..., Any])
def track_errors(component: str = "general"):
    """Decorator to track errors in functions"""
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracker = ErrorTracker(component)
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Create context with function information
                context = {
                    "function": func.__name__,
                    "args": str(args),
                    "kwargs": str(kwargs)
                }
                error_id = tracker.track_error(e, context)
                raise type(e)(f"{str(e)} (Error ID: {error_id})") from e
        return wrapper
    return decorator

# Define custom exceptions for better error categorization
class RedisConnectionError(Exception):
    """Error when connecting to Redis"""
    pass

class LLMAPIError(Exception):
    """Error when calling LLM API"""
    pass

class ValidationError(Exception):
    """Error during data validation"""
    pass

class StateManagementError(Exception):
    """Error during state management"""
    pass

# Global error tracker instance
error_tracker = ErrorTracker()

# Retry decorator with tracking
def retry_with_tracking(max_attempts: int = 3, 
                        backoff_factor: float = 1.5, 
                        component: str = "general"):
    """Decorator to retry functions with exponential backoff and error tracking"""
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracker = ErrorTracker(component)
            attempts = 0
            last_error = None
            
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    last_error = e
                    
                    # Track the error with retry information
                    context = {
                        "function": func.__name__,
                        "attempt": attempts,
                        "max_attempts": max_attempts,
                        "args": str(args),
                        "kwargs": str(kwargs)
                    }
                    
                    error_id = tracker.track_error(
                        e, 
                        context,
                        level="warning" if attempts < max_attempts else "error"
                    )
                    
                    # If this was the last attempt, re-raise with error ID
                    if attempts >= max_attempts:
                        raise type(e)(f"{str(e)} (Error ID: {error_id})") from e
                    
                    # Otherwise wait and retry
                    wait_time = backoff_factor ** attempts
                    tracker.logger.info(
                        f"Retrying {func.__name__} in {wait_time:.2f}s "
                        f"(attempt {attempts}/{max_attempts}, Error ID: {error_id})"
                    )
                    time.sleep(wait_time)
            
            # This should never happen, but just in case
            raise last_error
        return wrapper
    return decorator
