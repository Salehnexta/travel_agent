#!/usr/bin/env python3
"""
Integration tests for Redis and TravelState.
Tests that state can be properly stored, retrieved, and updated in Redis.
"""

import unittest
import sys
import os
import json
import uuid
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import components to test
from travel_agent.config.redis_client import RedisManager
from travel_agent.state_definitions import (
    TravelState, 
    ConversationStage,
    LocationParameter,
    DateParameter
)


class TestRedisStateIntegration(unittest.TestCase):
    """Test the integration between Redis and TravelState."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a mock Redis client
        self.mock_redis = MagicMock()
        
        # Initialize RedisManager with mock Redis
        self.redis_manager = RedisManager(redis_url="mock://localhost")
        self.redis_manager.client = self.mock_redis
        
        # Create a test TravelState
        self.session_id = f"test_{uuid.uuid4().hex[:8]}"
        self.travel_state = TravelState(
            session_id=self.session_id,
            conversation_stage=ConversationStage.INITIAL
        )
        
        # Add some data to the state
        self.travel_state.add_message("user", "Hello travel agent")
        self.travel_state.add_message("assistant", "How can I help you with your travel plans?")
    
    def test_save_and_retrieve_state(self):
        """Test saving and retrieving state from Redis."""
        # Configure mock
        self.mock_redis.set.return_value = True
        self.mock_redis.get.return_value = json.dumps(self.travel_state.dict())
        
        # Save state to Redis
        key = f"travel_agent:state:{self.session_id}"
        success = self.redis_manager.set_json(key, self.travel_state.dict())
        
        # Verify save operation
        self.assertTrue(success)
        self.mock_redis.set.assert_called_once()
        
        # Retrieve state from Redis
        state_dict = self.redis_manager.get_json(key)
        
        # Verify retrieve operation
        self.mock_redis.get.assert_called_once_with(key)
        self.assertIsNotNone(state_dict)
        
        # Reconstruct TravelState from retrieved data
        retrieved_state = TravelState.model_validate(state_dict)
        
        # Verify state is equivalent to original
        self.assertEqual(retrieved_state.session_id, self.session_id)
        self.assertEqual(retrieved_state.conversation_stage, ConversationStage.INITIAL)
        self.assertEqual(len(retrieved_state.messages), 2)
        self.assertEqual(retrieved_state.messages[0].role, "user")
        self.assertEqual(retrieved_state.messages[0].content, "Hello travel agent")
    
    def test_update_existing_state(self):
        """Test updating an existing state in Redis."""
        # Initial state in Redis
        initial_state = self.travel_state.dict()
        
        # Configure mock for initial get
        self.mock_redis.get.return_value = json.dumps(initial_state)
        
        # Retrieve state
        key = f"travel_agent:state:{self.session_id}"
        state_dict = self.redis_manager.get_json(key)
        retrieved_state = TravelState.model_validate(state_dict)
        
        # Modify state
        retrieved_state.add_message("user", "I want to travel to Paris")
        retrieved_state.add_origin(LocationParameter(name="New York", type="origin", confidence=0.9))
        retrieved_state.add_destination(LocationParameter(name="Paris", type="destination", confidence=0.95))
        retrieved_state.conversation_stage = ConversationStage.PARAMETER_EXTRACTION
        
        # Configure mock for set
        self.mock_redis.set.return_value = True
        
        # Save updated state
        success = self.redis_manager.set_json(key, retrieved_state.dict())
        
        # Verify save operation
        self.assertTrue(success)
        self.mock_redis.set.assert_called_once()
        
        # Verify the updated state was saved correctly
        args, kwargs = self.mock_redis.set.call_args
        saved_data = json.loads(kwargs.get('value', args[1]))
        
        self.assertEqual(saved_data['session_id'], self.session_id)
        self.assertEqual(saved_data['conversation_stage'], ConversationStage.PARAMETER_EXTRACTION.value)
        self.assertEqual(len(saved_data['messages']), 3)
        self.assertEqual(saved_data['messages'][2]['content'], "I want to travel to Paris")
        self.assertEqual(len(saved_data['origins']), 1)
        self.assertEqual(saved_data['origins'][0]['name'], "New York")
        self.assertEqual(len(saved_data['destinations']), 1)
        self.assertEqual(saved_data['destinations'][0]['name'], "Paris")
    
    def test_state_expiry(self):
        """Test that state expiry is set correctly."""
        # Configure mock
        self.mock_redis.set.return_value = True
        
        # Save state with expiry
        key = f"travel_agent:state:{self.session_id}"
        expiry = 3600  # 1 hour
        success = self.redis_manager.set_json(key, self.travel_state.dict(), ex=expiry)
        
        # Verify save operation with expiry
        self.assertTrue(success)
        self.mock_redis.set.assert_called_once()
        
        # Check that expiry was set
        args, kwargs = self.mock_redis.set.call_args
        self.assertEqual(kwargs.get('ex', None), expiry)
    
    def test_state_not_found(self):
        """Test behavior when state is not found in Redis."""
        # Configure mock to return None (key not found)
        self.mock_redis.get.return_value = None
        
        # Try to retrieve non-existent state
        key = f"travel_agent:state:non_existent_session"
        state_dict = self.redis_manager.get_json(key)
        
        # Verify retrieve operation
        self.mock_redis.get.assert_called_once_with(key)
        self.assertIsNone(state_dict)
    
    def test_redis_error_handling(self):
        """Test error handling for Redis operations."""
        # Configure mock to raise an exception
        self.mock_redis.get.side_effect = Exception("Redis connection error")
        
        # Try to retrieve state with error
        key = f"travel_agent:state:{self.session_id}"
        
        # Should not raise exception but return None
        state_dict = self.redis_manager.get_json(key)
        self.assertIsNone(state_dict)
        
        # Configure mock set to raise exception
        self.mock_redis.set.side_effect = Exception("Redis connection error")
        
        # Try to save state with error
        # Should not raise exception but return False
        success = self.redis_manager.set_json(key, self.travel_state.dict())
        self.assertFalse(success)

class TestTravelStateWithFallback(unittest.TestCase):
    """Test TravelState persistence with Redis fallback mechanism."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a real RedisManager but patch its client
        self.patcher = patch('travel_agent.config.redis_client.redis.from_url')
        self.mock_redis_factory = self.patcher.start()
        self.mock_redis = MagicMock()
        self.mock_redis_factory.return_value = self.mock_redis
        
        # Create a travel state with a real session ID
        self.session_id = f"fallback_test_{uuid.uuid4().hex[:8]}"
        self.travel_state = TravelState(
            session_id=self.session_id,
            conversation_stage=ConversationStage.INITIAL
        )
        
        # Create sample data for testing
        self.travel_state.add_message("user", "I want to fly from NYC to London")
        self.travel_state.add_message("assistant", "When would you like to travel?")
        self.travel_state.add_origin(LocationParameter(name="New York", type="origin", confidence=0.9))
        self.travel_state.add_destination(LocationParameter(name="London", type="destination", confidence=0.95))
    
    def tearDown(self):
        """Clean up after tests."""
        self.patcher.stop()
        
        # Clean up any temporary files created by fallback mechanism
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'temp_cache')
        if os.path.exists(cache_dir):
            for filename in os.listdir(cache_dir):
                if filename.startswith(f"travel_agent_state_{self.session_id}"):
                    os.remove(os.path.join(cache_dir, filename))
    
    @patch('travel_agent.error_handling.fallbacks.FallbackService.fallback_redis')
    def test_redis_fallback_when_redis_down(self, mock_fallback_redis):
        """Test that state is saved to fallback when Redis is down."""
        # Import the error handling integration
        from travel_agent.error_handling.integration import redis_with_fallback
        
        # Apply the decorator to RedisManager methods
        RedisManager.get_json = redis_with_fallback('get')(RedisManager.get_json)
        RedisManager.set_json = redis_with_fallback('set')(RedisManager.set_json)
        
        # Create a RedisManager instance
        redis_manager = RedisManager(redis_url="redis://localhost")
        
        # Configure Redis to fail
        self.mock_redis.get.side_effect = Exception("Redis is down")
        self.mock_redis.set.side_effect = Exception("Redis is down")
        
        # Configure fallback to succeed
        mock_fallback_redis.return_value = self.travel_state.dict()
        
        # Try to save state - should use fallback
        key = f"travel_agent:state:{self.session_id}"
        redis_manager.set_json(key, self.travel_state.dict())
        
        # Verify fallback was called
        mock_fallback_redis.assert_called_with('set', key, self.travel_state.dict())
        
        # Try to retrieve state - should use fallback
        state_dict = redis_manager.get_json(key)
        
        # Verify fallback was called for get
        mock_fallback_redis.assert_called_with('get', key)
        
        # Verify state was retrieved correctly
        self.assertIsNotNone(state_dict)
        self.assertEqual(state_dict['session_id'], self.session_id)
        self.assertEqual(state_dict['conversation_stage'], ConversationStage.INITIAL.value)
        self.assertEqual(len(state_dict['messages']), 2)
        self.assertEqual(len(state_dict['origins']), 1)
        self.assertEqual(state_dict['origins'][0]['name'], "New York")

