import os
import json
import logging
from dotenv import load_dotenv

from travel_agent.graph_builder import TravelAgentGraph
from travel_agent.state_definitions import TravelState

# Configure logging to see detailed output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def test_arabic_flight_recognition():
    """Test flight recognition with Arabic query"""
    
    # Initialize the travel agent graph
    print("\n--- Initializing Travel Agent Graph ---")
    agent_graph = TravelAgentGraph()
    
    # Create a new session
    print("\n--- Creating New Session ---")
    state = agent_graph.create_session()
    
    # Get the initial greeting
    print("\n--- Initial Greeting ---")
    greeting = None
    for message in state.conversation_history:
        if message['role'] == 'assistant':
            greeting = message['content']
    print(f"Assistant: {greeting}")
    
    # Process a direct flight request in Arabic
    print("\n--- Processing Arabic Flight Request ---")
    # "Find me a one-way flight from DMM to RUH tomorrow" in Arabic
    flight_request = "ابحث لي عن رحلة طيران من الدمام إلى الرياض غدًا ذهاب فقط"
    print(f"User: {flight_request}")
    
    # Process the message
    updated_state = agent_graph.process_message(state, flight_request)
    
    # Print the response
    print("\n--- Response ---")
    response = None
    for message in reversed(updated_state.conversation_history):
        if message['role'] == 'assistant':
            response = message['content']
            break
    print(f"Assistant: {response}")
    
    # Print the updated state for debugging
    print("\n--- State Information ---")
    print(f"Conversation Stage: {updated_state.conversation_stage}")
    print(f"Origins: {updated_state.origins if hasattr(updated_state, 'origins') else None}")
    print(f"Destinations: {updated_state.destinations if hasattr(updated_state, 'destinations') else None}")
    print(f"Dates: {updated_state.dates if hasattr(updated_state, 'dates') else None}")
    print(f"Parameters: {updated_state.parameters if hasattr(updated_state, 'parameters') else None}")
    
    return updated_state

if __name__ == "__main__":
    test_arabic_flight_recognition()
