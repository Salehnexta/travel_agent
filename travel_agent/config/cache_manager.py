"""
Enhanced caching system with tiered strategy (memory → Redis → API call)
Implements best practices for API optimization with cache invalidation
"""

import logging
import time
import hashlib
import json
from typing import Any, Dict, Optional, Callable, TypeVar, Generic, Union
from functools import wraps

from travel_agent.config.redis_client import RedisManager
from travel_agent.error_tracking import error_tracker, retry_with_tracking

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Type variables for generics
T = TypeVar('T')
R = TypeVar('R')


class MemoryCache:
    """Simple in-memory cache with TTL and max size management."""
    
    def __init__(self, max_size: int = 1000):
        """Initialize the memory cache with a maximum size."""
        self.cache = {}  # {key: (value, expiry_time)}
        self.max_size = max_size
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache if it exists and hasn't expired."""
        if key in self.cache:
            value, expiry = self.cache[key]
            # Check if the entry has expired
            if expiry is None or time.time() < expiry:
                return value
            # Remove expired entry
            del self.cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in the cache with optional TTL in seconds."""
        # Calculate expiry time if TTL is set
        expiry = None if ttl is None else time.time() + ttl
        
        # Enforce max size by removing oldest entries if needed
        if len(self.cache) >= self.max_size and key not in self.cache:
            # Simple strategy: remove the first key (rough approximation of oldest)
            # A better implementation would use LRU, but this is simpler
            if self.cache:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
        
        # Store the value with expiry time
        self.cache[key] = (value, expiry)
    
    def delete(self, key: str) -> None:
        """Delete a key from the cache if it exists."""
        if key in self.cache:
            del self.cache[key]
    
    def clear(self) -> None:
        """Clear all entries from the cache."""
        self.cache.clear()


class TieredCache:
    """
    Tiered caching system that uses memory cache as L1 and Redis as L2.
    Provides automatic cache invalidation based on TTL.
    """
    
    def __init__(self, redis_manager: Optional[RedisManager] = None, namespace: str = "travel_agent"):
        """Initialize the tiered cache with memory and Redis backends."""
        self.memory_cache = MemoryCache(max_size=1000)
        self.redis_manager = redis_manager or RedisManager()
        self.namespace = namespace
    
    def _create_key(self, key: str) -> str:
        """Create a namespaced key for Redis."""
        return f"{self.namespace}:cache:{key}"
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from the cache, trying memory first then Redis.
        Returns None if the key is not found in either cache.
        """
        # Try memory cache first (L1)
        value = self.memory_cache.get(key)
        if value is not None:
            logger.debug(f"Cache hit (memory): {key}")
            return value
        
        # If not in memory, try Redis (L2)
        redis_key = self._create_key(key)
        try:
            value = self.redis_manager.get_json(redis_key)
            if value is not None:
                # If found in Redis, also cache in memory for faster future access
                self.memory_cache.set(key, value, ttl=300)  # 5 minutes in memory
                logger.debug(f"Cache hit (Redis): {key}")
                return value
        except Exception as e:
            error_id = error_tracker.track_error(e, {"component": "tiered_cache", "operation": "get", "key": key})
            logger.error(f"Redis cache error: {str(e)} (Error ID: {error_id})")
        
        logger.debug(f"Cache miss: {key}")
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None, memory_only: bool = False) -> None:
        """
        Set a value in the cache with optional TTL in seconds.
        Stores in both memory and Redis by default.
        """
        # Always set in memory cache
        memory_ttl = min(ttl or 3600, 3600)  # Cap memory TTL at 1 hour
        self.memory_cache.set(key, value, ttl=memory_ttl)
        
        # Set in Redis unless memory_only is True
        if not memory_only:
            redis_key = self._create_key(key)
            try:
                self.redis_manager.store_json(redis_key, value, ttl=ttl)
            except Exception as e:
                error_id = error_tracker.track_error(
                    e, {"component": "tiered_cache", "operation": "set", "key": key}
                )
                logger.error(f"Redis cache error: {str(e)} (Error ID: {error_id})")
    
    def delete(self, key: str) -> None:
        """Delete a key from both memory and Redis caches."""
        # Delete from memory
        self.memory_cache.delete(key)
        
        # Delete from Redis
        redis_key = self._create_key(key)
        try:
            self.redis_manager.delete(redis_key)
        except Exception as e:
            error_id = error_tracker.track_error(
                e, {"component": "tiered_cache", "operation": "delete", "key": key}
            )
            logger.error(f"Redis cache error: {str(e)} (Error ID: {error_id})")
    
    def clear_namespace(self, sub_namespace: Optional[str] = None) -> None:
        """
        Clear all keys in a specific namespace or sub-namespace.
        For example, clear all flight search results or all results for a specific user.
        """
        # Clear memory cache (simple implementation just clears everything)
        # A more sophisticated implementation would only clear matching keys
        self.memory_cache.clear()
        
        # Clear Redis namespace
        namespace = self.namespace
        if sub_namespace:
            namespace = f"{namespace}:{sub_namespace}"
        
        try:
            pattern = f"{namespace}:*"
            self.redis_manager.delete_pattern(pattern)
        except Exception as e:
            error_id = error_tracker.track_error(
                e, {"component": "tiered_cache", "operation": "clear_namespace", "namespace": namespace}
            )
            logger.error(f"Redis cache error: {str(e)} (Error ID: {error_id})")