class TestTravelAgentStateMigration(unittest.TestCase):
    """Test TravelState migration and backward compatibility."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a mock Redis client
        self.mock_redis = MagicMock()
        
        # Initialize RedisManager with mock Redis
        self.redis_manager = RedisManager(redis_url="mock://localhost")
        self.redis_manager.client = self.mock_redis
        
        # Create a session ID
        self.session_id = f"migration_test_{uuid.uuid4().hex[:8]}"
        
        # Create an old format state (missing newer fields)
        self.old_state = {
            "session_id": self.session_id,
            "conversation_stage": "INITIAL",
            "messages": [
                {"role": "user", "content": "Hello travel agent"},
                {"role": "assistant", "content": "How can I help you?"}
            ],
            "origins": [],
            "destinations": [],
            "dates": [],
            # Missing newer fields like "extracted_parameters"
        }
    
    def test_backward_compatibility(self):
        """Test loading an old state format into new TravelState model."""
        # Configure mock to return old state format
        self.mock_redis.get.return_value = json.dumps(self.old_state)
        
        # Try to retrieve and parse old state
        key = f"travel_agent:state:{self.session_id}"
        state_dict = self.redis_manager.get_json(key)
        
        # Should be able to load into current TravelState model
        # without errors, with defaults for missing fields
        state = TravelState.model_validate(state_dict)
        
        # Verify basic fields were loaded
        self.assertEqual(state.session_id, self.session_id)
        self.assertEqual(state.conversation_stage, ConversationStage.INITIAL)
        self.assertEqual(len(state.messages), 2)
        
        # Verify defaults for missing fields
        self.assertEqual(state.extracted_parameters, set())
        
        # Modify state with new fields
        state.extracted_parameters.add("origin")
        state.add_origin(LocationParameter(name="New York", type="origin", confidence=0.9))
        
        # Configure mock for saving
        self.mock_redis.set.return_value = True
        
        # Save updated state
        success = self.redis_manager.set_json(key, state.dict())
        
        # Verify save operation
        self.assertTrue(success)
        
        # Check that new format was saved
        args, kwargs = self.mock_redis.set.call_args
        saved_data = json.loads(kwargs.get('value', args[1]))
        
        self.assertIn('extracted_parameters', saved_data)
        self.assertEqual(saved_data['extracted_parameters'], ["origin"])

if __name__ == "__main__":
    unittest.main()
