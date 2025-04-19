"""
Pytest configuration with fixtures for travel agent testing.
Implements best practices for test organization and mocking external services.
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
import json
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from travel_agent.state_definitions import (
    TravelState, 
    ConversationStage,
    LocationParameter,
    DateParameter,
    TravelerParameter,
    PreferenceParameter
)
from travel_agent.graph_builder_enhanced import EnhancedTravelAgentGraph
from travel_agent.config.env_manager import EnvironmentManager


@pytest.fixture
def env_manager():
    """Fixture for environment manager in test mode."""
    # Force test environment
    with patch.dict(os.environ, {"ENVIRONMENT": "testing"}):
        return EnvironmentManager("testing")


@pytest.fixture
def mock_redis():
    """Fixture for mocked Redis client."""
    mock = MagicMock()
    # Configure mock methods
    mock.get_json.return_value = None
    mock.store_json.return_value = True
    mock.delete.return_value = True
    mock.get.return_value = None
    mock.set.return_value = True
    
    return mock


@pytest.fixture
def mock_llm_client():
    """Fixture for mocked LLM client."""
    mock = MagicMock()
    mock.get_completion.return_value = {
        "choices": [
            {
                "message": {
                    "content": "This is a mock LLM response.",
                    "role": "assistant"
                }
            }
        ]
    }
    return mock


@pytest.fixture
def sample_travel_state():
    """Fixture for a sample travel state with basic data."""
    state = TravelState(
        session_id="test-session",
        conversation_stage=ConversationStage.PARAMETER_EXTRACTION
    )
    
    # Add some messages
    state.add_message("user", "I need a flight from DMM to BKK tomorrow")
    state.add_message("assistant", "I'll help you find a flight from DMM to BKK tomorrow.")
    
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
    
    return state


@pytest.fixture
def mock_search_results():
    """Fixture for mock search results."""
    # Flight search results
    flight_results = {
        "flights": [
            {
                "airline": "Saudi Airlines",
                "flight_number": "SV123",
                "departure": "DMM 08:00",
                "arrival": "BKK 18:30",
                "duration": "10h 30m",
                "price": "1200 SAR",
                "stops": 0
            },
            {
                "airline": "Thai Airways",
                "flight_number": "TG456",
                "departure": "DMM 14:15",
                "arrival": "BKK 23:45",
                "duration": "9h 30m",
                "price": "1350 SAR",
                "stops": 1
            }
        ]
    }
    
    # Hotel search results
    hotel_results = {
        "hotels": [
            {
                "name": "Grand Hyatt Bangkok",
                "stars": 5,
                "location": "Central Bangkok",
                "price_per_night": "850 SAR",
                "amenities": ["Pool", "Spa", "Free WiFi"]
            },
            {
                "name": "Sukhumvit Hotel",
                "stars": 4,
                "location": "Sukhumvit Road",
                "price_per_night": "550 SAR",
                "amenities": ["Free WiFi", "Restaurant"]
            }
        ]
    }
    
    return {
        "flights": flight_results,
        "hotels": hotel_results
    }


@pytest.fixture
def travel_agent_graph(mock_redis, mock_llm_client):
    """Fixture for travel agent graph with mocked dependencies."""
    with patch("travel_agent.config.redis_client.RedisManager", return_value=mock_redis), \
         patch("travel_agent.llm_provider.LLMClient", return_value=mock_llm_client):
        
        # Create graph with in-memory storage (not Redis)
        graph = EnhancedTravelAgentGraph(use_redis=False)
        return graph


@pytest.fixture
def mock_serper_flight_response():
    """Fixture for mock Serper flight search response."""
    return {
        "searchParameters": {
            "origin": "DMM",
            "destination": "BKK", 
            "date": date.today() + timedelta(days=1)
        },
        "flights": [
            {
                "airline": "Saudi Airlines",
                "departure_time": "08:00",
                "arrival_time": "18:30",
                "duration": "10h 30m",
                "price": 1200,
                "currency": "SAR",
                "stops": 0
            },
            {
                "airline": "Thai Airways",
                "departure_time": "14:15",
                "arrival_time": "23:45",
                "duration": "9h 30m",
                "price": 1350,
                "currency": "SAR",
                "stops": 1
            }
        ]
    }


@pytest.fixture
def mock_serper_hotel_response():
    """Fixture for mock Serper hotel search response."""
    return {
        "searchParameters": {
            "location": "BKK",
            "check_in": (date.today() + timedelta(days=1)).strftime("%Y-%m-%d"),
            "check_out": (date.today() + timedelta(days=4)).strftime("%Y-%m-%d")
        },
        "hotels": [
            {
                "name": "Grand Hyatt Bangkok",
                "rating": 5,
                "location": "Central Bangkok",
                "price_per_night": 850,
                "currency": "SAR",
                "amenities": ["Pool", "Spa", "Free WiFi"],
                "thumbnail": "https://example.com/thumbnail1.jpg",
                "url": "https://example.com/hotel1"
            },
            {
                "name": "Sukhumvit Hotel",
                "rating": 4,
                "location": "Sukhumvit Road",
                "price_per_night": 550,
                "currency": "SAR",
                "amenities": ["Free WiFi", "Restaurant"],
                "thumbnail": "https://example.com/thumbnail2.jpg",
                "url": "https://example.com/hotel2"
            }
        ]
    }
