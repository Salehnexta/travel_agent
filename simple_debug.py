import logging
import json
import datetime
import uuid
from travel_agent.agents.parameter_extraction import ParameterExtractionAgent
from travel_agent.state_definitions import TravelState, ConversationStage

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockTravelState:
    """Simple mock state for testing parameter extraction"""
    def __init__(self, user_query):
        self.query = user_query
        self.conversation_history = [{"role": "user", "content": user_query}]
    
    def get_conversation_context(self, num_messages=5):
        return self.conversation_history
    
    def get_latest_user_query(self):
        return self.query

def test_extraction(user_query):
    """Test the parameter extraction for a given query"""
    print(f"\nTesting parameter extraction for: '{user_query}'")
    
    # Create mock state
    mock_state = MockTravelState(user_query)
    
    # Create parameter extraction agent
    agent = ParameterExtractionAgent()
    
    # Extract parameters directly (don't update state)
    extracted_params = agent._extract_parameters(user_query, mock_state)
    
    # Print results
    print("\nExtracted Parameters:")
    print(json.dumps(extracted_params, indent=2, default=str))
    
    # Print correct date for tomorrow
    tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"\nReference: Tomorrow's date should be {tomorrow}")
    
    return extracted_params

# List of test queries
test_queries = [
    "find me flight from dmm to ruh tomorrow one way",
    "flight from dmm to dxb next week",
    "i need a one-way ticket from JED to CAI on friday"
]

# Run the first test query
if __name__ == "__main__":
    print("===== PARAMETER EXTRACTION TEST =====")
    test_extraction(test_queries[0])
    print("\nTest complete")
