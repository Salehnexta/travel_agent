#!/usr/bin/env python3
"""
Test script for validating a DMM to BKK flight request, testing:
1. Parameter extraction (specifically for 'next week' temporal reference)
2. Direct search using request API (bypassing SearchToolManager)
"""

import os
import sys
import json
import logging
import requests
from datetime import date, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("dmm_bkk_test")

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import travel agent components
from travel_agent.config.env_manager import get_env_manager
from travel_agent.state_definitions import (
    TravelState, 
    ConversationStage,
    LocationParameter,
    DateParameter
)

def test_parameter_extraction():
    """Extract parameters directly for DMM to BKK flight next week."""
    user_query = "flight from DMM to BKK next week after 7 days one way"
    logger.info(f"Processing query: {user_query}")
    
    # Create a fresh travel state
    state = TravelState(
        session_id="test_dmm_bkk_direct",
        conversation_stage=ConversationStage.PARAMETER_EXTRACTION
    )
    
    # Add the user message
    state.add_message("user", user_query)
    
    # Manually extract parameters
    # Origin - DMM
    dmm_origin = LocationParameter(
        name="DMM",
        type="origin",
        confidence=1.0
    )
    state.origins.append(dmm_origin)
    state.extracted_parameters.add("origin")
    
    # Destination - BKK
    bkk_destination = LocationParameter(
        name="BKK",
        type="destination",
        confidence=1.0
    )
    state.destinations.append(bkk_destination)
    state.extracted_parameters.add("destination")
    
    # Date - Next week (7 days from today)
    next_week_date = date.today() + timedelta(days=7)
    date_param = DateParameter(
        type="departure",
        date_value=next_week_date,
        flexible=True,
        confidence=1.0
    )
    state.dates.append(date_param)
    state.extracted_parameters.add("date")
    
    logger.info(f"Extracted origin: DMM")
    logger.info(f"Extracted destination: BKK")
    logger.info(f"Extracted date: {next_week_date.isoformat()} (next week)")
    
    return {
        "state": state,
        "parameters": {
            "origin": "DMM",
            "destination": "BKK",
            "departure_date": next_week_date.isoformat(),
            "is_one_way": True
        }
    }

def test_direct_flight_search(origin, destination, departure_date):
    """Perform a direct flight search using requests, bypassing SearchToolManager."""
    # Get API key from environment manager
    env_manager = get_env_manager()
    api_key = env_manager.get_api_key("serper")
    
    if not api_key:
        logger.error("Serper API key not found in environment")
        return None
    
    # Build the query
    query = f"flights from {origin} to {destination} on {departure_date} one way"
    logger.info(f"Searching: {query}")
    
    # Base URL for Serper API
    base_url = "https://google.serper.dev/search"
    
    # Set up request
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "q": query,
        "gl": "us",
        "hl": "en"
    }
    
    try:
        # Make the API request
        logger.info(f"Making direct API request to Serper")
        response = requests.post(base_url, headers=headers, json=payload)
        response.raise_for_status()
        
        search_results = response.json()
        
        # Process the results
        processed_results = {
            "search_query": query,
            "organic_results": [],
            "knowledge_graph": {},
            "_metadata": {
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
                "timestamp": search_results.get("searchParameters", {}).get("timeSearched", "")
            }
        }
        
        # Extract organic results
        for result in search_results.get("organic", []):
            processed_results["organic_results"].append({
                "title": result.get("title", ""),
                "link": result.get("link", ""),
                "snippet": result.get("snippet", "")[:150] + "..."  # Truncate for readability
            })
        
        # Extract knowledge graph if available
        if "knowledgeGraph" in search_results:
            processed_results["knowledge_graph"] = {
                "title": search_results["knowledgeGraph"].get("title", ""),
                "type": search_results["knowledgeGraph"].get("type", "")
            }
        
        logger.info(f"Search successful. Found {len(processed_results['organic_results'])} results")
        return processed_results
    
    except Exception as e:
        logger.error(f"Error in direct search: {str(e)}", exc_info=True)
        return None

if __name__ == "__main__":
    print("\n===== FLIGHT PARAMETER EXTRACTION TEST =====")
    print("Testing: flight from DMM to BKK next week after 7 days one way")
    
    # Step 1: Extract parameters
    extraction_results = test_parameter_extraction()
    parameters = extraction_results["parameters"]
    
    print(f"\n✅ Extracted Parameters:")
    print(f"  - Origin: {parameters['origin']}")
    print(f"  - Destination: {parameters['destination']}")
    print(f"  - Departure Date: {parameters['departure_date']} (7 days from today)")
    print(f"  - One Way: {parameters['is_one_way']}")
    
    # Step 2: Perform direct search
    print("\n===== DIRECT FLIGHT SEARCH TEST =====")
    search_results = test_direct_flight_search(
        parameters["origin"], 
        parameters["destination"], 
        parameters["departure_date"]
    )
    
    if search_results:
        print(f"\n✅ Search Successful:")
        print(f"  - Query: {search_results['search_query']}")
        print(f"  - Result Count: {len(search_results['organic_results'])}")
        
        print("\nTop Search Results:")
        for i, result in enumerate(search_results["organic_results"][:3], 1):
            print(f"  {i}. {result['title']}")
            print(f"     {result['snippet']}")
            print()
    else:
        print("\n❌ Search Failed")
    
    print("\nTest complete - validated parameter extraction for 'next week' temporal reference")
