"""
Optimized Redis client configuration for the travel agent application.
Implements connection pooling, retry logic, and health checks.
"""

import os
import json
import logging
from typing import Any, Dict, Optional, Union
from datetime import date, datetime
import redis
from redis.exceptions import RedisError, ConnectionError, TimeoutError

from travel_agent.error_tracking import (
    track_errors, retry_with_tracking, ErrorTracker, 
    RedisConnectionError
)

# Create a dedicated logger for Redis operations
redis_logger = logging.getLogger('travel_agent.redis')
error_tracker = ErrorTracker('redis')

class RedisManager:
    """Manages Redis connections and operations with best practices"""
    
    def __init__(self, redis_url: Optional[str] = None):
        """Initialize Redis connection with optimal settings"""
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self.client = None
        self.connect()
    
    @track_errors('redis')
    def connect(self) -> None:
        """Connect to Redis with optimized connection settings"""
        try:
            self.client = redis.from_url(
                self.redis_url,
                socket_timeout=30,
                socket_connect_timeout=30,
                retry_on_timeout=True,
                health_check_interval=30,
                decode_responses=True
            )
            # Test connection
            self.client.ping()
            redis_logger.info(f"Successfully connected to Redis at {self.redis_url}")
        except (ConnectionError, TimeoutError) as e:
            error_id = error_tracker.track_error(
                RedisConnectionError(f"Failed to connect to Redis: {str(e)}"),
                {"redis_url": self.redis_url}
            )
            raise RedisConnectionError(f"Redis connection failed (Error ID: {error_id})") from e
        except Exception as e:
            error_id = error_tracker.track_error(e, {"redis_url": self.redis_url})
            raise RedisConnectionError(f"Unexpected Redis error (Error ID: {error_id})") from e
    
    @track_errors('redis')
    def health_check(self) -> bool:
        """Check if Redis connection is healthy"""
        try:
            return bool(self.client.ping())
        except Exception as e:
            error_tracker.track_error(e, {"redis_url": self.redis_url}, level="warning")
            return False
    
    @track_errors('redis')
    def reconnect_if_needed(self) -> None:
        """Reconnect to Redis if the connection is lost"""
        if not self.health_check():
            redis_logger.warning("Redis connection lost, attempting to reconnect")
            self.connect()
    
    @retry_with_tracking(max_attempts=3, component='redis')
    def get(self, key: str) -> Optional[str]:
        """Get a value from Redis with retry logic"""
        self.reconnect_if_needed()
        return self.client.get(key)
    
    @retry_with_tracking(max_attempts=3, component='redis')
    def set(self, key: str, value: str, expire: int = None) -> bool:
        """Set a value in Redis with retry logic"""
        self.reconnect_if_needed()
        return bool(self.client.set(key, value, ex=expire))
    
    @retry_with_tracking(max_attempts=3, component='redis')
    def delete(self, key: str) -> bool:
        """Delete a key from Redis with retry logic"""
        self.reconnect_if_needed()
        return bool(self.client.delete(key))
    
    # Custom JSON encoder for handling dates, datetimes, and sets
    class EnhancedJSONEncoder(json.JSONEncoder):
        """Custom JSON encoder for handling date, datetime, set and other non-serializable objects"""
        def default(self, obj):
            if isinstance(obj, (date, datetime)):
                return obj.isoformat()
            elif isinstance(obj, set):
                return list(obj)
            elif hasattr(obj, 'model_dump'):
                # Handle Pydantic models
                return obj.model_dump()
            return super().default(obj)
    
    @retry_with_tracking(max_attempts=3, component='redis')
    def store_json(self, key: str, data: Union[Dict, list], expire: int = None) -> bool:
        """Store a JSON object in Redis with enhanced serialization for dates, datetimes, etc."""
        self.reconnect_if_needed()
        try:
            # Use the enhanced JSON encoder to handle non-serializable objects
            json_data = json.dumps(data, cls=self.EnhancedJSONEncoder)
            return bool(self.client.set(key, json_data, ex=expire))
        except Exception as e:
            error_id = error_tracker.track_error(e, {"key": key})
            redis_logger.error(f"Error storing JSON in Redis: {str(e)} (Error ID: {error_id})")
            raise RedisError(f"Error storing JSON in Redis (Error ID: {error_id})") from e
    
    @retry_with_tracking(max_attempts=3, component='redis')
    def get_json(self, key: str) -> Optional[Any]:
        """Get JSON data from Redis with retry logic"""
        data = self.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError as e:
                error_id = error_tracker.track_error(
                    e, {"key": key, "data": data[:100] + "..." if len(data) > 100 else data}
                )
                raise ValueError(f"Failed to deserialize data (Error ID: {error_id})") from e
        return None
    
    @retry_with_tracking(max_attempts=3, component='redis')
    def pipeline_execute(self, pipeline_commands):
        """Execute a pipeline of Redis commands with retry logic"""
        self.reconnect_if_needed()
        pipeline = self.client.pipeline()
        for cmd, args, kwargs in pipeline_commands:
            method = getattr(pipeline, cmd)
            method(*args, **kwargs)
        return pipeline.execute()


# Create a singleton instance for application-wide use
redis_manager = RedisManager()

# Test the connection during module import
try:
    redis_manager.health_check()
except Exception as e:
    redis_logger.error(f"Redis health check failed during initialization: {str(e)}")
    # Don't raise here, as the application might want to continue without Redis