def cached(
    ttl: Optional[int] = 3600,
    key_builder: Optional[Callable[..., str]] = None,
    namespace: Optional[str] = None,
    memory_only: bool = False,
    tiered_cache: Optional[TieredCache] = None
):
    """
    Decorator for caching function results.
    
    Args:
        ttl: Time-to-live in seconds. None means no expiration.
        key_builder: Function to build cache key from args and kwargs.
        namespace: Namespace to use for cache keys.
        memory_only: If True, only cache in memory, not in Redis.
        tiered_cache: Custom TieredCache instance to use.
    
    Returns:
        Decorated function with caching.
    """
    def default_key_builder(*args, **kwargs) -> str:
        """Default function to build cache keys based on arguments."""
        # Convert args and kwargs to a stable string representation
        key_dict = {"args": args, "kwargs": kwargs}
        try:
            key_str = json.dumps(key_dict, sort_keys=True, default=str)
        except TypeError:
            # If JSON serialization fails, use a simpler approach
            key_str = str(args) + str(sorted(kwargs.items()))
        
        # Hash the string to create a fixed-length key
        hashed = hashlib.md5(key_str.encode()).hexdigest()
        return hashed
    
    def decorator(func):
        # Use the provided namespace or create one from the function's module and name
        _namespace = namespace or f"{func.__module__}.{func.__name__}"
        # Use the provided cache or create a new one
        _cache = tiered_cache or TieredCache(namespace=_namespace)
        # Use the provided key builder or the default one
        _key_builder = key_builder or default_key_builder
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Skip caching if a special kwarg is passed
            skip_cache = kwargs.pop("skip_cache", False)
            if skip_cache:
                return func(*args, **kwargs)
            
            # Build the cache key
            cache_key = _key_builder(*args, **kwargs)
            
            # Try to get the result from cache
            cached_result = _cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # If not in cache, call the function
            result = func(*args, **kwargs)
            
            # Store the result in cache
            _cache.set(cache_key, result, ttl=ttl, memory_only=memory_only)
            
            return result
        
        # Add a method to invalidate the cache for specific arguments
        def invalidate_cache(*args, **kwargs):
            cache_key = _key_builder(*args, **kwargs)
            _cache.delete(cache_key)
        
        wrapper.invalidate_cache = invalidate_cache
        
        return wrapper
    
    return decorator
