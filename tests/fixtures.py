#!/usr/bin/env python3
"""
Test fixtures for the travel agent system.
Provides sample data for tests to ensure consistency.
"""

import os
import json
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional, Union

# Import models
from travel_agent.state_definitions import (
    TravelState, 
    ConversationStage,
    LocationParameter,
    DateParameter,
    MessageType
)

class TestFixtures:
    """
    Test fixtures for travel agent tests.
    Contains sample data and factory methods for creating test objects.
    """
    
    @staticmethod
    def today() -> date:
        """Get today's date, consistently across all tests."""
        return date(2025, 4, 18)  # Fixed date for all tests
    
    @staticmethod
    def tomorrow() -> date:
        """Get tomorrow's date, consistently across all tests."""
        return TestFixtures.today() + timedelta(days=1)
    
    @staticmethod
    def next_week() -> date:
        """Get a date one week from today, consistently across all tests."""
        return TestFixtures.today() + timedelta(days=7)
    
    @staticmethod
    def next_weekend() -> date:
        """Get next Saturday's date, consistently across all tests."""
        today = TestFixtures.today()
        days_until_saturday = (5 - today.weekday()) % 7  # 5 = Saturday
        if days_until_saturday == 0:
            days_until_saturday = 7  # Next Saturday, not today
        return today + timedelta(days=days_until_saturday)
    
    @staticmethod
    def next_month() -> date:
        """Get a date in the next month, consistently across all tests."""
        today = TestFixtures.today()
        if today.month == 12:
            return date(today.year + 1, 1, 15)  # Middle of next month
        else:
            return date(today.year, today.month + 1, 15)  # Middle of next month
    
    @staticmethod
    def create_travel_state(
        session_id: Optional[str] = None,
        conversation_stage: ConversationStage = ConversationStage.INITIAL,
        with_messages: bool = True,
        with_parameters: bool = False
    ) -> TravelState:
        """
        Create a travel state for testing.
        
        Args:
            session_id: Session ID (default: auto-generated)
            conversation_stage: Stage of conversation
            with_messages: Whether to include sample messages
            with_parameters: Whether to include sample parameters
            
        Returns:
            A TravelState instance
        """
        state = TravelState(
            session_id=session_id or f"test_session_{datetime.now().timestamp()}",
            conversation_stage=conversation_stage
        )
        
        # Add messages if requested
        if with_messages:
            state.add_message("user", "Hello travel agent")
            state.add_message("assistant", "Hello! How can I help you with your travel plans today?")
        
        # Add parameters if requested
        if with_parameters:
            # Add origin
            state.add_origin(LocationParameter(
                name="New York",
                type="origin",
                confidence=0.95
            ))
            state.extracted_parameters.add("origin")
            
            # Add destination
            state.add_destination(LocationParameter(
                name="Paris",
                type="destination",
                confidence=0.95
            ))
            state.extracted_parameters.add("destination")
            
            # Add dates
            state.add_date(DateParameter(
                type="departure",
                date_value=TestFixtures.next_week(),
                flexible=False,
                confidence=0.95
            ))
            state.extracted_parameters.add("date")
            
            # Add return date (one week later)
            state.add_date(DateParameter(
                type="return",
                date_value=TestFixtures.next_week() + timedelta(days=7),
                flexible=False,
                confidence=0.95
            ))
            state.extracted_parameters.add("return_date")
            
            # Set other parameters
            state.is_one_way = False
            state.adults = 2
            state.children = 0
            
        return state
    
    @staticmethod
    def create_flight_state(
        origin: str = "JFK",
        destination: str = "LAX",
        departure_date: Optional[date] = None,
        return_date: Optional[date] = None,
        is_one_way: bool = False,
        conversation_stage: ConversationStage = ConversationStage.PARAMETER_EXTRACTION
    ) -> TravelState:
        """
        Create a travel state for flight-specific testing.
        
        Args:
            origin: Origin airport or city
            destination: Destination airport or city
            departure_date: Departure date (default: next week)
            return_date: Return date (default: 7 days after departure)
            is_one_way: Whether the flight is one-way
            conversation_stage: Stage of conversation
            
        Returns:
            A TravelState instance configured for flight search
        """
        state = TravelState(
            session_id=f"test_flight_{origin}_{destination}_{datetime.now().timestamp()}",
            conversation_stage=conversation_stage
        )
        
        # Add messages
        state.add_message("user", f"I want to fly from {origin} to {destination}")
        state.add_message("assistant", "I'll help you find flights. When would you like to travel?")
        state.add_message("user", "Next week")
        
        # Add parameters
        state.add_origin(LocationParameter(
            name=origin,
            type="origin",
            confidence=0.95
        ))
        state.extracted_parameters.add("origin")
        
        state.add_destination(LocationParameter(
            name=destination,
            type="destination",
            confidence=0.95
        ))
        state.extracted_parameters.add("destination")
        
        # Set dates
        departure = departure_date or TestFixtures.next_week()
        state.add_date(DateParameter(
            type="departure",
            date_value=departure,
            flexible=False,
            confidence=0.95
        ))
        state.extracted_parameters.add("date")
        
        if not is_one_way and return_date:
            state.add_date(DateParameter(
                type="return",
                date_value=return_date,
                flexible=False,
                confidence=0.95
            ))
            state.extracted_parameters.add("return_date")
        elif not is_one_way:
            # Default to 7 days after departure
            state.add_date(DateParameter(
                type="return",
                date_value=departure + timedelta(days=7),
                flexible=False,
                confidence=0.95
            ))
            state.extracted_parameters.add("return_date")
        
        # Set trip type
        state.is_one_way = is_one_way
        state.extracted_parameters.add("trip_type")
        
        # Set passenger count
        state.adults = 1
        state.children = 0
        
        return state
    
    @staticmethod
    def create_hotel_state(
        location: str = "Paris",
        check_in_date: Optional[date] = None,
        check_out_date: Optional[date] = None,
        guests: int = 2,
        conversation_stage: ConversationStage = ConversationStage.PARAMETER_EXTRACTION
    ) -> TravelState:
        """
        Create a travel state for hotel-specific testing.
        
        Args:
            location: Hotel location
            check_in_date: Check-in date (default: next week)
            check_out_date: Check-out date (default: 3 days after check-in)
            guests: Number of guests
            conversation_stage: Stage of conversation
            
        Returns:
            A TravelState instance configured for hotel search
        """
        state = TravelState(
            session_id=f"test_hotel_{location}_{datetime.now().timestamp()}",
            conversation_stage=conversation_stage
        )
        
        # Add messages
        state.add_message("user", f"I need a hotel in {location}")
        state.add_message("assistant", "I'll help you find hotels. When would you like to check in?")
        state.add_message("user", "Next week for 3 nights")
        
        # Add parameters
        state.add_destination(LocationParameter(
            name=location,
            type="destination",
            confidence=0.95
        ))
        state.extracted_parameters.add("destination")
        
        # Set dates
        check_in = check_in_date or TestFixtures.next_week()
        check_out = check_out_date or (check_in + timedelta(days=3))
        
        state.add_date(DateParameter(
            type="departure",  # Check-in
            date_value=check_in,
            flexible=False,
            confidence=0.95
        ))
        state.extracted_parameters.add("date")
        
        state.add_date(DateParameter(
            type="return",  # Check-out
            date_value=check_out,
            flexible=False,
            confidence=0.95
        ))
        state.extracted_parameters.add("return_date")
        
        # Set guest count
        state.adults = guests
        state.children = 0
        
        # Set hotel flag
        state.hotel_needed = True
        
        return state
    
    @staticmethod
    def sample_serper_flight_response() -> Dict[str, Any]:
        """Get a sample Serper API response for flights."""
        return {
            "searchParameters": {
                "q": "flights from JFK to LAX next week one way",
                "gl": "us",
                "hl": "en",
                "num": 10,
                "timeSearched": "2025-04-18T12:34:56Z"
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
                },
                {
                    "title": "United Airlines: JFK to LAX from $279",
                    "link": "https://example.com/united/jfk-lax",
                    "snippet": "JFK to LAX flights with United. Departs JFK 10:30 AM, arrives LAX 2:15 PM. One-way flights from $279. Free checked bag for members."
                }
            ],
            "knowledge_graph": {
                "title": "Flights from JFK to LAX",
                "type": "Product",
                "attributes": {
                    "Duration": "About 6 hours",
                    "Distance": "2,475 miles",
                    "Price Range": "$199 - $500+",
                    "Airlines": "American, Delta, United, JetBlue"
                }
            }
        }
    
    @staticmethod
    def sample_serper_hotel_response() -> Dict[str, Any]:
        """Get a sample Serper API response for hotels."""
        return {
            "searchParameters": {
                "q": "hotels in Paris next week",
                "gl": "us",
                "hl": "en",
                "num": 10,
                "timeSearched": "2025-04-18T12:34:56Z"
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
                },
                {
                    "title": "Paris Boutique Hotel - Left Bank",
                    "link": "https://example.com/hotels/paris-boutique",
                    "snippet": "3-star boutique hotel in the Latin Quarter. $199 per night. Charming rooms, continental breakfast. 4.3/5 rating from 756 reviews."
                }
            ],
            "knowledge_graph": {
                "title": "Hotels in Paris",
                "type": "Product",
                "attributes": {
                    "Average Price": "$150 - $500 per night",
                    "Popular Areas": "Eiffel Tower, Champs-Élysées, Louvre, Latin Quarter",
                    "Best Time to Visit": "April to June, September to October",
                    "Average Rating": "4.2/5"
                }
            }
        }
    
    @staticmethod
    def sample_structured_flight_results() -> Dict[str, Any]:
        """Get sample structured flight search results."""
        next_week = TestFixtures.next_week()
        
        return {
            "flights": [
                {
                    "airline": "American Airlines",
                    "flight_number": "AA123",
                    "origin": "JFK",
                    "destination": "LAX",
                    "departure_date": next_week.isoformat(),
                    "departure_time": "08:00",
                    "arrival_time": "11:30",
                    "price": "$199",
                    "currency": "USD",
                    "duration": "6h 30m",
                    "stops": "Nonstop",
                    "link": "https://example.com/flights/jfk-lax/aa123"
                },
                {
                    "airline": "Delta",
                    "flight_number": "DL456",
                    "origin": "JFK",
                    "destination": "LAX",
                    "departure_date": next_week.isoformat(),
                    "departure_time": "09:15",
                    "arrival_time": "12:45",
                    "price": "$249",
                    "currency": "USD",
                    "duration": "6h 30m",
                    "stops": "Nonstop",
                    "link": "https://example.com/flights/jfk-lax/dl456"
                },
                {
                    "airline": "United Airlines",
                    "flight_number": "UA789",
                    "origin": "JFK",
                    "destination": "LAX",
                    "departure_date": next_week.isoformat(),
                    "departure_time": "10:30",
                    "arrival_time": "14:15",
                    "price": "$279",
                    "currency": "USD",
                    "duration": "6h 45m",
                    "stops": "Nonstop",
                    "link": "https://example.com/flights/jfk-lax/ua789"
                }
            ],
            "raw_results": TestFixtures.sample_serper_flight_response(),
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def sample_structured_hotel_results() -> Dict[str, Any]:
        """Get sample structured hotel search results."""
        next_week = TestFixtures.next_week()
        check_out = next_week + timedelta(days=3)
        
        return {
            "hotels": [
                {
                    "name": "Grand Hotel Paris",
                    "address": "123 Champs-Élysées, Paris",
                    "rating": "4.7",
                    "price": "$299",
                    "currency": "USD",
                    "check_in": next_week.isoformat(),
                    "check_out": check_out.isoformat(),
                    "amenities": ["WiFi", "Breakfast", "Spa"],
                    "link": "https://example.com/hotels/grand-hotel-paris"
                },
                {
                    "name": "Eiffel Tower View Hotel",
                    "address": "45 Avenue de la Tour, Paris",
                    "rating": "4.5",
                    "price": "$249",
                    "currency": "USD",
                    "check_in": next_week.isoformat(),
                    "check_out": check_out.isoformat(),
                    "amenities": ["WiFi", "Restaurant", "Bar"],
                    "link": "https://example.com/hotels/eiffel-tower-view"
                },
                {
                    "name": "Paris Boutique Hotel",
                    "address": "78 Rue Saint-Louis, Paris",
                    "rating": "4.3",
                    "price": "$199",
                    "currency": "USD",
                    "check_in": next_week.isoformat(),
                    "check_out": check_out.isoformat(),
                    "amenities": ["WiFi", "Breakfast"],
                    "link": "https://example.com/hotels/paris-boutique"
                }
            ],
            "raw_results": TestFixtures.sample_serper_hotel_response(),
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def sample_llm_parameter_extraction_response(query_type: str = "flight") -> Dict[str, Any]:
        """
        Get a sample LLM response for parameter extraction.
        
        Args:
            query_type: Type of query (flight, hotel, etc.)
            
        Returns:
            Sample LLM response
        """
        next_week = TestFixtures.next_week()
        
        if query_type == "flight":
            content = json.dumps({
                "query_type": "flight",
                "origin": "JFK",
                "destination": "LAX",
                "departure_date": next_week.isoformat(),
                "return_date": (next_week + timedelta(days=7)).isoformat(),
                "is_one_way": False,
                "adults": 1,
                "children": 0,
                "class": "economy"
            })
        elif query_type == "hotel":
            content = json.dumps({
                "query_type": "hotel",
                "location": "Paris",
                "check_in_date": next_week.isoformat(),
                "check_out_date": (next_week + timedelta(days=3)).isoformat(),
                "guests": 2,
                "rooms": 1,
                "hotel_amenities": ["wifi", "breakfast"]
            })
        else:
            content = json.dumps({
                "query_type": "unknown",
                "message": "I'm not sure what you're looking for. Could you provide more details?"
            })
        
        return {
            "choices": [
                {
                    "message": {
                        "content": content
                    }
                }
            ]
        }


# Save fixtures to a JSON file for easy loading in tests
def save_fixtures_to_json():
    """Save test fixtures to JSON files for use in tests."""
    fixtures_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixture_data")
    os.makedirs(fixtures_dir, exist_ok=True)
    
    # Save flight search response
    with open(os.path.join(fixtures_dir, "flight_search_response.json"), "w") as f:
        json.dump(TestFixtures.sample_serper_flight_response(), f, indent=2)
    
    # Save hotel search response
    with open(os.path.join(fixtures_dir, "hotel_search_response.json"), "w") as f:
        json.dump(TestFixtures.sample_serper_hotel_response(), f, indent=2)
    
    # Save structured flight results
    with open(os.path.join(fixtures_dir, "structured_flight_results.json"), "w") as f:
        json.dump(TestFixtures.sample_structured_flight_results(), f, indent=2)
    
    # Save structured hotel results
    with open(os.path.join(fixtures_dir, "structured_hotel_results.json"), "w") as f:
        json.dump(TestFixtures.sample_structured_hotel_results(), f, indent=2)
    
    # Save LLM parameter extraction responses
    with open(os.path.join(fixtures_dir, "llm_flight_extraction.json"), "w") as f:
        json.dump(TestFixtures.sample_llm_parameter_extraction_response("flight"), f, indent=2)
    
    with open(os.path.join(fixtures_dir, "llm_hotel_extraction.json"), "w") as f:
        json.dump(TestFixtures.sample_llm_parameter_extraction_response("hotel"), f, indent=2)


if __name__ == "__main__":
    save_fixtures_to_json()
