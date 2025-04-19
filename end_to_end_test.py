"""
End-to-End Test for Travel Agent System

This script tests the complete workflow:
1. Parameter extraction from user messages (including temporal references)
2. Search using the extracted parameters
3. Result parsing and enhancement
4. Response generation

Example queries test various scenarios including flight searches, 
hotel searches, and different temporal references.
"""

import os
import uuid
import json
import logging
from datetime import datetime, timedelta

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import travel agent components
from travel_agent.agents.parameter_extraction import ParameterExtractionAgent
from travel_agent.agents.search_manager import SearchManager
from travel_agent.agents.response_generator import ResponseGenerator
from travel_agent.state_definitions import TravelState, ConversationStage

# Test scenarios
TEST_SCENARIOS = [
    {
        "name": "Flight DMM to RUH Tomorrow",
        "query": "Find me a flight from DMM to RUH tomorrow one way",
        "expected_parameters": ["origin", "destination", "date", "trip_type"]
    },
    {
        "name": "Hotel in Riyadh Next Week",
        "query": "I need a hotel in Riyadh for next week",
        "expected_parameters": ["destination", "date"]
    },
    {
        "name": "Flight with Abbreviated Cities",
        "query": "Find flight jed to cai on Friday",
        "expected_parameters": ["origin", "destination", "date"]
    },
    {
        "name": "Flight with Multiple Temporal References",
        "query": "I want to fly from DMM to DXB next weekend and return next Monday",
        "expected_parameters": ["origin", "destination", "date", "return_date"]
    },
    {
        "name": "Hotel with Short Date Format",
        "query": "Book me hotel in Riyadh tmrw for 3 nights",
        "expected_parameters": ["destination", "date", "duration"]
    }
]

def run_end_to_end_test(scenario):
    """
    Run end-to-end test for a single scenario
    
    Args:
        scenario: Test scenario dictionary with name, query, and expected_parameters
    
    Returns:
        Dictionary with test results
    """
    print(f"\n{'='*20} TESTING SCENARIO: {scenario['name']} {'='*20}")
    print(f"Query: '{scenario['query']}'")
    
    # Initialize state
    session_id = str(uuid.uuid4())
    state = TravelState(session_id=session_id)
    state.add_message("user", scenario["query"])
    
    # Initialize agents
    parameter_agent = ParameterExtractionAgent()
    search_manager = SearchManager()
    response_generator = ResponseGenerator()
    
    # Step 1: Parameter Extraction
    print("\n--- Step 1: Parameter Extraction ---")
    try:
        state = parameter_agent.process(state)
        
        # Log extracted parameters
        print("Origins:", [o.model_dump() for o in state.origins] if state.origins else "None")
        print("Destinations:", [d.model_dump() for d in state.destinations] if state.destinations else "None")
        print("Dates:", [d.model_dump() for d in state.dates] if state.dates else "None")
        print("Preferences:", [p.model_dump() for p in state.preferences] if state.preferences else "None")
        
        # Validate expected parameters
        validation_results = {}
        for param in scenario["expected_parameters"]:
            if param == "origin" and state.origins:
                validation_results[param] = "✓"
            elif param == "destination" and state.destinations:
                validation_results[param] = "✓"
            elif param == "date" and state.dates:
                validation_results[param] = "✓"
            elif param == "trip_type" and any("one_way" in str(p.preferences).lower() or "round_trip" in str(p.preferences).lower() for p in state.preferences):
                validation_results[param] = "✓"
            elif param == "return_date" and any(d.type == "return" for d in state.dates):
                validation_results[param] = "✓"
            elif param == "duration" and state.dates and len(state.dates) >= 2:
                validation_results[param] = "✓"
            else:
                validation_results[param] = "✗"
        
        print("\nParameter Validation:")
        for param, result in validation_results.items():
            print(f"- {param}: {result}")
        
        # Step 2: Search
        print("\n--- Step 2: Search ---")
        if state.has_minimum_parameters():
            state = search_manager.process(state)
            
            # Log search results
            if state.search_results:
                for result_type, results in state.search_results.items():
                    print(f"\nFound {len(results)} {result_type} results")
                    
                    for result in results:
                        # Check if we have structured data
                        if "structured" in result.data:
                            structured_items = result.data.get("structured", [])
                            print(f"- {len(structured_items)} structured items found")
                            
                            # Show sample of structured data
                            if structured_items:
                                sample = structured_items[0]
                                print(f"  Sample: {json.dumps(sample, default=str)[:200]}...")
                        else:
                            print(f"- Raw data only")
            else:
                print("No search results found")
        else:
            print("Skipping search - missing required parameters")
            
        # Step 3: Response generation
        print("\n--- Step 3: Response Generation ---")
        if state.search_results:
            state = response_generator.process(state)
            
            # Get the generated response
            response = state.conversation_history[-1]["content"] if state.conversation_history else "No response generated"
            
            # Show a preview of the response
            preview_length = min(300, len(response))
            print(f"Response preview: {response[:preview_length]}...")
            if len(response) > preview_length:
                print(f"(Response truncated, total length: {len(response)} characters)")
        else:
            print("Skipping response generation - no search results")
        
        # Return test summary
        return {
            "scenario": scenario["name"],
            "query": scenario["query"],
            "parameters_extracted": all(result == "✓" for result in validation_results.values()),
            "search_completed": bool(state.search_results),
            "response_generated": state.conversation_history[-1]["role"] == "assistant" if state.conversation_history else False,
            "validation_results": validation_results
        }
    
    except Exception as e:
        logger.error(f"Error in test execution: {str(e)}", exc_info=True)
        return {
            "scenario": scenario["name"],
            "query": scenario["query"],
            "error": str(e),
            "error_type": type(e).__name__
        }

def run_all_tests():
    """Run all test scenarios and summarize results"""
    print(f"\n{'='*30} TRAVEL AGENT END-TO-END TESTS {'='*30}")
    print(f"Testing {len(TEST_SCENARIOS)} scenarios\n")
    
    # Timestamp for reference
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Tomorrow's date should be: {(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}")
    
    results = []
    
    for scenario in TEST_SCENARIOS:
        result = run_end_to_end_test(scenario)
        results.append(result)
    
    # Print summary
    print(f"\n{'='*30} TEST SUMMARY {'='*30}")
    print(f"Total scenarios: {len(results)}")
    print(f"Successful scenarios: {sum(1 for r in results if 'error' not in r)}")
    print(f"Failed scenarios: {sum(1 for r in results if 'error' in r)}")
    
    # Print detailed results
    print("\nResults by scenario:")
    for i, result in enumerate(results, 1):
        if "error" in result:
            status = f"❌ FAILED: {result['error_type']}: {result['error']}"
        elif result.get("parameters_extracted") and result.get("search_completed") and result.get("response_generated"):
            status = "✅ PASSED"
        else:
            status = "⚠️ PARTIAL"
            
        print(f"{i}. {result['scenario']}: {status}")
    
    return results

if __name__ == "__main__":
    run_all_tests()
