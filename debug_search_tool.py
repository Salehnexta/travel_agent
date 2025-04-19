import os
import json
import logging
import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import search tools directly to bypass other components
from travel_agent.search_tools import SearchToolManager

def test_direct_search_flight():
    """
    Test direct flight search using SearchToolManager
    """
    print("\n===== TESTING DIRECT FLIGHT SEARCH =====")
    
    # Initialize search tools
    search_tool = SearchToolManager()
    
    # Tomorrow's date in ISO format
    tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Test parameters
    origin = "DMM"  # Dammam
    destination = "RUH"  # Riyadh
    date = tomorrow
    travelers = 1
    
    print(f"Searching for flights: {origin} to {destination} on {date} for {travelers} traveler(s)")
    
    try:
        # Make a direct API call to search for flights
        result = search_tool.search(
            query=f"flights from {origin} to {destination} on {date}",
            search_type="organic",
            location=None
        )
        
        # Print the result
        print("\nSearch API Response:")
        print(json.dumps(result, indent=2, default=str))
        
        return result
    except Exception as e:
        print(f"Error in search: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None

def test_direct_hotel_search():
    """
    Test direct hotel search using SearchToolManager
    """
    print("\n===== TESTING DIRECT HOTEL SEARCH =====")
    
    # Initialize search tools
    search_tool = SearchToolManager()
    
    # Tomorrow and day after for check-in/out
    tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    day_after = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime("%Y-%m-%d")
    
    # Test parameters
    location = "Riyadh"
    check_in = tomorrow
    check_out = day_after
    num_people = 1
    
    print(f"Searching for hotels in {location} from {check_in} to {check_out} for {num_people} guest(s)")
    
    try:
        # Make a direct API call to search for hotels
        query = f"hotels in {location} check in {check_in} check out {check_out} for {num_people} guest"
        result = search_tool.search(
            query=query,
            search_type="organic",
            location=location
        )
        
        # Print the result
        print("\nSearch API Response:")
        print(json.dumps(result, indent=2, default=str))
        
        return result
    except Exception as e:
        print(f"Error in search: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None

# Run the tests
if __name__ == "__main__":
    # Check API key
    serper_api_key = os.getenv("SERPER_API_KEY")
    if not serper_api_key:
        print("ERROR: SERPER_API_KEY environment variable is not set")
        exit(1)
    
    # Run flight search test
    flight_result = test_direct_search_flight()
    
    # Run hotel search test
    hotel_result = test_direct_hotel_search()
