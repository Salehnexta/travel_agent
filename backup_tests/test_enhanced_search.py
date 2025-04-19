"""
Test the enhanced search functionality with result parsing
"""
import os
import json
import logging
import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import search tools
from travel_agent.search_tools import SearchToolManager
from travel_agent.search_result_parser import SearchResultParser

def test_enhanced_flight_search():
    """
    Test enhanced flight search with result parsing
    """
    print("\n===== TESTING ENHANCED FLIGHT SEARCH =====")
    
    # Initialize search tools
    search_tool = SearchToolManager()
    
    # Set search parameters
    origin = "DMM"  # Dammam
    destination = "RUH"  # Riyadh
    date = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")  # Tomorrow
    
    print(f"Searching for flights: {origin} to {destination} on {date}")
    
    try:
        # Make the search request
        raw_results = search_tool.search(
            query=f"flights from {origin} to {destination} on {date}",
            search_type="organic",
            location=None
        )
        
        # Parse the results into structured flight data
        params = {
            "origin": origin,
            "destination": destination,
            "date": date
        }
        structured_flights = SearchResultParser.process_search_results(raw_results, "flight", params)
        
        # Print structured results
        print("\nStructured Flight Results:")
        print(json.dumps(structured_flights, indent=2))
        
        return structured_flights
    except Exception as e:
        print(f"Error in enhanced flight search: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None

if __name__ == "__main__":
    print("Testing enhanced search with result parsing...")
    test_enhanced_flight_search()
