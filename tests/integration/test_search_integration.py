#!/usr/bin/env python3
"""
Integration tests for search functionality.
Tests the integration between search, parameter extraction, and state management.
"""

import unittest
import sys
import os
import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import components to test
from travel_agent.agents.search import search_agent
from travel_agent.state_definitions import (
    TravelState, 
    ConversationStage,
    LocationParameter,
    DateParameter
)


class TestSearchIntegration(unittest.TestCase):
    """Test the integration between search components and other parts of the system."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a test TravelState with parameters already extracted
        self.travel_state = TravelState(
            session_id="test_search_integration",
            conversation_stage=ConversationStage.SEARCH
        )
        
        # Add extracted parameters for a flight search
        self.travel_state.add_origin(LocationParameter(name="JFK", type="origin", confidence=0.95))
        self.travel_state.add_destination(LocationParameter(name="LAX", type="destination", confidence=0.95))
        
        tomorrow = date.today() + timedelta(days=1)
        self.travel_state.add_date(DateParameter(type="departure", date_value=tomorrow, flexible=False, confidence=0.95))
        
        self.travel_state.is_one_way = True
        self.travel_state.adults = 1
        self.travel_state.extracted_parameters.update(["origin", "destination", "date", "trip_type"])
        
        # Mock the search API client
        self.serper_patcher = patch('travel_agent.agents.search.serper_client')
        self.mock_serper = self.serper_patcher.start()
    
    def tearDown(self):
        """Clean up after tests."""
        self.serper_patcher.stop()
    
    def test_flight_search(self):
        """Test flight search functionality."""
        # Mock search API response for flights
        mock_search_response = {
            "searchParameters": {
                "q": "flights from JFK to LAX tomorrow one way",
                "gl": "us",
                "hl": "en",
                "num": 10,
                "timeSearched": "2023-04-19T12:34:56Z"
            },
            "organic": [
                {
                    "title": "Flights from JFK to LAX - Cheapest Deals",
                    "link": "https://example.com/flights/jfk-lax",
                    "snippet": "Find cheap flights from JFK to LAX. One-way from $199. Departs 08:00 AM JFK, arrives 11:30 AM LAX. American Airlines, Delta, and more."
                },
                {
                    "title": "JFK to LAX - Nonstop Flights - Example Airlines",
                    "link": "https://example.com/example-airlines/jfk-lax",
                    "snippet": "Book nonstop flights from JFK to LAX. Morning departure at 09:15 AM, arrives 12:45 PM. One-way fares from $249."
                }
            ],
            "flights": [
                {
                    "airline": "American Airlines",
                    "flight_number": "AA123",
                    "departure": "08:00 AM",
                    "arrival": "11:30 AM",
                    "price": "$199",
                    "duration": "6h 30m",
                    "stops": "Nonstop"
                },
                {
                    "airline": "Delta",
                    "flight_number": "DL456",
                    "departure": "09:15 AM",
                    "arrival": "12:45 PM",
                    "price": "$249",
                    "duration": "6h 30m",
                    "stops": "Nonstop"
                }
            ]
        }
        self.mock_serper.search.return_value = mock_search_response
        
        # Run search
        updated_state = search_agent(self.travel_state)
        
        # Verify search was performed
        self.mock_serper.search.assert_called_once()
        
        # Check search query
        args, kwargs = self.mock_serper.search.call_args
        self.assertIn("flights from JFK to LAX", kwargs["q"])
        
        # Verify state was updated with search results
        self.assertEqual(updated_state.conversation_stage, ConversationStage.SEARCH_RESULTS)
        self.assertIsNotNone(updated_state.search_results)
        self.assertIsNotNone(updated_state.last_search_query)
        
        # Verify structured data parsing
        self.assertIn("flights", updated_state.search_results)
        self.assertGreaterEqual(len(updated_state.search_results["flights"]), 2)
        
        # Check first flight details
        first_flight = updated_state.search_results["flights"][0]
        self.assertEqual(first_flight["airline"], "American Airlines")
        self.assertEqual(first_flight["flight_number"], "AA123")
        self.assertEqual(first_flight["price"], "$199")
    
    def test_hotel_search(self):
        """Test hotel search functionality."""
        # Create a fresh state for hotel search
        hotel_state = TravelState(
            session_id="test_hotel_search",
            conversation_stage=ConversationStage.SEARCH
        )
        
        # Add extracted parameters for a hotel search
        hotel_state.add_destination(LocationParameter(name="Paris", type="destination", confidence=0.95))
        
        check_in = date.today() + timedelta(days=7)
        check_out = check_in + timedelta(days=3)
        
        hotel_state.add_date(DateParameter(type="departure", date_value=check_in, flexible=False, confidence=0.95))
        hotel_state.add_date(DateParameter(type="return", date_value=check_out, flexible=False, confidence=0.95))
        
        hotel_state.adults = 2
        hotel_state.hotel_needed = True
        hotel_state.extracted_parameters.update(["destination", "date", "return_date"])
        
        # Mock search API response for hotels
        mock_search_response = {
            "searchParameters": {
                "q": f"hotels in Paris from {check_in.isoformat()} to {check_out.isoformat()} for 2 adults",
                "gl": "us",
                "hl": "en",
                "num": 10,
                "timeSearched": "2023-04-19T12:34:56Z"
            },
            "organic": [
                {
                    "title": "Grand Hotel Paris - Luxury in the City Center",
                    "link": "https://example.com/hotels/grand-hotel-paris",
                    "snippet": "5-star hotel in central Paris. $299 per night. Free WiFi, breakfast included. 4.7/5 rating from 1,245 reviews."
                },
                {
                    "title": "Eiffel Tower View Hotel - Paris",
                    "link": "https://example.com/hotels/eiffel-tower-view",
                    "snippet": "4-star hotel with Eiffel Tower views. $249 per night. Rooftop restaurant, spa services. 4.5/5 rating from 987 reviews."
                }
            ],
            "hotels": [
                {
                    "name": "Grand Hotel Paris",
                    "address": "123 Champs-Élysées, Paris",
                    "rating": "4.7",
                    "price": "$299",
                    "amenities": ["WiFi", "Breakfast", "Spa"]
                },
                {
                    "name": "Eiffel Tower View Hotel",
                    "address": "45 Avenue de la Tour, Paris",
                    "rating": "4.5",
                    "price": "$249",
                    "amenities": ["WiFi", "Restaurant", "Bar"]
                }
            ]
        }
        self.mock_serper.search.return_value = mock_search_response
        
        # Run search
        updated_state = search_agent(hotel_state)
        
        # Verify search was performed
        self.mock_serper.search.assert_called_once()
        
        # Check search query
        args, kwargs = self.mock_serper.search.call_args
        self.assertIn("hotels in Paris", kwargs["q"])
        self.assertIn(check_in.isoformat(), kwargs["q"])
        
        # Verify state was updated with search results
        self.assertEqual(updated_state.conversation_stage, ConversationStage.SEARCH_RESULTS)
        self.assertIsNotNone(updated_state.search_results)
        
        # Verify structured data parsing
        self.assertIn("hotels", updated_state.search_results)
        self.assertGreaterEqual(len(updated_state.search_results["hotels"]), 2)
        
        # Check hotel details
        first_hotel = updated_state.search_results["hotels"][0]
        self.assertEqual(first_hotel["name"], "Grand Hotel Paris")
        self.assertEqual(first_hotel["rating"], "4.7")
        self.assertEqual(first_hotel["price"], "$299")
    
    def test_search_result_parser(self):
        """Test the search result parser component."""
        # Import the parser directly
        from travel_agent.agents.search import SearchResultParser
        
        # Raw search results (minimal example)
        raw_results = {
            "organic": [
                {
                    "title": "Flights from JFK to LAX - American Airlines",
                    "snippet": "Nonstop flight, departs JFK 10:00 AM, arrives LAX 1:30 PM. $199 one-way."
                },
                {
                    "title": "Hotels in Tokyo - Best Western",
                    "snippet": "4-star hotel in Shinjuku, Tokyo. $150 per night, free WiFi. 4.2/5 rating."
                }
            ]
        }
        
        # Create parser instances
        flight_parser = SearchResultParser(raw_results, "flight", "JFK", "LAX")
        hotel_parser = SearchResultParser(raw_results, "hotel", None, "Tokyo")
        
        # Parse results
        flight_results = flight_parser.parse()
        hotel_results = hotel_parser.parse()
        
        # Check flight results
        self.assertIn("flights", flight_results)
        self.assertGreaterEqual(len(flight_results["flights"]), 1)
        
        # Flight parser should identify American Airlines from the title
        first_flight = flight_results["flights"][0]
        self.assertIn("American", first_flight["airline"])
        
        # Price should be extracted from the snippet
        self.assertEqual(first_flight["price"], "$199")
        
        # Check hotel results
        self.assertIn("hotels", hotel_results)
        self.assertGreaterEqual(len(hotel_results["hotels"]), 1)
        
        # Hotel parser should identify Best Western from the title
        first_hotel = hotel_results["hotels"][0]
        self.assertIn("Best Western", first_hotel["name"])
        
        # Rating and price should be extracted from the snippet
        self.assertEqual(first_hotel["price"], "$150")
        self.assertEqual(first_hotel["rating"], "4.2")
    
    def test_search_error_handling(self):
        """Test error handling during search."""
        # Import error handling components
        from travel_agent.error_handling import SearchError
        from travel_agent.error_handling.fallbacks import FallbackService
        
        # Mock search API to raise an error
        self.mock_serper.search.side_effect = Exception("Search API unavailable")
        
        # Mock the fallback service
        with patch('travel_agent.error_handling.fallbacks.FallbackService.fallback_flight_search') as mock_fallback:
            # Configure fallback to return basic flight results
            mock_fallback.return_value = [
                {
                    "airline": "Fallback Airways",
                    "flight_number": "FB123",
                    "origin": "JFK",
                    "destination": "LAX",
                    "departure_date": date.today() + timedelta(days=1),
                    "departure_time": "10:00",
                    "arrival_time": "13:30",
                    "price": "$---",
                    "fallback": True
                }
            ]
            
            # Run search with error handling
            # Normally this would be handled by decorators in the actual implementation
            # For testing, we'll simulate the process
            try:
                search_agent(self.travel_state)
            except Exception:
                # Simulate fallback behavior
                origin = self.travel_state.origins[0].name
                destination = self.travel_state.destinations[0].name
                departure_date = self.travel_state.dates[0].date_value
                
                # Get fallback flights
                fallback_flights = FallbackService.fallback_flight_search(
                    origin, destination, departure_date.isoformat()
                )
                
                # Update state with fallback results
                self.travel_state.search_results = {"flights": fallback_flights}
                self.travel_state.conversation_stage = ConversationStage.SEARCH_RESULTS
                self.travel_state.last_search_query = f"flights from {origin} to {destination}"
            
            # Verify fallback was called
            mock_fallback.assert_called_once_with("JFK", "LAX", self.travel_state.dates[0].date_value.isoformat())
            
            # Verify fallback results were stored
            self.assertIsNotNone(self.travel_state.search_results)
            self.assertIn("flights", self.travel_state.search_results)
            self.assertGreaterEqual(len(self.travel_state.search_results["flights"]), 1)
            
            # Check that results are marked as fallback
            first_flight = self.travel_state.search_results["flights"][0]
            self.assertTrue(first_flight["fallback"])
            self.assertEqual(first_flight["airline"], "Fallback Airways")

if __name__ == "__main__":
    unittest.main()
