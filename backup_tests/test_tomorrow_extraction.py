#!/usr/bin/env python3
"""
Test script for validating temporal reference extraction for 'tomorrow'
"""

import os
import sys
import logging
from datetime import date, datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("tomorrow_test")

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import travel agent components
from travel_agent.state_definitions import (
    TravelState, 
    ConversationStage,
    LocationParameter,
    DateParameter
)
from travel_agent.agents.parameter_extraction import ParameterExtractionAgent


def test_tomorrow_extraction():
    """Test extraction of 'tomorrow' temporal reference in flight search"""
    
    # Set up test queries with variations of tomorrow
    test_queries = [
        "find me flight from DMM to Cairo tomorrow one day",
        "I need a flight from DMM to Cairo tomorrow",
        "book a flight DMM to CAI for tomorrow",
        "flight from DMM to Cairo tmrw"
    ]
    
    results = []
    
    for query in test_queries:
        logger.info(f"Testing query: '{query}'")
        
        # Create fresh travel state
        state = TravelState(
            session_id=f"test_tomorrow_{len(results)}",
            conversation_stage=ConversationStage.PARAMETER_EXTRACTION
        )
        
        # Add the user message
        state.add_message("user", query)
        
        # Create parameter extraction agent
        agent = ParameterExtractionAgent()
        
        # Process the message
        try:
            result_state = agent.process(state)
            
            # Calculate expected date (tomorrow)
            tomorrow = date.today() + timedelta(days=1)
            
            # Check if origin was extracted
            has_dmm_origin = any(o.name == "DMM" for o in result_state.origins)
            
            # Check if destination was extracted
            has_cairo_destination = any(
                d.name in ["CAI", "Cairo"] for d in result_state.destinations
            )
            
            # Check if tomorrow's date was extracted
            # Compare directly with the date object or the date component of a datetime
            has_tomorrow = False
            if result_state.dates:
                for d in result_state.dates:
                    if d.date_value:
                        # Handle both datetime and date objects
                        date_to_compare = d.date_value
                        if hasattr(date_to_compare, 'date'):
                            # It's a datetime object
                            date_to_compare = date_to_compare.date()
                        if date_to_compare == tomorrow:
                            has_tomorrow = True
                            break
            
            # Log the extraction results
            logger.info(f"Origin DMM extracted: {has_dmm_origin}")
            logger.info(f"Destination Cairo/CAI extracted: {has_cairo_destination}")
            logger.info(f"Tomorrow extracted: {has_tomorrow}")
            
            if result_state.dates:
                for date_param in result_state.dates:
                    logger.info(f"Date extracted: {date_param.date_value}")
            else:
                logger.info("No dates extracted")
            
            # Add result to results list
            results.append({
                "query": query,
                "has_dmm_origin": has_dmm_origin,
                "has_cairo_destination": has_cairo_destination,
                "has_tomorrow": has_tomorrow,
                "extracted_dates": [
                    str(d.date_value) for d in result_state.dates
                ] if result_state.dates else []
            })
            
        except Exception as e:
            logger.error(f"Error processing query '{query}': {str(e)}", exc_info=True)
            results.append({
                "query": query,
                "error": str(e)
            })
    
    return results


if __name__ == "__main__":
    print("\n===== TESTING TOMORROW EXTRACTION =====")
    
    try:
        results = test_tomorrow_extraction()
        
        print("\n===== RESULTS SUMMARY =====")
        
        all_passed = True
        
        for i, result in enumerate(results, 1):
            print(f"\nQuery {i}: {result['query']}")
            
            if "error" in result:
                print(f"  ❌ Error: {result['error']}")
                all_passed = False
            else:
                origin_status = "✅" if result["has_dmm_origin"] else "❌"
                dest_status = "✅" if result["has_cairo_destination"] else "❌"
                tomorrow_status = "✅" if result["has_tomorrow"] else "❌"
                
                print(f"  Origin DMM: {origin_status}")
                print(f"  Destination Cairo/CAI: {dest_status}")
                print(f"  Tomorrow extracted: {tomorrow_status}")
                
                if result["extracted_dates"]:
                    print(f"  Extracted dates: {', '.join(result['extracted_dates'])}")
                else:
                    print("  No dates extracted ❌")
                
                if not (result["has_dmm_origin"] and 
                        result["has_cairo_destination"] and 
                        result["has_tomorrow"]):
                    all_passed = False
        
        print("\n===== OVERALL RESULT =====")
        if all_passed:
            print("✅ All 'tomorrow' extraction tests PASSED")
        else:
            print("❌ Some 'tomorrow' extraction tests FAILED")
        
    except Exception as e:
        print(f"\n❌ Test execution failed: {str(e)}")
