#!/usr/bin/env python
"""
Test script for the LangGraph-based Travel Agent Workflow

This script demonstrates how to use the LangGraph implementation of the travel agent
following LangGraph best practices.
"""

import logging
import json
from dotenv import load_dotenv
from travel_agent.langgraph_workflow import TravelAgentGraphLang, WorkflowStage

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env
load_dotenv()

def test_langgraph_workflow():
    """
    Test the LangGraph travel agent workflow by simulating a conversation.
    Verifies that the graph correctly transitions through different stages.
    """
    # Initialize the graph
    travel_graph = TravelAgentGraphLang()
    
    # Create a new session
    logger.info("=== Starting new conversation ===")
    state = travel_graph.create_session()
    
    # Display initial greeting
    logger.info(f"Assistant: {travel_graph.get_latest_assistant_response(state)}")
    
    # Test 1: Process a booking intent
    logger.info("=== Test 1: Processing booking intent ===")
    user_message = "I want to plan a trip to Paris next month"
    logger.info(f"User: {user_message}")
    
    state = travel_graph.process_message(state, user_message)
    logger.info(f"Next stage: {state['next_stage']}")
    logger.info(f"Assistant: {travel_graph.get_latest_assistant_response(state)}")
    
    # Test 2: Provide more details
    logger.info("=== Test 2: Providing more details ===")
    user_message = "I'd like to stay for 5 days and see the Eiffel Tower"
    logger.info(f"User: {user_message}")
    
    state = travel_graph.process_message(state, user_message)
    logger.info(f"Next stage: {state['next_stage']}")
    logger.info(f"Assistant: {travel_graph.get_latest_assistant_response(state)}")
    
    # Test 3: Ask for hotel information
    logger.info("=== Test 3: Asking for hotel information ===")
    user_message = "Can you recommend some hotels near the Eiffel Tower?"
    logger.info(f"User: {user_message}")
    
    state = travel_graph.process_message(state, user_message)
    logger.info(f"Next stage: {state['next_stage']}")
    logger.info(f"Assistant: {travel_graph.get_latest_assistant_response(state)}")
    
    # Test 4: Thank the assistant
    logger.info("=== Test 4: Thanking the assistant ===")
    user_message = "Thank you for your help!"
    logger.info(f"User: {user_message}")
    
    state = travel_graph.process_message(state, user_message)
    logger.info(f"Next stage: {state['next_stage']}")
    logger.info(f"Assistant: {travel_graph.get_latest_assistant_response(state)}")
    
    logger.info("All tests completed!")
    
    # Print final state (without messages to keep output clean)
    state_copy = state.copy()
    state_copy.pop("messages", None)
    logger.info(f"Final state: {json.dumps(state_copy, indent=2)}")
    
    return state

if __name__ == "__main__":
    try:
        final_state = test_langgraph_workflow()
        print("\nFinal conversation summary:")
        for i, message in enumerate(final_state["messages"]):
            if i > 0:  # Skip the first system message
                print(f"{message['role'].upper()}: {message['content']}")
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}", exc_info=True)
