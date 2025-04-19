"""
Integration module for error handling system.
Provides functions to integrate error handling into the Flask application.
"""

import logging
import functools
import traceback
from typing import Dict, Any, Callable
from flask import Flask, jsonify, render_template, request, g, current_app

from travel_agent.error_handling import (
    EnhancedErrorTracker, error_tracker, 
    retry_with_fallback, with_fallback, handle_error,
    LLMError, SearchError, ParameterExtractionError, 
    RedisError, StateError, SecurityError
)
from travel_agent.error_handling.monitoring import error_monitor, register_monitoring_routes
from travel_agent.error_handling.fallbacks import FallbackService

# Configure logging
logger = logging.getLogger('travel_agent.error_integration')

def setup_error_handling(app: Flask) -> None:
    """
    Set up error handling for Flask application.
    
    Args:
        app: Flask application
    """
    # Register error handlers
    @app.errorhandler(Exception)
    def handle_exception(e):
        """Handle all unhandled exceptions."""
        # Pass through HTTP errors
        if hasattr(e, 'code') and 400 <= e.code < 600:
            return e
        
        # Track error
        context = {
            "path": request.path,
            "method": request.method,
            "remote_addr": request.remote_addr
        }
        error_id = error_tracker.track_error(error=e, context=context)
        
        # Log error for monitoring
        component = getattr(g, 'current_component', 'api')
        error_monitor.register_error(
            error_id=error_id,
            component=component,
            severity="ERROR",
            timestamp=g.request_start_time if hasattr(g, 'request_start_time') else 0
        )
        
        # Return error response
        response, status_code = handle_error(e, component)
        return jsonify(response), status_code
    
    # Register specific error handlers
    @app.errorhandler(LLMError)
    def handle_llm_error(e):
        response, status_code = handle_error(e, "llm")
        return jsonify(response), status_code
    
    @app.errorhandler(SearchError)
    def handle_search_error(e):
        response, status_code = handle_error(e, "search")
        return jsonify(response), status_code
    
    @app.errorhandler(ParameterExtractionError)
    def handle_parameter_error(e):
        response, status_code = handle_error(e, "parameter")
        return jsonify(response), status_code
    
    @app.errorhandler(RedisError)
    def handle_redis_error(e):
        response, status_code = handle_error(e, "redis")
        return jsonify(response), status_code
    
    @app.errorhandler(StateError)
    def handle_state_error(e):
        response, status_code = handle_error(e, "state")
        return jsonify(response), status_code
    
    @app.errorhandler(SecurityError)
    def handle_security_error(e):
        response, status_code = handle_error(e, "security")
        return jsonify(response), status_code
    
    # Add request tracking middleware
    @app.before_request
    def before_request():
        """Track request start time and initialize request context."""
        import time
        g.request_start_time = time.time()
        g.current_component = "api"
    
    # Register monitoring routes
    register_monitoring_routes(app)
    
    # Add error dashboard route
    @app.route("/admin/errors", methods=["GET"])
    def error_dashboard():
        """Render error monitoring dashboard."""
        return render_template('error_dashboard.html')
    
    logger.info("Error handling system integrated with Flask app")

def apply_error_handling(component: str = "general", fallback=None, default_return_value=None):
    """
    Decorator factory to apply error handling to any function.
    
    Args:
        component: Component name for error tracking
        fallback: Fallback function or method
        default_return_value: Default return value if all else fails
        
    Returns:
        Decorator function
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            tracker = EnhancedErrorTracker(component)
            try:
                return f(*args, **kwargs)
            except Exception as e:
                # Create context with function information
                context = {
                    "function": f.__name__,
                    "args_count": len(args),
                    "kwargs": str(kwargs)
                }
                
                # Track error
                error_id = tracker.track_error(
                    error=e,
                    context=context,
                    user_message=f"Error in {component} component. Reference ID: {error_id}"
                )
                
                # Register with monitor
                error_monitor.register_error(
                    error_id=error_id,
                    component=component,
                    severity="ERROR",
                    timestamp=time.time()
                )
                
                # Try fallback if provided
                if fallback:
                    try:
                        tracker.logger.info(
                            f"Using fallback for {f.__name__} after error {error_id}"
                        )
                        return fallback(*args, **kwargs)
                    except Exception as fallback_error:
                        fallback_error_id = tracker.track_error(
                            error=fallback_error,
                            context={"original_error_id": error_id},
                            user_message=f"Fallback for {component} also failed"
                        )
                
                # Re-raise appropriate exception type
                if component == "llm":
                    raise LLMError(str(e), error_id)
                elif component == "search":
                    raise SearchError(str(e), error_id)
                elif component == "parameter":
                    raise ParameterExtractionError(str(e), error_id)
                elif component == "redis":
                    raise RedisError(str(e), error_id)
                elif component == "state":
                    raise StateError(str(e), error_id)
                elif component == "security":
                    raise SecurityError(str(e), error_id)
                else:
                    # Return default value if provided, otherwise re-raise
                    if default_return_value is not None:
                        return default_return_value
                    raise
        
        return wrapped
    
    return decorator

# Function to wrap Redis operations with fallback
def redis_with_fallback(operation):
    """
    Decorator to add Redis fallback to Redis operations.
    
    Args:
        operation: Redis operation name ('get', 'set', 'delete')
        
    Returns:
        Decorator function
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            # Extract key from arguments (assuming first arg after self is key)
            key = args[1] if len(args) > 1 else kwargs.get('key')
            
            # For set operations, extract value
            value = None
            if operation.lower() == 'set':
                value = args[2] if len(args) > 2 else kwargs.get('value')
            
            # Create fallback function
            def redis_fallback(*_args, **_kwargs):
                return FallbackService.fallback_redis(operation, key, value)
            
            # Apply error handling with Redis fallback
            return apply_error_handling(
                component="redis",
                fallback=redis_fallback
            )(f)(*args, **kwargs)
        
        return wrapped
    
    return decorator

# Function to wrap LLM operations with fallback
def llm_with_fallback(f):
    """
    Decorator to add LLM fallback to LLM operations.
    
    Args:
        f: Function to decorate
        
    Returns:
        Decorated function
    """
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        # Extract prompt from arguments (assuming first arg after self is prompt)
        prompt = args[1] if len(args) > 1 else kwargs.get('prompt')
        
        # Create context for the request
        context = kwargs.get('context', {})
        
        # Create fallback function
        def llm_fallback(*_args, **_kwargs):
            return FallbackService.fallback_llm_response(prompt, context)
        
        # Apply error handling with LLM fallback
        return apply_error_handling(
            component="llm",
            fallback=llm_fallback
        )(f)(*args, **kwargs)
    
    return wrapped
