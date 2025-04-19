#!/usr/bin/env python
"""
Test script for the minimal LangGraph-based Travel Agent

This script demonstrates how to use the minimal LangGraph implementation
designed to show the core LangGraph patterns in a clear way.
"""

import logging
import json
from dotenv import load_dotenv
from travel_agent.langgraph_mini import TravelAgentMini

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env
load_dotenv()

def test_mini_langgraph():
    """
    Test the minimal LangGraph travel agent by simulating a conversation.
    """
    # Initialize the travel agent
    travel_agent = TravelAgentMini()
    
    # Create a new session
    logger.info("=== Starting new conversation ===")
    state = travel_agent.create_session()
    
    # Run the greeting
    state = travel_agent.graph.invoke(state)
    logger.info(f"Assistant: {travel_agent.get_latest_response(state)}")
    
    # Test 1: Process a booking intent
    logger.info("=== Test 1: Processing booking intent ===")
    user_message = "I want to plan a trip to Paris next month"
    logger.info(f"User: {user_message}")
    
    state = travel_agent.process_message(state, user_message)
    logger.info(f"Next node: {state['next']}")
    logger.info(f"Assistant: {travel_agent.get_latest_response(state)}")
    
    # Test 2: Provide more details
    logger.info("=== Test 2: Providing more details ===")
    user_message = "I'd like to stay for 5 days and see the Eiffel Tower"
    logger.info(f"User: {user_message}")
    
    state = travel_agent.process_message(state, user_message)
    logger.info(f"Next node: {state['next']}")
    logger.info(f"Assistant: {travel_agent.get_latest_response(state)}")
    
    # Test 3: Ask for hotel information
    logger.info("=== Test 3: Asking for hotel information ===")
    user_message = "Yes, please suggest some hotels"
    logger.info(f"User: {user_message}")
    
    state = travel_agent.process_message(state, user_message)
    logger.info(f"Next node: {state['next']}")
    logger.info(f"Assistant: {travel_agent.get_latest_response(state)}")
    
    # Test 4: Thank the assistant
    logger.info("=== Test 4: Thanking the assistant ===")
    user_message = "Thank you for your help!"
    logger.info(f"User: {user_message}")
    
    state = travel_agent.process_message(state, user_message)
    logger.info(f"Next node: {state['next']}")
    logger.info(f"Assistant: {travel_agent.get_latest_response(state)}")
    
    logger.info("All tests completed!")
    
    # Print parameters and search results
    logger.info(f"Extracted parameters: {json.dumps(state['parameters'], indent=2)}")
    if state['search_results']:
        logger.info(f"Search results: Found {len(state['search_results']['hotels'])} hotels and {len(state['search_results']['attractions'])} attractions")
    
    return state

if __name__ == "__main__":
    try:
        final_state = test_mini_langgraph()
        print("\nFinal conversation summary:")
        for message in final_state["messages"]:
            print(f"{message['role'].upper()}: {message['content']}")
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}", exc_info=True)
