#!/usr/bin/env python3
"""
Unit tests for rate limiter module.
Tests rate limiting functionality with Redis backend.
"""

import unittest
import sys
import os
import time
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import test utilities
from tests.test_utils import flask_request_context, mock_redis, configure_test_logging

# Ensure logging is properly configured
configure_test_logging()

# Import components to test
from travel_agent.security.rate_limiter import RateLimiter, rate_limit

class TestRateLimiter(unittest.TestCase):
    """Test the RateLimiter class functionality."""
    
    def setUp(self):
        # Create a mock Redis client
        self.mock_redis = MagicMock()
        self.limiter = RateLimiter(self.mock_redis)
    
    def test_get_rate_limit_key(self):
        """Test generation of Redis keys for rate limiting."""
        # Test IP-based key
        key = self.limiter._get_rate_limit_key('ip', '127.0.0.1')
        self.assertEqual(key, 'ratelimit:ip:127.0.0.1')
        
        # Test user-based key
        key = self.limiter._get_rate_limit_key('user', 'user123')
        self.assertEqual(key, 'ratelimit:user:user123')
        
        # Test endpoint-based key
        key = self.limiter._get_rate_limit_key('endpoint', 'api/chat')
        self.assertEqual(key, 'ratelimit:endpoint:api/chat')
        
        # Test global key
        key = self.limiter._get_rate_limit_key('global')
        self.assertEqual(key, 'ratelimit:global')
        
        # Test custom key type
        key = self.limiter._get_rate_limit_key('custom', 'value')
        self.assertEqual(key, 'ratelimit:custom:value')
    
    def test_is_rate_limited_not_limited(self):
        """Test rate limiting when limit is not exceeded."""
        # Set up mock pipeline
        mock_pipeline = MagicMock()
        self.mock_redis.pipeline.return_value = mock_pipeline
        
        # Configure pipeline to return values for not limited case
        mock_pipeline.execute.return_value = [0, 5, 0, 1]  # zremrangebyscore, zcard, zadd, expire
        
        # Test IP-based rate limiting
        is_limited, info = self.limiter.is_rate_limited('ip', '127.0.0.1', 10, 60)
        
        # Verify results
        self.assertFalse(is_limited)
        self.assertEqual(info['limit'], 10)
        self.assertEqual(info['remaining'], 5)  # 10 - 5 = 5
        self.assertTrue('reset' in info)
        
        # Verify Redis operations
        self.mock_redis.pipeline.assert_called_once()
        self.assertEqual(mock_pipeline.zremrangebyscore.call_count, 1)
        self.assertEqual(mock_pipeline.zcard.call_count, 1)
        self.assertEqual(mock_pipeline.zadd.call_count, 1)
        self.assertEqual(mock_pipeline.expire.call_count, 1)
    
    def test_is_rate_limited_exceeded(self):
        """Test rate limiting when limit is exceeded."""
        # Set up mock pipeline
        mock_pipeline = MagicMock()
        self.mock_redis.pipeline.return_value = mock_pipeline
        
        # Configure pipeline to return values for limited case
        mock_pipeline.execute.return_value = [0, 10, 0, 1]  # zremrangebyscore, zcard, zadd, expire
        
        # Test user-based rate limiting
        is_limited, info = self.limiter.is_rate_limited('user', 'user123', 10, 60)
        
        # Verify results
        self.assertTrue(is_limited)
        self.assertEqual(info['limit'], 10)
        self.assertEqual(info['remaining'], 0)  # Limit reached
        self.assertTrue('reset' in info)
        
        # Verify Redis operations
        self.mock_redis.pipeline.assert_called_once()
    
    def test_default_limits(self):
        """Test using default limits."""
        # Set up mock pipeline
        mock_pipeline = MagicMock()
        self.mock_redis.pipeline.return_value = mock_pipeline
        
        # Configure pipeline to return values
        mock_pipeline.execute.return_value = [0, 5, 0, 1]  # zremrangebyscore, zcard, zadd, expire
        
        # Test using default limit for 'ip'
        is_limited, info = self.limiter.is_rate_limited('ip', '127.0.0.1')
        
        # Default for IP should be 60 per minute
        self.assertEqual(info['limit'], 60)
        
        # Reset for next test
        mock_pipeline.reset_mock()
        
        # Test using default limit for endpoint
        mock_pipeline.execute.return_value = [0, 3, 0, 1]
        is_limited, info = self.limiter.is_rate_limited('endpoint', 'api/chat')
        
        # Default for api/chat endpoint should be 10 per minute
        self.assertEqual(info['limit'], 10)

