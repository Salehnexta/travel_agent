#!/usr/bin/env python3
"""
Script to demonstrate enhanced flight results display for Travel Agent.
This provides all flight results with better formatting and more details.
"""
import logging
import os
import re
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import travel agent components
from travel_agent.search_tools import SearchToolManager
from travel_agent.state_definitions import TravelState
from travel_agent.agents.parameter_extraction import ParameterExtractionAgent

def format_flight_detail(title, value):
    """Format a flight detail with consistent spacing"""
    return f"{title:<15}: {value}"

def show_enhanced_flights(query_text=None):
    """
    Show all flight search results with enhanced formatting.
    
    Args:
        query_text: Natural language query (e.g., "Flight from RUH to DMM next week")
    """
    if not query_text:
        # Get query from command line if not provided
        if len(sys.argv) > 1:
            query_text = " ".join(sys.argv[1:])
        else:
            print("\nUsage: python enhance_flight_results.py 'flight from RUH to DMM next week'")
            query_text = input("\nEnter flight search query: ")
    
    print(f"\n🔍 PROCESSING QUERY: {query_text}")
    
    # Extract parameters using the parameter extraction agent
    parameter_agent = ParameterExtractionAgent()
    
    # Create a mock state for processing
    state = TravelState(session_id="test-session")
    state.add_message(role="user", content=query_text)
    
    # Process the query to extract parameters
    print("\nExtracting parameters...")
    state = parameter_agent.process(state)
    
    # Get extracted parameters
    origin = state.origins[0] if state.origins else None
    destination = state.get_primary_destination()
    
    if not origin or not destination:
        print("\n❌ Error: Could not extract origin or destination from query")
        return
    
    origin_name = origin.name
    destination_name = destination.name
    
    # Get date information - look for departure and return dates
    departure_date = None
    return_date = None
    
    # Process dates from the state
    for date_param in state.dates:
        if hasattr(date_param, 'type') and date_param.type == 'departure' and hasattr(date_param, 'start_date') and date_param.start_date:
            departure_date = date_param.start_date.strftime("%Y-%m-%d")
            print(f"\nDeparture date: {departure_date}")
        elif hasattr(date_param, 'type') and date_param.type == 'return' and hasattr(date_param, 'start_date') and date_param.start_date:
            return_date = date_param.start_date.strftime("%Y-%m-%d")
            print(f"Return date: {return_date}")
    
    print(f"\n✈️ FLIGHT SEARCH: {origin_name} → {destination_name}")
    
    # Initialize search tool
    search_tool = SearchToolManager()
    
    # Construct query for outbound flight
    query = f"flights from {origin_name} to {destination_name}"
    if departure_date:
        query += f" on {departure_date}"
    
    # Get raw search results
    print("\nFetching flight results...")
    raw_results = search_tool.search(query=query, search_type="organic", num_results=10)
    
    if not raw_results or "organic" not in raw_results:
        print("\n❌ No flight results found")
        return
    
    # Display all flight results with enhanced formatting
    print(f"\n🎯 FOUND {len(raw_results.get('organic', []))} OUTBOUND FLIGHT OPTIONS:")
    
    # Extract prices for comparison
    all_prices = []
    for result in raw_results.get("organic", []):
        combined_text = f"{result.get('title', '')} {result.get('snippet', '')}"
        price_match = re.search(r'\$(\d+)', combined_text)
        if price_match:
            try:
                all_prices.append(int(price_match.group(1)))
            except ValueError:
                pass
    
    # Get min/max prices if available
    min_price = min(all_prices) if all_prices else None
    max_price = max(all_prices) if all_prices else None
    
    if min_price and max_price:
        print(f"\n💰 Price range: ${min_price} - ${max_price}")
    
    for i, result in enumerate(raw_results.get("organic", [])):
        print(f"\n{'=' * 60}")
        print(f"✈️ FLIGHT OPTION #{i+1}")
        print(f"{'=' * 60}")
        
        # Extract title, link, and description
        title = result.get('title', 'N/A')
        link = result.get('link', 'N/A')
        snippet = result.get('snippet', 'N/A')
        
        # Extract website source
        source = "Unknown"
        if "expedia" in link.lower():
            source = "Expedia"
        elif "skyscanner" in link.lower():
            source = "Skyscanner"
        elif "kayak" in link.lower():
            source = "Kayak"
        elif "flyadeal" in link.lower():
            source = "Flyadeal"
        elif "flynas" in link.lower():
            source = "Flynas"
        elif "saudia" in link.lower():
            source = "Saudia Airlines"
        elif "google" in link.lower():
            source = "Google Flights"
        
        # Extract price
        combined_text = f"{title} {snippet}"
        price = "Not specified"
        price_match = re.search(r'\$(\d+)', combined_text)
        if price_match:
            price = price_match.group(0)
            
        # Format output with consistent spacing
        print(format_flight_detail("Title", title))
        print(format_flight_detail("Source", source))
        print(format_flight_detail("Price", price))
        print(format_flight_detail("Details", snippet))
        print(format_flight_detail("Link", link))
    
    # Show related searches if available
    if "relatedSearches" in raw_results and raw_results["relatedSearches"]:
        print("\n🔍 RELATED SEARCHES:")
        for i, related in enumerate(raw_results["relatedSearches"]):
            print(f"  {i+1}. {related.get('query', '')}")
    
    # If we have a return date, also search for return flights
    if return_date:
        print(f"\n\n🔄 SEARCHING RETURN FLIGHTS: {destination_name} → {origin_name} on {return_date}")
        
        # Construct query for return flight
        return_query = f"flights from {destination_name} to {origin_name} on {return_date}"
        
        # Get raw search results for return flight
        return_results = search_tool.search(query=return_query, search_type="organic", num_results=10)
        
        if not return_results or "organic" not in return_results:
            print("\n❌ No return flight results found")
            return
        
        # Display all return flight results
        print(f"\n🎯 FOUND {len(return_results.get('organic', []))} RETURN FLIGHT OPTIONS:")
        
        # Extract prices for comparison
        all_return_prices = []
        for result in return_results.get("organic", []):
            combined_text = f"{result.get('title', '')} {result.get('snippet', '')}"
            price_match = re.search(r'\$(\d+)', combined_text)
            if price_match:
                try:
                    all_return_prices.append(int(price_match.group(1)))
                except ValueError:
                    pass
        
        # Get min/max prices if available
        min_return_price = min(all_return_prices) if all_return_prices else None
        max_return_price = max(all_return_prices) if all_return_prices else None
        
        if min_return_price and max_return_price:
            print(f"\n💰 Return price range: ${min_return_price} - ${max_return_price}")
        
        for i, result in enumerate(return_results.get("organic", [])):
            print(f"\n{'=' * 60}")
            print(f"✈️ RETURN FLIGHT #{i+1}")
            print(f"{'=' * 60}")
            
            # Extract title, link, and description
            title = result.get('title', 'N/A')
            link = result.get('link', 'N/A')
            snippet = result.get('snippet', 'N/A')
            
            # Extract website source
            source = "Unknown"
            if "expedia" in link.lower():
                source = "Expedia"
            elif "skyscanner" in link.lower():
                source = "Skyscanner"
            elif "kayak" in link.lower():
                source = "Kayak"
            elif "flyadeal" in link.lower():
                source = "Flyadeal"
            elif "flynas" in link.lower():
                source = "Flynas"
            elif "saudia" in link.lower():
                source = "Saudia Airlines"
            elif "google" in link.lower():
                source = "Google Flights"
            
            # Extract price
            combined_text = f"{title} {snippet}"
            price = "Not specified"
            price_match = re.search(r'\$(\d+)', combined_text)
            if price_match:
                price = price_match.group(0)
                
            # Format output with consistent spacing
            print(format_flight_detail("Title", title))
            print(format_flight_detail("Source", source))
            print(format_flight_detail("Price", price))
            print(format_flight_detail("Details", snippet))
            print(format_flight_detail("Link", link))

if __name__ == "__main__":
    show_enhanced_flights()
