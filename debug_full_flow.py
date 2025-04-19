import logging
import json
import datetime
from typing import Dict, Any, List, Optional

from travel_agent.agents.parameter_extraction import ParameterExtractionAgent
from travel_agent.agents.search_manager import SearchManager
from travel_agent.state_definitions import TravelState, DateParameter, LocationParameter, ConversationStage

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TestTravelState(TravelState):
    """Testing implementation of TravelState with minimal required functionality."""
    
    def __init__(self):
        self.conversation_history = []
        self.conversation_stage = ConversationStage.PARAMETER_EXTRACTION
        self.origins = []
        self.destinations = []
        self.dates = []
        self.travelers = None
        self.budget = None
        self.preferences = []
        self.search_results = {}
        self.errors = []
        
    def get_conversation_context(self, num_messages=5):
        return self.conversation_history[-num_messages:] if self.conversation_history else []
    
    def get_latest_user_query(self):
        return "find me flight from dmm to ruh tomorrow one way"
    
    def add_message(self, role, content):
        self.conversation_history.append({"role": role, "content": content})
        return self
        
    def add_origin(self, origin):
        self.origins.append(origin)
        return self
        
    def add_destination(self, destination):
        self.destinations.append(destination)
        return self
    
    def add_date(self, date):
        self.dates.append(date)
        return self
    
    def get_primary_destination(self):
        return self.destinations[0] if self.destinations else None
    
    def get_primary_date_range(self):
        return self.dates[0] if self.dates else None
    
    def update_conversation_stage(self, stage):
        self.conversation_stage = stage
        return self
    
    def log_error(self, error_type, error_data):
        self.errors.append({"type": error_type, **error_data})
        return self
    
    def has_minimum_parameters(self):
        return len(self.destinations) > 0 and len(self.dates) > 0

# Run the test
def run_test():
    print("Starting full travel agent flow test...")
    
    # Initialize state with user message
    state = TestTravelState()
    user_query = "find me flight from dmm to ruh tomorrow one way"
    state.add_message("user", user_query)
    
    print(f"\nProcessing user query: '{user_query}'")
    
    # Stage 1: Parameter Extraction
    print("\n==== STAGE 1: PARAMETER EXTRACTION ====")
    parameter_agent = ParameterExtractionAgent()
    state = parameter_agent.process(state)
    
    print("\nExtracted Parameters:")
    print(f"Origins: {[o.name for o in state.origins]}")
    print(f"Destinations: {[d.name for d in state.destinations]}")
    
    # Print date info with tomorrow's correct date
    tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"Dates: {[(d.type, getattr(d, 'date_value', None) or getattr(d, 'start_date', None)) for d in state.dates]}")
    print(f"Note: 'tomorrow' should be {tomorrow}")
    
    # Stage 2: Search
    print("\n==== STAGE 2: SEARCH ====")
    try:
        search_manager = SearchManager()
        state = search_manager.process(state)
        
        print("\nSearch Results:")
        if state.search_results:
            print(json.dumps(state.search_results, indent=2, default=str))
        else:
            print("No search results or search failed")
            if state.errors:
                print(f"Errors: {state.errors}")
    except Exception as e:
        print(f"Search failed with error: {str(e)}")
    
    print("\nTest complete.")
    return state

if __name__ == "__main__":
    run_test()
