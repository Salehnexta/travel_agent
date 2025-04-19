"""
Rate limiting module for the travel agent application.
Implements IP-based and token-based rate limiting to prevent abuse.
"""

import time
import logging
from typing import Dict, Tuple, Optional, Any, Callable
import functools
from flask import request, jsonify, Response
from redis import Redis

# Configure logging
logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Rate limiting implementation with Redis backend.
    Supports IP-based and token-based rate limiting with configurable limits.
    """
    
    def __init__(self, redis_client: Redis):
        """
        Initialize rate limiter with Redis client.
        
        Args:
            redis_client: Redis client for storing rate limit data
        """
        self.redis = redis_client
        self.default_limits = {
            'global': {'rate': 300, 'per': 60 * 60},  # 300 requests per hour globally
            'ip': {'rate': 60, 'per': 60},            # 60 requests per minute per IP
            'user': {'rate': 120, 'per': 60},         # 120 requests per minute per user
            'endpoint': {                             # Endpoint-specific limits
                'api/chat': {'rate': 10, 'per': 60},  # 10 requests per minute for chat endpoint
                'api/search': {'rate': 5, 'per': 60}, # 5 requests per minute for search endpoint
            }
        }
    
    def _get_rate_limit_key(self, key_type: str, identifier: str = None) -> str:
        """
        Generate Redis key for rate limiting.
        
        Args:
            key_type: Type of rate limit (ip, user, endpoint)
            identifier: Specific identifier (IP address, user ID, endpoint name)
            
        Returns:
            Redis key for rate limiting
        """
        if key_type == 'ip':
            return f"ratelimit:ip:{identifier or request.remote_addr}"
        elif key_type == 'user':
            return f"ratelimit:user:{identifier}"
        elif key_type == 'endpoint':
            return f"ratelimit:endpoint:{identifier}"
        elif key_type == 'global':
            return "ratelimit:global"
        else:
            return f"ratelimit:{key_type}:{identifier}"
    
    def is_rate_limited(self, key_type: str, identifier: str = None,
                       limit: int = None, period: int = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if a request should be rate limited.
        
        Args:
            key_type: Type of rate limit (ip, user, endpoint)
            identifier: Specific identifier (IP address, user ID, endpoint name)
            limit: Maximum number of requests allowed
            period: Time period in seconds
            
        Returns:
            Tuple of (is_limited, rate_limit_info)
        """
        # Get default limit if not specified
        if limit is None or period is None:
            if key_type == 'endpoint' and identifier in self.default_limits['endpoint']:
                limit = self.default_limits['endpoint'][identifier]['rate']
                period = self.default_limits['endpoint'][identifier]['per']
            elif key_type in self.default_limits:
                limit = self.default_limits[key_type]['rate']
                period = self.default_limits[key_type]['per']
            else:
                # Use global defaults
                limit = self.default_limits['global']['rate']
                period = self.default_limits['global']['per']
        
        # Generate key
        key = self._get_rate_limit_key(key_type, identifier)
        current_time = int(time.time())
        window_start = current_time - period
        
        # Use pipeline to ensure atomic operations
        pipe = self.redis.pipeline()
        
        # Remove old entries outside of the current time window
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count requests in the current time window
        pipe.zcard(key)
        
        # Add current request timestamp to the sorted set
        pipe.zadd(key, {str(current_time): current_time})
        
        # Set expiry on the key to clean up automatically
        pipe.expire(key, period)
        
        # Execute pipeline
        results = pipe.execute()
        
        # Get count of requests in window
        request_count = results[1]
        
        # Check if rate limit exceeded
        is_limited = request_count >= limit
        
        # Prepare rate limit info for headers
        rate_limit_info = {
            'limit': limit,
            'remaining': max(0, limit - request_count),
            'reset': window_start + period,
            'count': request_count
        }
        
        if is_limited:
            logger.warning(f"Rate limit exceeded for {key_type}:{identifier or 'default'}, "
                         f"count: {request_count}, limit: {limit}")
        
        return is_limited, rate_limit_info

# Flask decorator for rate limiting
def rate_limit(limiter: RateLimiter,
              key_type: str = 'ip',
              identifier: Optional[Callable] = None,
              limit: Optional[int] = None,
              period: Optional[int] = None):
    """
    Decorator for rate limiting Flask routes.
    
    Args:
        limiter: RateLimiter instance
        key_type: Type of rate limit (ip, user, endpoint)
        identifier: Function to extract identifier from request
        limit: Maximum number of requests allowed
        period: Time period in seconds
        
    Returns:
        Decorated function
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            # Get identifier
            id_value = None
            if identifier:
                id_value = identifier()
                
            if key_type == 'endpoint':
                # Use endpoint name from request
                endpoint = request.endpoint or request.path
                id_value = endpoint
            
            # Check rate limit
            is_limited, rate_limit_info = limiter.is_rate_limited(
                key_type, id_value, limit, period
            )
            
            # Add rate limit headers
            headers = {
                'X-RateLimit-Limit': str(rate_limit_info['limit']),
                'X-RateLimit-Remaining': str(rate_limit_info['remaining']),
                'X-RateLimit-Reset': str(rate_limit_info['reset'])
            }
            
            # Return 429 Too Many Requests if rate limited
            if is_limited:
                response = jsonify({
                    'error': 'Rate limit exceeded',
                    'retry_after': rate_limit_info['reset'] - int(time.time())
                })
                response.status_code = 429
                for key, value in headers.items():
                    response.headers[key] = value
                response.headers['Retry-After'] = str(rate_limit_info['reset'] - int(time.time()))
                return response
            
            # Process request normally
            response = f(*args, **kwargs)
            
            # Add rate limit headers to response
            if isinstance(response, Response):
                for key, value in headers.items():
                    response.headers[key] = value
            
            return response
        return wrapped
    return decorator
