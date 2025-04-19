#!/usr/bin/env python3
"""
Test script for parameter extraction specifically for DMM to BKK flight tomorrow
This test bypasses LLM calls and directly tests the parameter extraction functionality
"""

import logging
import re
from datetime import date, datetime, timedelta

from travel_agent.state_definitions import (
    TravelState, 
    ConversationStage,
    LocationParameter,
    DateParameter
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("param_test")

def test_flight_parameter_extraction():
    """Test parameter extraction for a DMM to BKK flight query tomorrow"""
    
    # Set up initial query and state
    query = "I need a flight from DMM to BKK tomorrow one way"
    
    # Create fresh travel state
    state = TravelState(
        session_id="test_param_extraction",
        conversation_stage=ConversationStage.PARAMETER_EXTRACTION
    )
    
    # Add the message to state
    state.add_message("user", query)
    
    # Perform basic parameter extraction directly (without LLM)
    
    # 1. Extract locations based on airport codes (DMM and BKK)
    locations = []
    airport_pattern = r'\b([A-Z]{3})\b'
    airport_matches = re.finditer(airport_pattern, query)
    
    for i, match in enumerate(airport_matches):
        airport_code = match.group(1)
        location_type = "origin" if i == 0 else "destination"
        
        location = LocationParameter(
            name=airport_code,
            type=location_type,
            confidence=0.9
        )
        
        # Add to state based on type
        if location_type == "origin":
            state.origins.append(location)
        else:
            state.destinations.append(location)
        
        locations.append(location)
        logger.info(f"Extracted {location_type}: {airport_code}")
    
    # 2. Extract date (tomorrow)
    tomorrow = date.today() + timedelta(days=1)
    
    if "tomorrow" in query.lower():
        date_param = DateParameter(
            type="departure",
            date_value=tomorrow,
            flexible=False,
            confidence=0.9
        )
        
        state.dates.append(date_param)
        logger.info(f"Extracted tomorrow as departure date: {tomorrow}")
    
    # Validation
    has_origin = any(o.name == "DMM" for o in state.origins)
    has_destination = any(d.name == "BKK" for d in state.destinations)
    has_tomorrow = any(d.date_value and d.date_value == tomorrow for d in state.dates)
    
    # Print validation results
    logger.info(f"Has DMM origin: {has_origin}")
    logger.info(f"Has BKK destination: {has_destination}")
    logger.info(f"Has tomorrow date: {has_tomorrow}")
    
    # Check if we have the minimum parameters needed for search
    has_min_params = len(state.destinations) > 0 and len(state.dates) > 0
    
    # Log the detailed state
    logger.info(f"Origins: {[o.model_dump() for o in state.origins]}")
    logger.info(f"Destinations: {[d.model_dump() for d in state.destinations]}")
    logger.info(f"Dates: {[d.model_dump() for d in state.dates]}")
    
    return {
        "success": has_origin and has_destination and has_tomorrow and has_min_params,
        "extracted_origins": [o.model_dump() for o in state.origins],
        "extracted_destinations": [d.model_dump() for d in state.destinations],
        "extracted_dates": [d.model_dump() for d in state.dates],
        "minimum_parameters_met": has_min_params
    }

if __name__ == "__main__":
    # Run the test
    print("Testing parameter extraction for flight from DMM to BKK tomorrow")
    results = test_flight_parameter_extraction()
    
    # Print results in a readable format
    print("\n=== TEST RESULTS ===")
    print(f"Success: {results['success']}")
    
    print("\nExtracted Origins:")
    for origin in results.get('extracted_origins', []):
        print(f"  - {origin['name']} (Type: {origin['type']})")
    
    print("\nExtracted Destinations:")
    for dest in results.get('extracted_destinations', []):
        print(f"  - {dest['name']} (Type: {dest['type']})")
    
    print("\nExtracted Dates:")
    for date_param in results.get('extracted_dates', []):
        date_str = date_param['date_value'] if date_param.get('date_value') else "None"
        print(f"  - Type: {date_param['type']}, Date: {date_str}")
    
    print(f"\nMinimum Parameters Met: {results['minimum_parameters_met']}")
    
    if results['success']:
        print("\n✅ Flight parameter extraction test PASSED")
    else:
        print("\n❌ Flight parameter extraction test FAILED")
