#!/usr/bin/env python3
"""
Utilities for testing the travel agent system.
Provides test helpers, mocks, and context managers.
"""

import os
import sys
import json
import logging
from typing import Dict, Any, Optional, Callable
from unittest import mock
from contextlib import contextmanager
from datetime import date, datetime, timedelta

# Make sure we can import from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging for tests - with custom formatter to avoid error_id issues
class TestLogFormatter(logging.Formatter):
    """Custom formatter that handles missing format fields gracefully."""
    def format(self, record):
        # Add error_id if it doesn't exist to avoid KeyError during formatting
        if not hasattr(record, 'error_id'):
            record.error_id = 'test-error'
        return super().format(record)

# Configure test logging
def configure_test_logging():
    """Configure logging for tests with custom formatter."""
    handler = logging.StreamHandler()
    formatter = TestLogFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    # Reset root logger
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    
    # Ensure specific loggers have the right settings too
    for logger_name in ['travel_agent', 'security', 'error_handling']:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        
    return root

# Flask test context
@contextmanager
def flask_request_context(**kwargs):
    """Provide a Flask request context for testing Flask decorators.
    
    This creates a temporary Flask app and request context for testing
    decorators that rely on Flask's request context.
    """
    from flask import Flask, request, Response
    app = Flask(__name__)
    
    # Prepare request parameters
    defaults = {
        'method': 'POST',
        'path': '/',
        'json': {'message': 'test', 'session_id': 'test123'},
        'headers': {'Content-Type': 'application/json'}
    }
    
    # Override defaults with provided kwargs
    for key, value in kwargs.items():
        if key in defaults:
            if isinstance(defaults[key], dict) and isinstance(value, dict):
                defaults[key].update(value)
            else:
                defaults[key] = value
    
    # Create request context
    with app.test_request_context(
        path=defaults['path'],
        method=defaults['method'],
        headers=defaults['headers'],
        json=defaults['json']
    ):
        yield

# Redis mocking
class MockRedis:
    """Mock Redis client for testing Redis operations."""
    def __init__(self):
        self.data = {}
        self.expiry = {}
    
    def get(self, key):
        return self.data.get(key)
    
    def set(self, key, value, ex=None, nx=False):
        # If nx is True and the key exists, return False
        if nx and key in self.data:
            return False
        
        self.data[key] = value
        if ex:
            self.expiry[key] = datetime.now() + timedelta(seconds=ex)
        return True
    
    def incr(self, key, amount=1):
        # Create key with 0 value if it doesn't exist
        if key not in self.data:
            self.data[key] = '0'
        
        # Increment value
        curr_val = int(self.data[key])
        new_val = curr_val + amount
        self.data[key] = str(new_val)
        return new_val
    
    def expire(self, key, seconds):
        if key in self.data:
            self.expiry[key] = datetime.now() + timedelta(seconds=seconds)
            return True
        return False
    
    def ttl(self, key):
        if key not in self.data:
            return -2  # Key doesn't exist
        if key not in self.expiry:
            return -1  # No expiry
        
        # Calculate remaining TTL
        remaining = (self.expiry[key] - datetime.now()).total_seconds()
        return max(0, int(remaining))
    
    def ping(self):
        return True
    
    def from_url(self, *args, **kwargs):
        return self


@contextmanager
def mock_redis():
    """Context manager to mock Redis for testing."""
    redis_mock = MockRedis()
    
    with mock.patch('redis.Redis', return_value=redis_mock), \
         mock.patch('redis.from_url', return_value=redis_mock):
        yield redis_mock


# LLM testing utilities
class MockLLMResponse:
    """Mock LLM response for testing."""
    def __init__(self, content=None):
        if isinstance(content, dict):
            self.content = json.dumps(content)
        else:
            self.content = content or '{}'
    
    def json(self):
        return json.loads(self.content)


def create_mock_llm(response_content=None):
    """Create a mock LLM client for testing."""
    mock_llm = mock.MagicMock()
    mock_response = MockLLMResponse(response_content)
    
    # Set up the completions.create method
    mock_llm.completions.create.return_value = mock.MagicMock(content=mock_response.content)
    
    return mock_llm


# Load fixture data for tests
def load_test_fixture(fixture_name: str) -> Dict[str, Any]:
    """Load fixture data from JSON file."""
    fixture_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'fixture_data',
        f'{fixture_name}.json'
    )
    
    if not os.path.exists(fixture_path):
        # Create fixtures directory if it doesn't exist
        os.makedirs(os.path.dirname(fixture_path), exist_ok=True)
        return {}
    
    with open(fixture_path, 'r') as f:
        return json.load(f)


# Initialize test environment
configure_test_logging()
