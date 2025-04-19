import logging
import json
import datetime
import uuid
from typing import Dict, Any, List, Optional

from travel_agent.agents.parameter_extraction import ParameterExtractionAgent
from travel_agent.state_definitions import TravelState, ConversationStage

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_parameters(user_query):
    """
    Test parameter extraction for a given user query
    """
    print(f"\nProcessing user query: '{user_query}'")
    
    # Initialize state with session ID and user message
    session_id = str(uuid.uuid4())
    state = TravelState(session_id=session_id)
    state.add_message("user", user_query)
    
    # Parameter Extraction
    parameter_agent = ParameterExtractionAgent()
    updated_state = parameter_agent.process(state)
    
    # Check extraction results
    print("\nExtracted Parameters:")
    print(f"Origins: {[o.model_dump() for o in updated_state.origins]}")
    print(f"Destinations: {[d.model_dump() for d in updated_state.destinations]}")
    print(f"Dates: {[d.model_dump() for d in updated_state.dates]}")
    print(f"Trip type: {[p.model_dump() for p in updated_state.preferences if 'trip' in str(p.preferences).lower()]}")
    print(f"Travelers: {updated_state.travelers.model_dump() if updated_state.travelers else None}")
    
    # Print correct date for temporal references
    tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"\nTemporal reference check:")
    print(f"Tomorrow's date should be: {tomorrow}")
    
    return updated_state

# Test with different user queries
def run_tests():
    print("Starting parameter extraction tests...")
    
    # Test cases focused on the DMM to RUH flight example
    test_queries = [
        "find me flight from dmm to ruh tomorrow one way",
        "flight from dmm to ruh next week",
        "i need a plane ticket from dmm to jed this weekend"
    ]
    
    # Run test for first query only
    extract_parameters(test_queries[0])
    
    print("\nTest complete.")

if __name__ == "__main__":
    run_tests()
