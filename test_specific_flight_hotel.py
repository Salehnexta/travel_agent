#!/usr/bin/env python3
"""
Test script for checking a specific flight and hotel query.
This script tests the travel agent's ability to handle a specific query about
a flight from DMM to RUH tomorrow and a hotel near the Ministry of Manufacturing.
"""

import os
import sys
import json
import time
import logging
from datetime import date, datetime, timedelta
from pprint import pprint

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('test_specific_query')

# Import from travel_agent package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from travel_agent.state_definitions import TravelState, ConversationStage
from travel_agent.graph_builder import TravelAgentGraph
from travel_agent.error_tracking import ErrorTracker

# Initialize error tracker
error_tracker = ErrorTracker('test')

def test_flight_hotel_query():
    """Test the travel agent with a specific flight and hotel query"""
    logger.info("=== Testing Specific Flight and Hotel Query ===")
    
    # Initialize the travel agent graph
    try:
        agent_graph = TravelAgentGraph()
        logger.info("Travel agent graph initialized successfully")
    except Exception as e:
        error_id = error_tracker.track_error(e, {"component": "graph_initialization"})
        logger.error(f"Failed to initialize travel agent graph: {str(e)} (Error ID: {error_id})")
        return False
    
    # Create a new session
    session_id = f"test-{int(time.time())}"
    try:
        state = agent_graph.create_session(session_id)
        logger.info(f"Created new session with ID: {session_id}")
    except Exception as e:
        error_id = error_tracker.track_error(e, {"component": "session_creation"})
        logger.error(f"Failed to create session: {str(e)} (Error ID: {error_id})")
        return False
    
    # Process the query
    query = "test flight from dmm to ruh tomorrow and 1 day hotel near ministry of manufacturing"
    
    try:
        logger.info(f"Processing query: {query}")
        updated_state = agent_graph.process_message(state, query)
        
        # Print conversation history
        logger.info("=== Conversation History ===")
        for message in updated_state.conversation_history:
            role = message['role']
            content = message['content']
            logger.info(f"{role.upper()}: {content}")
        
        # Check extracted parameters
        logger.info("=== Extracted Parameters ===")
        
        # Check destinations
        if updated_state.destinations:
            logger.info("Destinations:")
            for dest in updated_state.destinations:
                logger.info(f"  - {dest.name} (confidence: {dest.confidence:.2f})")
        else:
            logger.warning("No destinations extracted")
            
        # Check origins
        if updated_state.origins:
            logger.info("Origins:")
            for origin in updated_state.origins:
                logger.info(f"  - {origin.name} (confidence: {origin.confidence:.2f})")
        else:
            logger.warning("No origins extracted")
            
        # Check dates
        if updated_state.dates:
            logger.info("Dates:")
            for date_param in updated_state.dates:
                date_value = date_param.date_value if date_param.date_value else "Unknown"
                logger.info(f"  - {date_param.type}: {date_value} (confidence: {date_param.confidence:.2f})")
        else:
            logger.warning("No dates extracted")
        
        # Check travelers
        if updated_state.travelers:
            logger.info(f"Travelers: {updated_state.travelers.adults} adults, {updated_state.travelers.children} children, {updated_state.travelers.infants} infants")
        else:
            logger.warning("No travelers extracted")
        
        # Check preferences
        if updated_state.preferences:
            logger.info("Preferences:")
            for pref in updated_state.preferences:
                logger.info(f"  - {pref.category}: {', '.join(pref.preferences)}")
        else:
            logger.info("No preferences extracted")
        
        # Analyze the results
        flight_recognized = any(dest.name.upper() == "RUH" for dest in updated_state.destinations)
        origin_recognized = any(origin.name.upper() == "DMM" for origin in updated_state.origins)
        tomorrow_recognized = any(date_param.date_value == (date.today() + timedelta(days=1)) for date_param in updated_state.dates if date_param.date_value)
        
        logger.info("=== Analysis ===")
        logger.info(f"Flight destination (RUH) recognized: {flight_recognized}")
        logger.info(f"Flight origin (DMM) recognized: {origin_recognized}")
        logger.info(f"Tomorrow's date recognized: {tomorrow_recognized}")
        
        # Check for hotel near ministry
        hotel_preference_found = False
        ministry_location_found = False
        
        for pref in updated_state.preferences:
            if pref.category.lower() == "hotel":
                hotel_preference_found = True
                logger.info(f"Hotel preferences: {pref.preferences}")
                if any("ministry" in p.lower() for p in pref.preferences):
                    ministry_location_found = True
        
        logger.info(f"Hotel preference found: {hotel_preference_found}")
        logger.info(f"Ministry location recognized: {ministry_location_found}")
        
        return True
    except Exception as e:
        error_id = error_tracker.track_error(e, {"query": query})
        logger.error(f"Error processing query: {str(e)} (Error ID: {error_id})")
        return False

if __name__ == "__main__":
    success = test_flight_hotel_query()
    if success:
        logger.info("Test completed successfully")
        sys.exit(0)
    else:
        logger.error("Test failed")
        sys.exit(1)
