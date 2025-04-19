#!/usr/bin/env python3
"""
Diagnostic script to test the Google Serper API connection directly.
"""

import os
import json
import logging
import requests
import sys
from datetime import date

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("serper_test")

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import environment manager from travel_agent
from travel_agent.config.env_manager import get_env_manager


def test_serper_api_connection():
    """Test direct connection to Serper API."""
    # Get API key from environment manager
    env_manager = get_env_manager()
    api_key = env_manager.get_api_key("serper")
    
    if not api_key:
        logger.error("Serper API key not found in environment variables")
        return {
            "success": False,
            "message": "API key not found"
        }
    
    # Print partial API key for debugging (hiding most characters)
    masked_key = api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:] if len(api_key) > 8 else "****"
    logger.info(f"Using Serper API key: {masked_key}")
    
    # Base URL for Serper API
    base_url = "https://google.serper.dev/search"
    
    # Test with a simple search query
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "q": "test search query",
        "gl": "us",
        "hl": "en"
    }
    
    try:
        logger.info(f"Making test request to {base_url}")
        response = requests.post(base_url, headers=headers, json=payload)
        
        # Check response status
        logger.info(f"Serper API response status: {response.status_code}")
        
        if response.status_code == 200:
            # Successfully connected to the API
            logger.info("Successfully connected to Serper API")
            
            # Get a sample of the response (first few items)
            response_json = response.json()
            response_snippet = {
                "organic": response_json.get("organic", [])[:2],
                "searchParameters": response_json.get("searchParameters", {})
            }
            
            return {
                "success": True,
                "status_code": response.status_code,
                "response_sample": response_snippet
            }
        else:
            # Failed to connect with error
            error_msg = f"Failed to connect to Serper API: HTTP {response.status_code}"
            try:
                error_details = response.json()
                error_msg += f" - {json.dumps(error_details)}"
            except:
                error_msg += f" - {response.text[:200]}"
                
            logger.error(error_msg)
            return {
                "success": False,
                "status_code": response.status_code,
                "message": error_msg
            }
            
    except Exception as e:
        logger.error(f"Exception during Serper API test: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": str(e)
        }


def test_flight_search_query():
    """Test building a flight search query and making a direct API call."""
    # Get API key from environment manager
    env_manager = get_env_manager()
    api_key = env_manager.get_api_key("serper")
    
    if not api_key:
        logger.error("Serper API key not found in environment variables")
        return {
            "success": False,
            "message": "API key not found"
        }
    
    # Base URL for Serper API
    base_url = "https://google.serper.dev/search"
    
    # Test parameters
    origin = "DMM"
    destination = "BKK"
    departure_date = (date.today().isoformat())
    
    # Build the flight search query
    query = f"flights from {origin} to {destination} on {departure_date}"
    logger.info(f"Testing flight search query: '{query}'")
    
    # Set up request headers and payload
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
        logger.info(f"Making flight search request to {base_url}")
        response = requests.post(base_url, headers=headers, json=payload)
        
        # Check response status
        logger.info(f"Serper API response status: {response.status_code}")
        
        if response.status_code == 200:
            # Successfully connected to the API
            logger.info("Successfully executed flight search query")
            
            # Get a sample of the response (first few items)
            response_json = response.json()
            
            # Extract key information
            organic_results = response_json.get("organic", [])
            knowledge_graph = response_json.get("knowledgeGraph", {})
            
            # Return summary information
            return {
                "success": True,
                "status_code": response.status_code,
                "query": query,
                "result_count": len(organic_results),
                "has_knowledge_graph": bool(knowledge_graph),
                "top_result_title": organic_results[0].get("title") if organic_results else None
            }
        else:
            # Failed to connect with error
            error_msg = f"Failed flight search query: HTTP {response.status_code}"
            try:
                error_details = response.json()
                error_msg += f" - {json.dumps(error_details)}"
            except:
                error_msg += f" - {response.text[:200]}"
                
            logger.error(error_msg)
            return {
                "success": False,
                "status_code": response.status_code,
                "message": error_msg
            }
            
    except Exception as e:
        logger.error(f"Exception during flight search test: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": str(e)
        }


if __name__ == "__main__":
    logger.info("Starting Serper API diagnostic tests")
    
    print("\n===== SERPER API CONNECTION TEST =====")
    connection_results = test_serper_api_connection()
    
    if connection_results.get("success", False):
        print("✅ Successfully connected to Serper API")
        
        # If connection test passes, also test flight search
        print("\n===== FLIGHT SEARCH QUERY TEST =====")
        flight_results = test_flight_search_query()
        
        if flight_results.get("success", False):
            print(f"✅ Successfully executed flight search query: {flight_results.get('query')}")
            print(f"  - Found {flight_results.get('result_count')} organic results")
            print(f"  - Has knowledge graph: {flight_results.get('has_knowledge_graph')}")
            print(f"  - Top result: {flight_results.get('top_result_title')}")
        else:
            print(f"❌ Flight search query failed: {flight_results.get('message')}")
    else:
        print(f"❌ Failed to connect to Serper API: {connection_results.get('message')}")
        
    print("\nCheck the logs above for more detailed diagnostic information.")
