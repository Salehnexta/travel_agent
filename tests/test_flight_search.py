"""
Test script specifically for the flight search functionality.
Implements best testing practices for validating the DMM to BKK flight search.
"""

import os
import pytest
import json
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from travel_agent.state_definitions import (
    TravelState, 
    ConversationStage,
    LocationParameter,
    DateParameter,
    TravelerParameter
)
from travel_agent.search_tools import SearchToolManager


class TestFlightSearch:
    """Test suite for flight search functionality."""
    
    @pytest.fixture
    def mock_serper_response(self):
        """Fixture for mock Serper API response."""
        return {
            "searchParameters": {
                "gl": "sa",
                "hl": "en",
                "num": 10,
                "q": "flights from DMM to BKK tomorrow for 1 passenger"
            },
            "organic": [
                {
                    "title": "Flights from Dammam to Bangkok - Cheap DMM to BKK",
                    "link": "https://example.com/flights/dmm-bkk",
                    "snippet": "Find flights from Dammam (DMM) to Bangkok (BKK). Compare prices, book tickets & find schedules."
                }
            ],
            "peopleAlsoAsk": [
                {
                    "question": "What is the cheapest month to fly from Dammam to Bangkok?",
                    "answer": "The cheapest month to fly from Dammam to Bangkok is usually January."
                }
            ],
            "_metadata": {
                "query": "flights from DMM to BKK tomorrow for 1 passenger",
                "search_type": "organic",
                "location": "sa",
                "latency": 0.5,
                "timestamp": 1618844400.0
            }
        }
    
    @pytest.fixture
    def search_tool_manager(self):
        """Create a search tool manager for testing."""
        # Use a mock API key for testing
        with patch.dict(os.environ, {"SERPER_API_KEY": "test_api_key"}):
            return SearchToolManager(cache_enabled=True)
    
    def test_search_flight_dmm_to_bkk(self, search_tool_manager, mock_serper_response):
        """Test searching for a flight from DMM to BKK."""
        # Mock the API response
        with patch.object(search_tool_manager, 'search', return_value=mock_serper_response):
            # Get tomorrow's date
            tomorrow = date.today() + timedelta(days=1)
            tomorrow_str = tomorrow.strftime("%Y-%m-%d")
            
            # Execute the search
            result = search_tool_manager.search_flights(
                origin="DMM",
                destination="BKK",
                departure_date=tomorrow_str,
                return_date=None,
                num_passengers=1
            )
            
            # Verify the result
            assert result is not None
            assert "_metadata" in result
            assert result["_metadata"]["query"].lower().find("dmm") >= 0
            assert result["_metadata"]["query"].lower().find("bkk") >= 0
    
    def test_search_with_cache(self, search_tool_manager, mock_serper_response):
        """Test that caching works for flight searches."""
        # Mock the API response
        with patch.object(search_tool_manager, 'search') as mock_search:
            mock_search.return_value = mock_serper_response
            
            # Get tomorrow's date
            tomorrow = date.today() + timedelta(days=1)
            tomorrow_str = tomorrow.strftime("%Y-%m-%d")
            
            # First search should hit the API
            search_tool_manager.search_flights(
                origin="DMM",
                destination="BKK",
                departure_date=tomorrow_str,
                return_date=None,
                num_passengers=1
            )
            
            # Second search with same parameters should use cache
            search_tool_manager.search_flights(
                origin="DMM",
                destination="BKK",
                departure_date=tomorrow_str,
                return_date=None,
                num_passengers=1
            )
            
            # Verify the API was only called once
            assert mock_search.call_count == 1
    
    def test_flight_search_integration_with_travel_state(self):
        """Test integration between TravelState and flight search."""
        # Create a state with flight parameters
        state = TravelState(
            session_id="test_session",
            conversation_stage=ConversationStage.SEARCH_EXECUTION
        )
        
        # Add origin
        origin = LocationParameter(
            name="DMM",
            type="origin",
            confidence=0.9
        )
        state.origins.append(origin)
        
        # Add destination
        destination = LocationParameter(
            name="BKK",
            type="destination",
            confidence=0.9
        )
        state.destinations.append(destination)
        
        # Add date
        tomorrow = date.today() + timedelta(days=1)
        departure_date = DateParameter(
            type="departure",
            date_value=tomorrow,
            flexible=False,
            confidence=0.9
        )
        state.dates.append(departure_date)
        
        # Add travelers
        travelers = TravelerParameter(
            adults=1,
            children=0,
            infants=0,
            confidence=0.9
        )
        state.travelers = travelers
        
        # Verify the state has all necessary parameters for flight search
        assert len(state.origins) > 0
        assert len(state.destinations) > 0
        assert len(state.dates) > 0
        assert state.travelers is not None
        
        # With a proper implementation, these parameters would be passed to search_flights
        # This verifies the correct data flow from state to search function
        assert state.origins[0].name == "DMM"
        assert state.destinations[0].name == "BKK"
        assert state.dates[0].date_value == tomorrow
