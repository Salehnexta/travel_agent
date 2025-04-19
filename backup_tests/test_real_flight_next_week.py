#!/usr/bin/env python3
"""
Direct test script for searching a flight from DMM to BKK next week using real data.
This test uses actual API calls and search functionality without mocking.
"""

import os
import logging
import json
from datetime import date, timedelta
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("real_flight_test")

# Ensure we can import from the travel_agent package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import travel agent components
from travel_agent.state_definitions import TravelState, ConversationStage, LocationParameter, DateParameter
from travel_agent.search_tools import SearchToolManager
from travel_agent.agents.parameter_extraction import ParameterExtractionAgent
from travel_agent.config.env_manager import get_env_manager  # Use our enhanced env management


def verify_environment():
    """Check if the required API keys are available."""
    env_manager = get_env_manager()
    
    # Check for API keys
    serper_api_key = env_manager.get_api_key("serper")
    deepseek_api_key = env_manager.get_api_key("deepseek")
    groq_api_key = env_manager.get_api_key("groq")
    
    logger.info(f"Serper API available: {bool(serper_api_key)}")
    logger.info(f"DeepSeek API available: {bool(deepseek_api_key)}")
    logger.info(f"Groq API available: {bool(groq_api_key)}")
    
    return bool(serper_api_key)


def manually_extract_parameters(query: str):
    """Extract parameters manually without LLM to avoid API dependency."""
    # Create a state with the user query
    state = TravelState(
        session_id="test_next_week_flight",
        conversation_stage=ConversationStage.PARAMETER_EXTRACTION
    )
    state.add_message("user", query)
    
    # Extract origins and destinations
    if "DMM" in query:
        origin = LocationParameter(
            name="DMM",
            type="origin",
            confidence=1.0
        )
        state.origins.append(origin)
    
    if "BKK" in query:
        destination = LocationParameter(
            name="BKK",
            type="destination",
            confidence=1.0
        )
        state.destinations.append(destination)
    
    # Extract dates
    if "next week" in query or "after 7 days" in query:
        next_week = date.today() + timedelta(days=7)
        date_param = DateParameter(
            type="departure",
            date_value=next_week,
            flexible=True,
            confidence=1.0
        )
        state.dates.append(date_param)
    
    # Set the travelers (default to 1)
    from travel_agent.state_definitions import TravelerParameter
    state.travelers = TravelerParameter(
        adults=1,
        children=0,
        infants=0,
        confidence=1.0
    )
    
    return state


def search_flight_next_week():
    """Search for a flight from DMM to BKK next week using real search."""
    # Verify environment first
    if not verify_environment():
        logger.error("Required API keys not available. Cannot proceed with real search.")
        return {
            "success": False,
            "message": "Required API keys not available"
        }
    
    # Query for flight from DMM to BKK next week
    query = "flight from DMM to BKK next week after 7 days one way"
    logger.info(f"Processing query: {query}")
    
    # Extract parameters manually to avoid LLM dependency
    state = manually_extract_parameters(query)
    
    # Create a search tool manager
    try:
        search_manager = SearchToolManager()
        logger.info("Created search manager")
        
        # Get necessary parameters from state
        origin = state.origins[0].name if state.origins else None
        destination = state.destinations[0].name if state.destinations else None
        date_value = state.dates[0].date_value if state.dates else None
        
        if not (origin and destination and date_value):
            logger.error("Missing required parameters for search")
            return {
                "success": False,
                "message": "Missing required parameters",
                "state": state.model_dump()
            }
        
        # Format date for search
        departure_date = date_value.isoformat()
        
        # Log search parameters
        logger.info(f"Searching flight from {origin} to {destination} on {departure_date}")
        
        # Execute flight search
        flight_results = search_manager.search_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,  # Use the correct parameter name
            return_date=None  # One-way flight
        )
        
        # Log search completion
        logger.info("Flight search completed")
        
        # Add results to state
        from travel_agent.state_definitions import SearchResult
        if flight_results:
            search_result = SearchResult(
                type="flight",
                source="serper",
                data=flight_results
            )
            state.add_search_result(search_result)
        
        # Return results
        return {
            "success": True,
            "parameters": {
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
            },
            "flight_results_available": bool(flight_results and "_metadata" in flight_results),
            "state": state.model_dump(),
            "flight_results": flight_results
        }
        
    except Exception as e:
        logger.error(f"Error in flight search: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": str(e)
        }


if __name__ == "__main__":
    logger.info("Starting Real Flight Search Test (DMM to BKK next week)")
    
    try:
        results = search_flight_next_week()
        
        print("\n===== TEST RESULTS =====")
        print(f"Success: {results.get('success', False)}")
        
        if results.get('success', False):
            parameters = results.get('parameters', {})
            print(f"\nOrigin: {parameters.get('origin')}")
            print(f"Destination: {parameters.get('destination')}")
            print(f"Departure Date: {parameters.get('departure_date')}")
            
            print(f"\nFlight results available: {results.get('flight_results_available', False)}")
            
            if results.get('flight_results_available', False):
                flight_results = results.get('flight_results', {})
                print("\n--- Flight Search Results ---")
                
                # Display search metadata
                metadata = flight_results.get("_metadata", {})
                if metadata:
                    print(f"Query: {metadata.get('query')}")
                    print(f"Latency: {metadata.get('latency', 0):.2f} seconds")
                
                # Display organic results (top 3)
                organic = flight_results.get("organic", [])
                if organic:
                    print("\nTop Flight Options:")
                    for i, result in enumerate(organic[:3], 1):
                        print(f"  {i}. {result.get('title', 'No title')}")
                        print(f"     {result.get('snippet', 'No description')[:100]}...")
                
                # Display "People Also Ask" questions
                paa = flight_results.get("peopleAlsoAsk", [])
                if paa:
                    print("\nRelated Questions:")
                    for i, question in enumerate(paa[:3], 1):
                        print(f"  {i}. {question.get('question', 'No question')}")
        else:
            print(f"\nError: {results.get('message', 'Unknown error')}")
        
    except Exception as e:
        logger.error(f"Error running test: {str(e)}", exc_info=True)
        print(f"\n❌ TEST FAILED: {str(e)}")
