#!/usr/bin/env python3
"""
API tests for the travel agent Flask application.
Tests endpoints with security and error handling.
"""

import unittest
import sys
import os
import json
import time
from unittest.mock import MagicMock, patch
import flask_unittest
from flask import Flask

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import Flask app components
from travel_agent.app import app
from travel_agent.agents.conversation_manager import ConversationManager
from travel_agent.config.redis_client import RedisManager
from travel_agent.state_definitions import TravelState
from travel_agent.error_handling import LLMError, SearchError
from travel_agent.error_handling.integration import setup_error_handling
from travel_agent.security.input_validation import InputValidator
from travel_agent.security.rate_limiter import RateLimiter

class TestFlaskAPI(flask_unittest.AppTestCase):
    """Test the Flask API endpoints with security and error handling."""
    
    def create_app(self):
        """Configure a fresh test app for each test run."""
        from travel_agent.app import app as original_app
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['SERVER_NAME'] = 'localhost:5000'
        # Register blueprints, routes, error handlers, etc.
        # If travel_agent.app uses blueprints, register them here:
        if hasattr(original_app, 'blueprints'):
            for name, blueprint in original_app.blueprints.items():
                app.register_blueprint(blueprint)
        # If there are custom error handlers or extensions, register them as well
        # Example: setup_error_handling(app)
        try:
            from travel_agent.error_handling.integration import setup_error_handling
            setup_error_handling(app)
        except Exception:
            pass
        return app
    
    def test_health_endpoint(self, app):
        """Test the health check endpoint."""
        response = self.client.get('/api/health')

    @patch.object(ConversationManager, 'create_session')
    def test_chat_start_endpoint(self, mock_conv):
        """Test the chat start endpoint."""
        # Mock conversation manager
        mock_state = MagicMock(spec=TravelState)
        mock_state.session_id = 'test_session_123'
        mock_conv.return_value = mock_state

        response = self.client.post('/api/chat/start')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('session_id', data)
        self.assertEqual(data['session_id'], 'test_session_123')
    
    @patch('travel_agent.app.redis_manager')
    @patch('travel_agent.app.travel_agent')
    def test_send_message_endpoint(self, mock_travel_agent, mock_redis_manager, app):
        """Test the send message endpoint."""
        # Mock Redis get_json to return a serialized state
        mock_redis_manager.get_json.return_value = {
            'session_id': 'test_session_123',
            'conversation_stage': 'INITIAL',
            'messages': []
        }
        
        # Mock travel_agent.handle_message to return a response
        mock_travel_agent.handle_message.return_value = ('I can help with your travel plans', True)
        
        # Mock Redis set_json
        mock_redis_manager.set_json.return_value = True
        
        client = self.client
        # Send a message
        response = client.post(
            '/api/chat/test_session_123/message',
            json={'message': 'I want to travel to Paris'},
            content_type='application/json'
        )
        # Check response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('message', data)
        self.assertEqual(data['message'], 'I can help with your travel plans')
        # Verify Redis operations
        mock_redis_manager.get_json.assert_called_once()
        mock_redis_manager.set_json.assert_called_once()
        # Verify travel_agent.handle_message was called with correct args
        mock_travel_agent.handle_message.assert_called_once()
        args, kwargs = mock_travel_agent.handle_message.call_args
        self.assertIsInstance(args[0], TravelState)
        self.assertEqual(args[1], 'I want to travel to Paris')
    
    @patch('travel_agent.app.redis_manager')
    def test_send_message_invalid_json(self, mock_redis_manager, app):
        """Test sending an invalid JSON message."""
        client = self.client
        # Send invalid JSON
        response = client.post(
            '/api/chat/test_session_123/message',
            data='invalid json',
            content_type='application/json'
        )
        # Check for bad request response
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    @patch('travel_agent.app.redis_manager')
    def test_send_message_empty_message(self, mock_redis_manager, app):
        """Test sending an empty message."""
        client = self.client
        # Send empty message
        response = client.post(
            '/api/chat/test_session_123/message',
            json={'message': ''},
            content_type='application/json'
        )
        # Check for bad request response
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Message is required')
    
    @patch('travel_agent.app.redis_manager')
    @patch('travel_agent.app.travel_agent')
    def test_send_message_llm_error(self, mock_travel_agent, mock_redis_manager, app):
        """Test handling of LLM errors."""
        # Mock Redis get_json to return a valid state
        mock_redis_manager.get_json.return_value = {
            'session_id': 'test_session_123',
            'conversation_stage': 'INITIAL',
            'messages': []
        }
        
        # Mock travel_agent.handle_message to raise an LLM error
        mock_travel_agent.handle_message.side_effect = LLMError("LLM API error", "E-LLM-123456-1650389914")
        
        client = self.client
        response = client.post(
            '/api/chat/test_session_123/message',
            json={'message': 'I want to travel to Paris'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 502)  # Bad Gateway
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'LLMError')
        self.assertIn('error_id', data)
        self.assertEqual(data['error_id'], 'E-LLM-123456-1650389914')

    @patch('travel_agent.app.redis_manager')
    def test_invalid_session_id(self, mock_redis_manager, app):
        """Test handling of invalid session IDs."""
        # Mock Redis get_json to return None (session not found)
        mock_redis_manager.get_json.return_value = None
        
        client = self.client
        # Send a message with invalid session ID
        response = client.post(
            '/api/chat/invalid@session/message',
            json={'message': 'I want to travel to Paris'},
            content_type='application/json'
        )
        # Check for appropriate error response
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    @patch('travel_agent.app.travel_agent')
    def test_error_dashboard_route(self, mock_travel_agent, app):
        """Test the error dashboard route."""
        client = self.client
        response = client.get('/admin/errors')
        # Should return the dashboard HTML
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Error Dashboard', response.data)
    
    @patch('travel_agent.app.redis_manager')
    @patch('travel_agent.security.rate_limiter.RateLimiter.is_rate_limited')
    def test_rate_limiting(self, mock_is_rate_limited, mock_redis_manager, app):
        """Test rate limiting on API endpoints."""
        # Configure the mock to indicate rate limit exceeded
        mock_is_rate_limited.return_value = (True, {
            'limit': 10,
            'remaining': 0,
            'reset': int(time.time()) + 60,
            'count': 10
        })
        client = self.client
        # Attempt to call an endpoint
        response = self.client.post('/api/chat/start')
        # Should be rate limited
        self.assertEqual(response.status_code, 429)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('Rate limit exceeded', data['error'])
        # Headers should include rate limit info
        self.assertIn('X-RateLimit-Limit', response.headers)
        self.assertIn('X-RateLimit-Remaining', response.headers)
        self.assertIn('X-RateLimit-Reset', response.headers)
        self.assertIn('Retry-After', response.headers)

