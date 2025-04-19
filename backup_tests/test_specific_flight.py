#!/usr/bin/env python3
"""
Test script for testing a specific flight query: DMM to BKK tomorrow one way
"""

import os
import logging
import json
import datetime
from datetime import date, timedelta

from travel_agent.state_definitions import TravelState, ConversationStage
from travel_agent.graph_builder import TravelAgentGraph

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("flight_test")

def test_flight_dmm_to_bkk():
    """Test flight search from DMM to BKK for tomorrow (one-way)"""
    
    # Set up initial query
    query = "I need a flight from DMM to BKK tomorrow one way"
    
    # Create fresh travel state
    state = TravelState(
        session_id="test_dmm_bkk_flight",
        conversation_stage=ConversationStage.INITIAL_GREETING
    )
    
    # Create the travel agent graph
    graph = TravelAgentGraph()
    
    # Run the graph with our test query
    logger.info(f"Testing flight query: {query}")
    try:
        state = graph.process_message(state, query)
        
        # Use state directly as our result
        final_state = state
        
        # Print extracted destinations
        logger.info(f"Extracted destinations: {[d.model_dump() for d in final_state.destinations]}")
        
        # Print extracted dates
        logger.info(f"Extracted dates: {[d.model_dump() for d in final_state.dates]}")
        
        # Validate specific requirements
        has_origin = any(d.name == "DMM" for d in final_state.destinations)
        has_destination = any(d.name == "BKK" for d in final_state.destinations)
        
        # Check if tomorrow's date was correctly extracted
        tomorrow = date.today() + timedelta(days=1)
        tomorrow_str = tomorrow.strftime("%Y-%m-%d")
        has_tomorrow = any(d.date_value and d.date_value == tomorrow for d in final_state.dates)
        
        # Print validation results
        logger.info(f"Has DMM origin: {has_origin}")
        logger.info(f"Has BKK destination: {has_destination}")
        logger.info(f"Has tomorrow date: {has_tomorrow}")
        
        # Print final results
        return {
            "success": has_origin and has_destination and has_tomorrow,
            "extracted_destinations": [d.model_dump() for d in final_state.destinations],
            "extracted_dates": [d.model_dump() for d in final_state.dates],
            "search_results": final_state.search_results
        }
        
    except Exception as e:
        logger.error(f"Error running test: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    # Run the test
    results = test_flight_dmm_to_bkk()
    
    # Print results in a readable format
    print("\n=== TEST RESULTS ===")
    print(f"Success: {results['success']}")
    print("\nExtracted Destinations:")
    for dest in results.get('extracted_destinations', []):
        print(f"  - {dest}")
    
    print("\nExtracted Dates:")
    for date_param in results.get('extracted_dates', []):
        print(f"  - {date_param}")
    
    print("\nSearch Results:")
    if results.get('search_results'):
        for category, results_list in results.get('search_results', {}).items():
            print(f"\n{category.upper()}:")
            if results_list:
                for i, result in enumerate(results_list[:3], 1):  # Show top 3 results
                    print(f"  Result {i}: {result}")
            else:
                print("  No results found.")
    else:
        print("  No search results available.")
