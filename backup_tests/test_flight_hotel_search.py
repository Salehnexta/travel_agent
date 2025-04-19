#!/usr/bin/env python3
"""
Comprehensive test for the travel agent's flight and hotel search functionality.
Tests the specific DMM to BKK flight for tomorrow and hotel search near destination.
"""

import os
import logging
import sys
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("e2e_test")

# Add parent directory to path to allow importing travel_agent
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from travel_agent.state_definitions import (
    TravelState, 
    ConversationStage,
    LocationParameter,
    DateParameter,
    TravelerParameter,
    PreferenceParameter
)
from travel_agent.graph_builder import TravelAgentGraph


def check_apis_available():
    """Check if required API keys are available."""
    deepseek_available = bool(os.getenv("DEEPSEEK_API_KEY"))
    groq_available = bool(os.getenv("GROQ_API_KEY"))
    serper_available = bool(os.getenv("SERPER_API_KEY"))
    
    logger.info(f"DeepSeek API available: {deepseek_available}")
    logger.info(f"Groq API available: {groq_available}")
    logger.info(f"Serper API available: {serper_available}")
    
    return deepseek_available, groq_available, serper_available


def test_flight_hotel_search():
    """
    Test the travel agent's ability to handle flight and hotel search
    for DMM to BKK tomorrow with hotel preferences.
    """
    # Check if APIs are available
    deepseek_available, groq_available, serper_available = check_apis_available()
    
    # If Serper API is not available, we can't perform search tests
    if not serper_available:
        logger.warning("Serper API key not available, skipping search test")
        return {
            "success": False,
            "message": "Serper API key not available"
        }
    
    # Create a travel agent graph
    graph = TravelAgentGraph()
    
    # Create a test session for DMM to BKK flight tomorrow
    flight_query = "I need a flight from DMM to BKK tomorrow one way and a hotel near the city center"
    
    # Create state and add the message
    state = graph.create_session("test_flight_hotel")
    
    # Process the message through the graph
    result_state = graph.process_message(state, flight_query)
    
    # Validate that the state has been updated correctly
    has_dmm_origin = any(o.name == "DMM" for o in result_state.origins)
    has_bkk_destination = any(d.name == "BKK" for d in result_state.destinations)
    
    # Check if tomorrow's date was extracted
    tomorrow = date.today() + timedelta(days=1)
    has_tomorrow = any(d.date_value and d.date_value == tomorrow for d in result_state.dates)
    
    # Check if hotel preference was recognized
    has_hotel_preference = False
    for pref in result_state.preferences:
        if pref.category.lower() == "hotel" and any("city center" in p.lower() for p in pref.preferences):
            has_hotel_preference = True
            break
    
    # Check if search results are available
    has_flight_results = "flight" in result_state.search_results and result_state.search_results["flight"]
    has_hotel_results = "hotel" in result_state.search_results and result_state.search_results["hotel"]
    
    # Print validation results
    logger.info(f"Has DMM origin: {has_dmm_origin}")
    logger.info(f"Has BKK destination: {has_bkk_destination}")
    logger.info(f"Has tomorrow date: {has_tomorrow}")
    logger.info(f"Has hotel preference: {has_hotel_preference}")
    logger.info(f"Has flight results: {has_flight_results}")
    logger.info(f"Has hotel results: {has_hotel_results}")
    
    # Return the results
    results = {
        "success": has_dmm_origin and has_bkk_destination and has_tomorrow,
        "has_flight_results": has_flight_results,
        "has_hotel_results": has_hotel_results,
        "has_hotel_preference": has_hotel_preference,
        "origins": [o.model_dump() for o in result_state.origins],
        "destinations": [d.model_dump() for d in result_state.destinations],
        "dates": [d.model_dump() for d in result_state.dates],
        "preferences": [p.model_dump() for p in result_state.preferences]
    }
    
    return results


if __name__ == "__main__":
    logger.info("Starting Flight and Hotel Search Test")
    
    try:
        results = test_flight_hotel_search()
        
        # Print results summary
        print("\n===== TEST RESULTS =====")
        if results.get("success", False):
            print("✅ Basic parameter extraction: SUCCESS")
        else:
            print("❌ Basic parameter extraction: FAILED")
        
        print(f"\nOrigin DMM extracted: {'✅' if any('DMM' in str(o) for o in results.get('origins', [])) else '❌'}")
        print(f"Destination BKK extracted: {'✅' if any('BKK' in str(d) for d in results.get('destinations', [])) else '❌'}")
        print(f"Tomorrow's date extracted: {'✅' if any(str(date.today() + timedelta(days=1)) in str(d) for d in results.get('dates', [])) else '❌'}")
        print(f"Hotel preference extracted: {'✅' if results.get('has_hotel_preference', False) else '❌'}")
        
        print(f"\nFlight search executed: {'✅' if results.get('has_flight_results', False) else '❌'}")
        print(f"Hotel search executed: {'✅' if results.get('has_hotel_results', False) else '❌'}")
        
        print("\n===== DETAILED RESULTS =====")
        for category, items in results.items():
            if category not in ["success", "has_flight_results", "has_hotel_results", "has_hotel_preference"]:
                print(f"\n{category.upper()}:")
                for item in items:
                    print(f"  - {item}")
        
    except Exception as e:
        logger.error(f"Error running test: {str(e)}", exc_info=True)
        print(f"\n❌ TEST FAILED: {str(e)}")
