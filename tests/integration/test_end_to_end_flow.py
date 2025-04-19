#!/usr/bin/env python3
"""
End-to-end integration tests for the complete travel agent workflow.
Tests the flow from user input through parameter extraction, search, and response generation.
"""

import unittest
import sys
import os
import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import test fixtures
from tests.fixtures import TestFixtures

# Import components to test
from travel_agent.app import travel_agent
from travel_agent.state_definitions import (
    TravelState, 
    ConversationStage,
    LocationParameter,
    DateParameter
)
from travel_agent.date_processor import process_date_value


class TestEndToEndFlow(unittest.TestCase):
    """Test the end-to-end flow of the travel agent system."""
    
    def setUp(self):
        """Set up test environment."""
        # Create patchers for external services
        self.llm_patcher = patch('travel_agent.agents.parameter_extraction.llm_client')
        self.serper_patcher = patch('travel_agent.agents.search.serper_client')
        
        # Start patchers
        self.mock_llm = self.llm_patcher.start()
        self.mock_serper = self.serper_patcher.start()
    
    def tearDown(self):
        """Clean up after tests."""
        self.llm_patcher.stop()
        self.serper_patcher.stop()
    
    def test_flight_search_end_to_end(self):
        """Test complete flow for flight search."""
        # Create initial state
        state = TravelState(
            session_id="test_e2e_flight",
            conversation_stage=ConversationStage.INITIAL
        )
        
        # User message about a flight
        user_message = "I want to fly from DMM to BKK tomorrow one way"
        
        # Configure mocks
        # 1. Parameter extraction response
        tomorrow = TestFixtures.tomorrow()
        mock_extraction_response = {
            "content": json.dumps({
                "query_type": "flight",
                "origin": "DMM",
                "destination": "BKK",
                "departure_date": tomorrow.isoformat(),
                "return_date": None,
                "is_one_way": True,
                "adults": 1,
                "children": 0,
                "class": "economy"
            })
        }
        self.mock_llm.completions.create.return_value = MagicMock(**mock_extraction_response)
        
        # 2. Search response
        self.mock_serper.search.return_value = TestFixtures.sample_serper_flight_response()
        
        # Run the complete flow
        response, _ = travel_agent.handle_message(state, user_message)
        
        # Verify flow progression
        # 1. Parameter extraction should have been performed
        self.mock_llm.completions.create.assert_called_once()
        
        # 2. Search should have been performed
        self.mock_serper.search.assert_called_once()
        
        # 3. State should have extracted parameters
        self.assertIn("origin", state.extracted_parameters)
        self.assertIn("destination", state.extracted_parameters)
        self.assertIn("date", state.extracted_parameters)
        self.assertIn("trip_type", state.extracted_parameters)
        
        # 4. Check specific parameters
        self.assertEqual(len(state.origins), 1)
        self.assertEqual(state.origins[0].name, "DMM")
        
        self.assertEqual(len(state.destinations), 1)
        self.assertEqual(state.destinations[0].name, "BKK")
        
        # 5. Check date handling with temporal reference
        self.assertEqual(len(state.dates), 1)
        self.assertEqual(state.dates[0].date_value, tomorrow)
        
        # 6. Verify trip type
        self.assertTrue(state.is_one_way)
        
        # 7. State should have search results
        self.assertIsNotNone(state.search_results)
        self.assertGreater(len(state.search_results.get("flights", [])), 0)
        
        # 8. Response should mention flight details
        self.assertIn("flight", response.lower())
        self.assertIn("DMM", response)
        self.assertIn("BKK", response)
    
    def test_hotel_search_end_to_end(self):
        """Test complete flow for hotel search."""
        # Create initial state
        state = TravelState(
            session_id="test_e2e_hotel",
            conversation_stage=ConversationStage.INITIAL
        )
        
        # User message about a hotel
        next_weekend = TestFixtures.next_weekend()
        user_message = "I need a hotel in Paris for next weekend"
        
        # Configure mocks
        # 1. Parameter extraction response
        mock_extraction_response = {
            "content": json.dumps({
                "query_type": "hotel",
                "location": "Paris",
                "check_in_date": next_weekend.isoformat(),
                "check_out_date": (next_weekend + timedelta(days=2)).isoformat(),
                "guests": 2,
                "rooms": 1,
                "hotel_amenities": ["wifi", "breakfast"]
            })
        }
        self.mock_llm.completions.create.return_value = MagicMock(**mock_extraction_response)
        
        # 2. Search response
        self.mock_serper.search.return_value = TestFixtures.sample_serper_hotel_response()
        
        # Run the complete flow
        response, _ = travel_agent.handle_message(state, user_message)
        
        # Verify flow progression
        # 1. Parameter extraction should have been performed
        self.mock_llm.completions.create.assert_called_once()
        
        # 2. Search should have been performed
        self.mock_serper.search.assert_called_once()
        
        # 3. State should have extracted parameters
        self.assertIn("destination", state.extracted_parameters)
        self.assertIn("date", state.extracted_parameters)
        self.assertIn("return_date", state.extracted_parameters)
        
        # 4. Check specific parameters
        self.assertEqual(len(state.destinations), 1)
        self.assertEqual(state.destinations[0].name, "Paris")
        
        # 5. Check date handling with temporal reference
        self.assertEqual(len(state.dates), 2)
        check_in = next((d for d in state.dates if d.type == "departure"), None)
        check_out = next((d for d in state.dates if d.type == "return"), None)
        
        self.assertIsNotNone(check_in)
        self.assertIsNotNone(check_out)
        self.assertEqual(check_in.date_value, next_weekend)
        self.assertEqual(check_out.date_value, next_weekend + timedelta(days=2))
        
        # 6. State should have search results
        self.assertIsNotNone(state.search_results)
        self.assertGreater(len(state.search_results.get("hotels", [])), 0)
        
        # 7. Response should mention hotel details
        self.assertIn("hotel", response.lower())
        self.assertIn("Paris", response)
    
    def test_progressive_parameter_extraction(self):
        """Test extracting parameters across multiple messages."""
        # Create initial state
        state = TravelState(
            session_id="test_e2e_progressive",
            conversation_stage=ConversationStage.INITIAL
        )
        
        # First user message with partial information
        first_message = "I want to go to London"
        
        # Configure mocks for first extraction
        mock_extraction_response1 = {
            "content": json.dumps({
                "query_type": "travel",
                "destination": "London",
                "departure_date": None,
                "return_date": None,
                "is_one_way": False
            })
        }
        self.mock_llm.completions.create.return_value = MagicMock(**mock_extraction_response1)
        
        # Run first message
        response1, _ = travel_agent.handle_message(state, first_message)
        
        # Verify partial parameters extracted
        self.assertIn("destination", state.extracted_parameters)
        self.assertEqual(len(state.destinations), 1)
        self.assertEqual(state.destinations[0].name, "London")
        
        # Response should ask for more information
        self.assertIn("when", response1.lower(), "Response should ask about travel dates")
        
        # Second user message with more information
        second_message = "I'll be traveling from New York next week"
        
        # Configure mocks for second extraction
        next_week = TestFixtures.next_week()
        mock_extraction_response2 = {
            "content": json.dumps({
                "query_type": "flight",
                "origin": "New York",
                "departure_date": next_week.isoformat(),
                "is_one_way": False
            })
        }
        self.mock_llm.completions.create.return_value = MagicMock(**mock_extraction_response2)
        
        # Run second message
        response2, _ = travel_agent.handle_message(state, second_message)
        
        # Verify updated parameters (should include both messages' information)
        self.assertIn("destination", state.extracted_parameters)
        self.assertIn("origin", state.extracted_parameters)
        self.assertIn("date", state.extracted_parameters)
        
        self.assertEqual(len(state.destinations), 1)
        self.assertEqual(state.destinations[0].name, "London")
        
        self.assertEqual(len(state.origins), 1)
        self.assertEqual(state.origins[0].name, "New York")
        
        self.assertEqual(len(state.dates), 1)
        self.assertEqual(state.dates[0].date_value, next_week)
        
        # Configure mock for search
        self.mock_serper.search.return_value = TestFixtures.sample_serper_flight_response()
        
        # Third message to trigger search
        third_message = "Please find flights for that trip"
        
        # Run third message
        response3, _ = travel_agent.handle_message(state, third_message)
        
        # Search should have been performed
        self.mock_serper.search.assert_called_once()
        
        # State should have search results
        self.assertIsNotNone(state.search_results)
        
        # Response should mention flight details
        self.assertIn("flight", response3.lower())
        self.assertIn("New York", response3)
        self.assertIn("London", response3)
    
    def test_temporal_reference_handling(self):
        """Test handling of temporal references in natural language queries."""
        # Test various temporal references
        test_cases = [
            ("tomorrow", TestFixtures.tomorrow()),
            ("next week", TestFixtures.next_week()),
            ("this weekend", TestFixtures.next_weekend()),
            ("next month", TestFixtures.next_month())
        ]
        
        for temporal_ref, expected_date in test_cases:
            with self.subTest(temporal_ref=temporal_ref):
                # Create fresh state for each test
                state = TravelState(
                    session_id=f"test_temporal_{temporal_ref}",
                    conversation_stage=ConversationStage.INITIAL
                )
                
                user_message = f"I want to fly from DMM to RUH {temporal_ref}"
                
                # Configure mocks
                # LLM might return the raw temporal reference
                mock_extraction_response = {
                    "content": json.dumps({
                        "query_type": "flight",
                        "origin": "DMM",
                        "destination": "RUH",
                        "departure_date": temporal_ref,  # Raw temporal reference
                        "is_one_way": True
                    })
                }
                self.mock_llm.completions.create.return_value = MagicMock(**mock_extraction_response)
                
                # Configure search response
                self.mock_serper.search.return_value = TestFixtures.sample_serper_flight_response()
                
                # Run the flow
                response, _ = travel_agent.handle_message(state, user_message)
                
                # Verify the temporal reference was properly resolved
                self.assertIn("date", state.extracted_parameters)
                self.assertEqual(len(state.dates), 1)
                
                # Date should be processed to match expected date
                actual_date = state.dates[0].date_value
                date_diff = abs((actual_date - expected_date).days)
                self.assertLessEqual(date_diff, 1, 
                                    f"Expected date close to {expected_date}, got {actual_date} for '{temporal_ref}'")
                
                # Response should mention the correct date
                date_str = actual_date.strftime("%B %d")  # e.g., "April 19"
                self.assertIn(date_str, response, f"Response should mention {date_str} for '{temporal_ref}'")
    
    def test_airport_code_recognition(self):
        """Test recognition of specific airport codes from improved system."""
        # Test special airport codes mentioned in the memory
        test_codes = ["DMM", "RUH", "BKK"]
        
        for code in test_codes:
            with self.subTest(airport_code=code):
                # Create fresh state for each test
                state = TravelState(
                    session_id=f"test_airport_{code}",
                    conversation_stage=ConversationStage.INITIAL
                )
                
                user_message = f"Find me flights from {code} to JFK next week"
                
                # Configure mocks
                mock_extraction_response = {
                    "content": json.dumps({
                        "query_type": "flight",
                        "origin": code,
                        "destination": "JFK",
                        "departure_date": TestFixtures.next_week().isoformat(),
                        "is_one_way": False
                    })
                }
                self.mock_llm.completions.create.return_value = MagicMock(**mock_extraction_response)
                
                # Configure search response
                self.mock_serper.search.return_value = TestFixtures.sample_serper_flight_response()
                
                # Run the flow
                response, _ = travel_agent.handle_message(state, user_message)
                
                # Verify airport code was recognized correctly
                self.assertIn("origin", state.extracted_parameters)
                self.assertEqual(len(state.origins), 1)
                self.assertEqual(state.origins[0].name, code)
                
                # Response should mention the airport code
                self.assertIn(code, response, f"Response should mention airport code {code}")
    
    def test_date_processor_handling_past_dates(self):
        """Test date processor correctly fixes outdated years."""
        # Test date with outdated year
        past_date = "2023-04-25"  # Should be corrected to 2025
        state = TravelState(
            session_id="test_date_correction",
            conversation_stage=ConversationStage.INITIAL
        )
        
        user_message = f"I want to fly from JFK to LAX on {past_date}"
        
        # Configure mocks
        # LLM might return the raw date
        mock_extraction_response = {
            "content": json.dumps({
                "query_type": "flight",
                "origin": "JFK",
                "destination": "LAX",
                "departure_date": past_date,  # Date with outdated year
                "is_one_way": True
            })
        }
        self.mock_llm.completions.create.return_value = MagicMock(**mock_extraction_response)
        
        # Configure search response
        self.mock_serper.search.return_value = TestFixtures.sample_serper_flight_response()
        
        # Run the flow
        response, _ = travel_agent.handle_message(state, user_message)
        
        # Verify date was corrected
        self.assertIn("date", state.extracted_parameters)
        self.assertEqual(len(state.dates), 1)
        
        # Year should be 2025, not 2023
        actual_date = state.dates[0].date_value
        self.assertEqual(actual_date.year, 2025)
        self.assertEqual(actual_date.month, 4)
        self.assertEqual(actual_date.day, 25)
        
        # Response should mention the correct year
        self.assertIn("2025", response, "Response should mention the corrected year 2025")
    
    def test_search_result_parser_with_raw_data(self):
        """Test the enhanced search result parser extracts structured data correctly."""
        # Create state and add some parameters
        state = TestFixtures.create_flight_state(
            origin="DMM", 
            destination="BKK",
            conversation_stage=ConversationStage.SEARCH
        )
        
        # Configure search response - use raw response without structured data
        raw_response = {
            "organic": [
                {
                    "title": "Flights from DMM to BKK - Best Deals for Tomorrow",
                    "snippet": "Book DMM to BKK flights. Saudi Airlines departs DMM 8:00 AM, arrives BKK 7:30 PM. $450. Thai Airways departs 10:15 AM, arrives 9:45 PM. $520."
                },
                {
                    "title": "Dammam (DMM) to Bangkok (BKK) - Direct Flights",
                    "snippet": "Nonstop flights from Dammam to Bangkok. Saudi Airlines SA123 departing 8:00 AM, arriving 7:30 PM, $450. Thai Airways TG456 departing 10:15 AM."
                }
            ]
        }
        self.mock_serper.search.return_value = raw_response
        
        # Run search
        response, _ = travel_agent.handle_message(state, "Please find flights")
        
        # Verify search was performed
        self.mock_serper.search.assert_called_once()
        
        # Check that structured data was extracted from unstructured response
        self.assertIsNotNone(state.search_results)
        self.assertIn("flights", state.search_results)
        
        # Parser should have extracted flight info
        flights = state.search_results.get("flights", [])
        self.assertGreaterEqual(len(flights), 1)
        
        # Check extracted data for Saudi Airlines
        saudi_flight = next((f for f in flights if "Saudi Airlines" in f.get("airline", "")), None)
        self.assertIsNotNone(saudi_flight, "Saudi Airlines flight should be extracted")
        
        # Check price and times were extracted
        self.assertEqual(saudi_flight.get("price"), "$450")
        self.assertIn("8:00", saudi_flight.get("departure_time", ""))
        
        # Response should mention flight details
        self.assertIn("saudi airlines", response.lower())
        self.assertIn("DMM", response)
        self.assertIn("BKK", response)
        self.assertIn("$450", response)


if __name__ == "__main__":
    unittest.main()