# Flask decorator test
class TestRateLimitDecorator(unittest.TestCase):
    """Test the rate_limit decorator functionality."""
    
    def setUp(self):
        # Create a mock limiter
        self.mock_limiter = MagicMock()
    
    def test_rate_limit_not_limited(self):
        """Test rate_limit decorator when not rate limited."""
        # Use Flask test context
        with flask_request_context():
            
            # Configure mock limiter
            self.mock_limiter.is_rate_limited.return_value = (False, {
                'limit': 10,
                'remaining': 5,
                'reset': int(time.time()) + 60,
                'count': 5
            })
            
            # Create a test function
            @rate_limit(self.mock_limiter, 'ip')
            def test_func():
                return 'success'
            
            # Call the function
            result = test_func()
            
            # Verify limiter was called
            self.mock_limiter.is_rate_limited.assert_called_once()
            
            # Verify result
            self.assertEqual(result, 'success')
    
    def test_rate_limit_exceeded(self):
        """Test rate_limit decorator when rate limited."""
        # Use Flask test context
        with flask_request_context():
            
            # Configure mock limiter for rate limited case
            reset_time = int(time.time()) + 60
            self.mock_limiter.is_rate_limited.return_value = (True, {
                'limit': 10,
                'remaining': 0,
                'reset': reset_time,
                'count': 10
            })
            
            # Create a test function
            @rate_limit(self.mock_limiter, 'ip')
            def test_func():
                return 'success'  # This should not be called
            
            # Call the function
            result = test_func()
            
            # Verify limiter was called
            self.mock_limiter.is_rate_limited.assert_called_once()
            
            # Verify 429 response - get the status code correctly
            if isinstance(result, tuple):
                status_code = result[1]
                response_obj = result[0]
                self.assertEqual(status_code, 429)  # HTTP 429 Too Many Requests
                self.assertIn('error', response_obj.json)
                self.assertIn('Rate limit exceeded', response_obj.json['error'])
                headers = response_obj.headers
            else:
                # Direct Response object
                self.assertEqual(result.status_code, 429)  # HTTP 429 Too Many Requests
                response_data = result.get_json()
                self.assertIn('error', response_data)
                self.assertIn('Rate limit exceeded', response_data['error'])
                headers = result.headers
            self.assertIn('X-RateLimit-Limit', headers)
            self.assertIn('X-RateLimit-Remaining', headers)
            self.assertIn('X-RateLimit-Reset', headers)
            self.assertIn('Retry-After', headers)
    
    def test_custom_identifier(self):
        """Test rate_limit decorator with custom identifier."""
        # Use Flask test context with session_id in JSON
        with flask_request_context(json={'session_id': 'user123'}):
            
            # Configure mock limiter
            self.mock_limiter.is_rate_limited.return_value = (False, {
                'limit': 10,
                'remaining': 5,
                'reset': int(time.time()) + 60,
                'count': 5
            })
            
            # Define custom identifier function
            def custom_id():
                from flask import request
                return request.json.get('session_id')
            
            # Create a test function with custom identifier
            @rate_limit(self.mock_limiter, 'user', identifier=custom_id)
            def test_func():
                return 'success'
            
            # Call the function
            result = test_func()
            
            # Verify limiter was called with custom identifier
            self.mock_limiter.is_rate_limited.assert_called_once()
            # Extract the args from the call
            args, kwargs = self.mock_limiter.is_rate_limited.call_args
            self.assertEqual(args[0], 'user')
            self.assertEqual(args[1], 'user123')
            
            # Verify result
            self.assertEqual(result, 'success')

if __name__ == "__main__":
    unittest.main()
