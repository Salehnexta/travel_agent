#!/usr/bin/env python
"""
Test script to verify Redis state persistence for the travel agent application.
This script tests storing and retrieving state from Redis.
"""

import os
import json
import uuid
from datetime import datetime, timedelta
import logging

from travel_agent.config.redis_client import RedisManager
from travel_agent.state_definitions import TravelState, LocationParameter, DateParameter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("redis_test")

def test_redis_persistence():
    """Test Redis state persistence functionality"""
    # Initialize Redis manager
    redis_manager = RedisManager()
    
    # Check Redis connection
    if not redis_manager.health_check():
        logger.error("❌ Redis connection failed. Make sure Redis is running.")
        return False
    
    logger.info("✅ Redis connection successful")
    
    # Create a unique test key
    test_session_id = f"test_{uuid.uuid4()}"
    test_key = f"travel_agent:test:{test_session_id}"
    
    # Create a test state with travel parameters
    state = TravelState(session_id=test_session_id)
    
    # Add some data to the state
    state.add_destination(LocationParameter(
        name="Bangkok",
        code="BKK",
        confidence=0.9
    ))
    
    # Add tomorrow as the departure date
    tomorrow = datetime.now().date() + timedelta(days=1)
    state.add_date(DateParameter(
        type="departure",
        date_value=tomorrow,
        flexible=False,
        confidence=0.9
    ))
    
    # Convert to dictionary for storage
    state_dict = state.model_dump()
    
    try:
        # Store in Redis with 5 minute expiration
        logger.info(f"Storing test data in Redis with key: {test_key}")
        result = redis_manager.store_json(test_key, state_dict, expire=300)
        
        if not result:
            logger.error("❌ Failed to store data in Redis")
            return False
        
        logger.info("✅ Successfully stored data in Redis")
        
        # Retrieve from Redis
        logger.info(f"Retrieving data from Redis with key: {test_key}")
        retrieved_data = redis_manager.get_json(test_key)
        
        if not retrieved_data:
            logger.error("❌ Failed to retrieve data from Redis")
            return False
        
        logger.info("✅ Successfully retrieved data from Redis")
        
        # Print the data for debugging
        logger.info(f"Original state dict: {json.dumps(state_dict, indent=2, default=str)}")
        logger.info(f"Retrieved data: {json.dumps(retrieved_data, indent=2, default=str)}")
        
        # Verify data integrity - check if destinations exists and has content
        if not retrieved_data.get("destinations"):
            logger.error(f"❌ Data integrity check failed. 'destinations' not found in retrieved data")
            return False
            
        # Get the destination name from the retrieved data
        retrieved_destination = retrieved_data.get("destinations", [])[0]
        name = None
        
        if isinstance(retrieved_destination, dict):
            name = retrieved_destination.get("name")
        
        logger.info(f"Retrieved destination: {retrieved_destination}")
        logger.info(f"Retrieved destination name: {name}")
        
        if name != "Bangkok":
            logger.error(f"❌ Data integrity check failed. Expected 'Bangkok', got '{name}'")
            return False
        
        logger.info("✅ Data integrity check passed")
        
        # Clean up
        redis_manager.delete(test_key)
        logger.info(f"Cleaned up test data (key: {test_key})")
        
        return True
    
    except Exception as e:
        logger.error(f"❌ Error during Redis test: {str(e)}")
        # Attempt cleanup even if test failed
        try:
            redis_manager.delete(test_key)
        except:
            pass
        return False

if __name__ == "__main__":
    logger.info("===== Starting Redis Persistence Test =====")
    
    # Check if Redis URL is set
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        logger.warning("⚠️ REDIS_URL environment variable not set, using default localhost:6379")
    
    # Run the test
    success = test_redis_persistence()
    
    if success:
        logger.info("🎉 All Redis persistence tests PASSED!")
    else:
        logger.error("❌ Redis persistence tests FAILED!")
    
    logger.info("===== Redis Test Complete =====")
