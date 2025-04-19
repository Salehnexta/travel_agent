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
from travel_agent.app import create_app
from travel_agent.state_definitions import TravelState
from travel_agent.error_handling import LLMError, SearchError
from travel_agent.error_handling.integration import setup_error_handling
from travel_agent.security.input_validation import InputValidator
from travel_agent.security.rate_limiter import RateLimiter

class TestFlaskAPI(flask_unittest.AppTestCase):
    """Test the Flask API endpoints with security and error handling."""
    
    def create_app(self):
        """Create a test Flask application."""
        # Use the app factory function with test config
        app = create_app(testing=True)
        
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['SERVER_NAME'] = 'localhost:5000'
        app.config['PRESERVE_CONTEXT_ON_EXCEPTION'] = False
        
        return app
    
    def test_health_endpoint(self, app):
        """Test the health check endpoint."""
        with app.test_client() as client:
            response = client.get('/api/health')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn('status', data)
            self.assertEqual(data['status'], 'healthy')
    
    @patch('travel_agent.app.redis_manager')
    @patch('travel_agent.app.travel_agent')
    def test_chat_start_endpoint(self, mock_travel_agent, mock_redis_manager, app):
        """Test the chat start endpoint."""
        # Mock travel_agent.create_session to return a session ID
        mock_state = MagicMock(spec=TravelState)
        mock_state.session_id = 'test_session_123'
        mock_travel_agent.create_session.return_value = mock_state
        
        # Mock Redis operations
        mock_redis_manager.set_json.return_value = True
        
        with app.test_client() as client:
            response = client.post('/api/chat/start')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn('session_id', data)
            self.assertEqual(data['session_id'], 'test_session_123')
            
            # Verify travel_agent.create_session was called
            mock_travel_agent.create_session.assert_called_once()
            
            # Verify Redis operations
            mock_redis_manager.set_json.assert_called_once()
    
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
        
        with app.test_client() as client:
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
        with app.test_client() as client:
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
        with app.test_client() as client:
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
        
        with app.test_client() as client:
            # Send a message
            response = client.post(
                '/api/chat/test_session_123/message',
                json={'message': 'I want to travel to Paris'},
                content_type='application/json'
            )
            
            # Check for appropriate error response
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
        
        with app.test_client() as client:
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
        with app.test_client() as client:
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
        
        with app.test_client() as client:
            # Attempt to call an endpoint
            response = client.post('/api/chat/start')
            
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
    
    def create_app(self):
        """Create a test Flask application with session security."""
        app = create_app(testing=True)
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
        
        with app.test_client() as client:
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
        
        with app.test_client() as client:
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
        with app.test_client() as client:
            # No session headers
            response = client.get('/test/secure')
            
            # Should deny access
            self.assertEqual(response.status_code, 401)
            data = json.loads(response.data)
            self.assertIn('error', data)
            self.assertIn('Authentication required', data['error'])

if __name__ == "__main__":
    unittest.main()
