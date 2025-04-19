from travel_agent.agents.parameter_extraction import ParameterExtractionAgent
from travel_agent.state_definitions import TravelState
import json
import datetime

class MockTravelState:
    def __init__(self):
        self.conversation_history = []
    
    def get_conversation_context(self, num_messages=5):
        return []
    
    def get_latest_user_query(self):
        return "find me flight from dmm to ruh tomorrow one way"

print("Starting travel agent parameter extraction debug...")

# Initialize the parameter extraction agent
agent = ParameterExtractionAgent()

# Create a mock travel state
state = MockTravelState()

# Extract parameters
print("Extracting parameters from: 'find me flight from dmm to ruh tomorrow one way'")
extracted_params = agent._extract_parameters(state.get_latest_user_query(), state)

print("\nExtracted Parameters:")
print(json.dumps(extracted_params, indent=2, default=str))

# Test with tomorrow's date explicitly
tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
print(f"\nTomorrow's date should be: {tomorrow}")

print("\nTest complete.")