class TestErrorHandlingIntegration(unittest.TestCase):
    """Test the integration of error handling with Flask."""
    
    def setUp(self):
        """Set up a test Flask application with error handling."""
        self.app = Flask('test_app')
        
        # Set up error handling
        setup_error_handling(self.app)
        
        # Add a test route that raises different errors
        @self.app.route('/test/llm-error')
        def test_llm_error():
            raise LLMError("Test LLM error")
        
        @self.app.route('/test/search-error')
        def test_search_error():
            raise SearchError("Test search error")
        
        @self.app.route('/test/general-error')
        def test_general_error():
            raise ValueError("Test general error")
    
    def test_llm_error_handled(self):
        """Test that LLM errors are handled correctly."""
        with self.app.test_client() as client:
            response = client.get('/test/llm-error')
            
            # Should return appropriate status code
            self.assertEqual(response.status_code, 502)  # Bad Gateway
            
            # Response should include error details
            data = json.loads(response.data)
            self.assertEqual(data['error'], 'LLMError')
            self.assertEqual(data['message'], 'Test LLM error')
            self.assertIn('error_id', data)
    
    def test_search_error_handled(self):
        """Test that search errors are handled correctly."""
        with self.app.test_client() as client:
            response = client.get('/test/search-error')
            
            # Should return appropriate status code
            self.assertEqual(response.status_code, 503)  # Service Unavailable
            
            # Response should include error details
            data = json.loads(response.data)
            self.assertEqual(data['error'], 'SearchError')
            self.assertEqual(data['message'], 'Test search error')
            self.assertIn('error_id', data)
    
    def test_general_error_handled(self):
        """Test that general errors are handled correctly."""
        with self.app.test_client() as client:
            response = client.get('/test/general-error')
            
            # Should return appropriate status code
            self.assertEqual(response.status_code, 500)  # Internal Server Error
            
            # Response should include error details
            data = json.loads(response.data)
            self.assertEqual(data['error'], 'ValueError')
            self.assertEqual(data['message'], 'Test general error')
            self.assertIn('error_id', data)

class TestSessionSecurityIntegration(flask_unittest.AppTestCase):
    """Test the session security integration with Flask."""
    
    def setUp(self):
        self.client = app.test_client()
        self.redis_patcher = patch('travel_agent.redis_client.RedisManager')
        self.mock_redis = self.redis_patcher.start()
        self.conv_patcher = patch('travel_agent.agents.conversation_manager.ConversationManager')
        self.mock_conv = self.conv_patcher.start()

    def create_app(self):
        """Create a test Flask application with session security."""
        app.config['TESTING'] = True
        # Add a test route that requires session authentication
        @app.route('/test/secure')
        def test_secure():
            return {'status': 'authenticated'}
        return app

    @patch('travel_agent.security.session_security.SessionManager.validate_session')
    def test_valid_session(self, mock_validate_session, app):
        """Test access with a valid session."""
        # Configure mock to indicate valid session
        mock_validate_session.return_value = (True, {'user_id': 'test_user'})
        client = self.client
        # Set session headers
        headers = {
            'X-Session-ID': 'test_session_123',
            'X-Access-Token': 'test_token_456'
        }
        response = client.get('/test/secure', headers=headers)
        # Should allow access
        self.assertEqual(response.status_code, 200)
        # Verify session validation was called
        mock_validate_session.assert_called_once_with('test_session_123', 'test_token_456')

    @patch('travel_agent.security.session_security.SessionManager.validate_session')
    def test_invalid_session(self, mock_validate_session, app):
        """Test access with an invalid session."""
        # Configure mock to indicate invalid session
        mock_validate_session.return_value = (False, None)
        client = self.client
        # Set session headers
        headers = {
            'X-Session-ID': 'invalid_session',
            'X-Access-Token': 'invalid_token'
        }
        response = client.get('/test/secure', headers=headers)
        # Should deny access
        self.assertEqual(response.status_code, 401)
        # Verify session validation was called
        mock_validate_session.assert_called_once_with('invalid_session', 'invalid_token')
    
    def test_missing_session_headers(self, app):
        """Test access with missing session headers."""
        client = self.client
        # No session headers
        response = client.get('/test/secure')
        # Should deny access
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('Authentication required', data['error'])

if __name__ == "__main__":
    unittest.main()
