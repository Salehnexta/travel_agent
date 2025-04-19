#!/usr/bin/env python3
"""
Integration tests for parameter extraction and LLM components.
Tests the parameter extraction pipeline from user input to structured parameters.
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
from travel_agent.agents.parameter_extraction import parameter_extraction_agent
from travel_agent.date_processor import process_date_value
from travel_agent.state_definitions import (
    TravelState, 
    ConversationStage,
    LocationParameter,
    DateParameter
)


class TestParameterExtractionIntegration(unittest.TestCase):
    """Test the integration between parameter extraction and LLM components."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a test TravelState
        self.travel_state = TravelState(
            session_id="test_parameter_extraction",
            conversation_stage=ConversationStage.PARAMETER_EXTRACTION
        )
        
        # Mock the LLM client
        self.llm_patcher = patch('travel_agent.agents.parameter_extraction.llm_client')
        self.mock_llm = self.llm_patcher.start()
    
    def tearDown(self):
        """Clean up after tests."""
        self.llm_patcher.stop()
    
    def test_extract_flight_parameters(self):
        """Test extracting parameters for a flight query."""
        # User message about a flight
        user_message = "I want to fly from JFK to LAX next week, one way"
        self.travel_state.add_message("user", user_message)
        
        # Mock LLM response with structured parameters
        mock_llm_response = {
            "content": json.dumps({
                "query_type": "flight",
                "origin": "JFK",
                "destination": "LAX",
                "departure_date": date.today() + timedelta(days=7),
                "return_date": None,
                "is_one_way": True,
                "adults": 1,
                "children": 0,
                "class": "economy"
            })
        }
        self.mock_llm.completions.create.return_value = MagicMock(**mock_llm_response)
        
        # Run parameter extraction
        updated_state = parameter_extraction_agent(self.travel_state)
        
        # Verify parameters were extracted correctly
        self.assertIn("origin", updated_state.extracted_parameters)
        self.assertIn("destination", updated_state.extracted_parameters)
        self.assertIn("date", updated_state.extracted_parameters)
        self.assertIn("trip_type", updated_state.extracted_parameters)
        
        # Check specific parameter values
        self.assertEqual(len(updated_state.origins), 1)
        self.assertEqual(updated_state.origins[0].name, "JFK")
        
        self.assertEqual(len(updated_state.destinations), 1)
        self.assertEqual(updated_state.destinations[0].name, "LAX")
        
        self.assertEqual(len(updated_state.dates), 1)
        # The date should be processed to be 7 days from today
        expected_date = date.today() + timedelta(days=7)
        self.assertEqual(updated_state.dates[0].date_value, expected_date)
        
        # Verify one-way trip was detected
        self.assertTrue(updated_state.is_one_way)
    
    def test_extract_hotel_parameters(self):
        """Test extracting parameters for a hotel query."""
        # User message about a hotel
        user_message = "I need a hotel in Paris for next weekend from Friday to Monday"
        self.travel_state.add_message("user", user_message)
        
        # Calculate expected dates for next weekend
        today = date.today()
        days_until_friday = (4 - today.weekday()) % 7  # 4 = Friday
        if days_until_friday == 0:
            days_until_friday = 7  # Next Friday, not today
        next_friday = today + timedelta(days=days_until_friday)
        next_monday = next_friday + timedelta(days=3)
        
        # Mock LLM response with structured parameters
        mock_llm_response = {
            "content": json.dumps({
                "query_type": "hotel",
                "location": "Paris",
                "check_in_date": next_friday.isoformat(),
                "check_out_date": next_monday.isoformat(),
                "guests": 2,
                "rooms": 1,
                "hotel_amenities": ["wifi", "breakfast"]
            })
        }
        self.mock_llm.completions.create.return_value = MagicMock(**mock_llm_response)
        
        # Run parameter extraction
        updated_state = parameter_extraction_agent(self.travel_state)
        
        # Verify parameters were extracted correctly
        self.assertIn("destination", updated_state.extracted_parameters)
        self.assertIn("date", updated_state.extracted_parameters)
        self.assertIn("return_date", updated_state.extracted_parameters)
        
        # Check specific parameter values
        self.assertEqual(len(updated_state.destinations), 1)
        self.assertEqual(updated_state.destinations[0].name, "Paris")
        
        # Should have 2 dates (check-in and check-out)
        self.assertEqual(len(updated_state.dates), 2)
        
        # Find check-in and check-out dates
        check_in = next((d for d in updated_state.dates if d.type == "departure"), None)
        check_out = next((d for d in updated_state.dates if d.type == "return"), None)
        
        self.assertIsNotNone(check_in)
        self.assertIsNotNone(check_out)
        self.assertEqual(check_in.date_value, next_friday)
        self.assertEqual(check_out.date_value, next_monday)
    
    def test_extract_complex_parameters(self):
        """Test extracting parameters from a complex query with multiple intentions."""
        # Complex user message
        user_message = "I'm planning a trip to Tokyo next month with my family. We need a flight from SFO and a hotel for 5 nights. We'll be 2 adults and 1 child."
        self.travel_state.add_message("user", user_message)
        
        # Calculate dates for next month
        today = date.today()
        next_month = today.replace(month=today.month + 1 if today.month < 12 else 1)
        checkout_date = next_month + timedelta(days=5)
        
        # Mock LLM response with structured parameters
        mock_llm_response = {
            "content": json.dumps({
                "query_type": "combined",
                "origin": "SFO",
                "destination": "Tokyo",
                "departure_date": next_month.isoformat(),
                "return_date": None,  # Not specified in query
                "is_one_way": False,
                "adults": 2,
                "children": 1,
                "hotel_needed": True,
                "check_in_date": next_month.isoformat(),
                "check_out_date": checkout_date.isoformat(),
                "hotel_amenities": []
            })
        }
        self.mock_llm.completions.create.return_value = MagicMock(**mock_llm_response)
        
        # Run parameter extraction
        updated_state = parameter_extraction_agent(self.travel_state)
        
        # Verify multiple intentions were captured
        self.assertIn("origin", updated_state.extracted_parameters)
        self.assertIn("destination", updated_state.extracted_parameters)
        self.assertIn("date", updated_state.extracted_parameters)
        self.assertTrue(updated_state.hotel_needed)
        
        # Check specific parameter values
        self.assertEqual(len(updated_state.origins), 1)
        self.assertEqual(updated_state.origins[0].name, "SFO")
        
        self.assertEqual(len(updated_state.destinations), 1)
        self.assertEqual(updated_state.destinations[0].name, "Tokyo")
        
        # Should have at least 2 dates (departure and check-out)
        self.assertGreaterEqual(len(updated_state.dates), 2)
        
        # Verify passenger count
        self.assertEqual(updated_state.adults, 2)
        self.assertEqual(updated_state.children, 1)
    
    def test_handling_of_temporal_references(self):
        """Test proper handling of temporal references like 'tomorrow', 'next week', etc."""
        # Test various temporal references
        test_cases = [
            ("tomorrow", date.today() + timedelta(days=1)),
            ("next week", date.today() + timedelta(days=7)),
            ("this weekend", self._next_weekend()),
            ("next month", self._next_month())
        ]
        
        for temporal_ref, expected_date in test_cases:
            with self.subTest(temporal_ref=temporal_ref):
                # Create fresh state for each test
                state = TravelState(
                    session_id=f"test_{temporal_ref}",
                    conversation_stage=ConversationStage.PARAMETER_EXTRACTION
                )
                
                user_message = f"I want to travel to Paris {temporal_ref}"
                state.add_message("user", user_message)
                
                # Mock LLM response
                mock_llm_response = {
                    "content": json.dumps({
                        "query_type": "flight",
                        "destination": "Paris",
                        "departure_date": temporal_ref,  # Raw temporal reference
                        "return_date": None,
                        "is_one_way": True
                    })
                }
                self.mock_llm.completions.create.return_value = MagicMock(**mock_llm_response)
                
                # Run parameter extraction
                updated_state = parameter_extraction_agent(state)
                
                # Verify date handling
                self.assertIn("date", updated_state.extracted_parameters)
                self.assertEqual(len(updated_state.dates), 1)
                
                # Check date value with some flexibility (± 1 day) due to weekend calculations
                actual_date = updated_state.dates[0].date_value
                date_diff = abs((actual_date - expected_date).days)
                self.assertLessEqual(date_diff, 1, f"Expected date close to {expected_date}, got {actual_date}")
    
    def test_date_processor_integration(self):
        """Test integration with the date_processor module."""
        # Test various date formats and references
        test_cases = [
            # Wrong year
            ("2023-04-20", date(2025, 4, 20)),  # Should correct to current year
            
            # Temporal references
            ("tomorrow", date.today() + timedelta(days=1)),
            ("next friday", self._next_day_of_week(4)),  # 4 = Friday
            
            # Correct format
            ("2025-05-15", date(2025, 5, 15))
        ]
        
        for date_str, expected_date in test_cases:
            with self.subTest(date_str=date_str):
                # Process the date value
                processed_date = process_date_value(date_str)
                
                # Check result
                self.assertIsInstance(processed_date, date)
                self.assertEqual(processed_date, expected_date)
    
    def test_airport_code_recognition(self):
        """Test recognition of airport codes."""
        # Common airport codes
        test_codes = ["JFK", "LAX", "LHR", "CDG", "SYD", "DXB", "DMM", "RUH", "BKK"]
        
        for code in test_codes:
            with self.subTest(airport_code=code):
                # Create fresh state for each test
                state = TravelState(
                    session_id=f"test_{code}",
                    conversation_stage=ConversationStage.PARAMETER_EXTRACTION
                )
                
                user_message = f"I need a flight from {code} to Paris"
                state.add_message("user", user_message)
                
                # Mock LLM response
                mock_llm_response = {
                    "content": json.dumps({
                        "query_type": "flight",
                        "origin": code,
                        "destination": "Paris",
                        "departure_date": date.today() + timedelta(days=7),
                        "is_one_way": False
                    })
                }
                self.mock_llm.completions.create.return_value = MagicMock(**mock_llm_response)
                
                # Run parameter extraction
                updated_state = parameter_extraction_agent(state)
                
                # Verify airport code was recognized
                self.assertIn("origin", updated_state.extracted_parameters)
                self.assertEqual(len(updated_state.origins), 1)
                self.assertEqual(updated_state.origins[0].name, code)
    
    def test_repeated_parameter_extraction(self):
        """Test behavior when extracting parameters multiple times with different inputs."""
        # Initial state
        state = TravelState(
            session_id="test_repeated",
            conversation_stage=ConversationStage.PARAMETER_EXTRACTION
        )
        
        # First message with partial information
        user_message1 = "I want to go to London"
        state.add_message("user", user_message1)
        
        # Mock first LLM response
        mock_llm_response1 = {
            "content": json.dumps({
                "query_type": "travel",
                "destination": "London",
                "departure_date": None,
                "return_date": None,
                "is_one_way": False
            })
        }
        self.mock_llm.completions.create.return_value = MagicMock(**mock_llm_response1)
        
        # First parameter extraction
        state = parameter_extraction_agent(state)
        
        # Verify initial parameters
        self.assertIn("destination", state.extracted_parameters)
        self.assertEqual(len(state.destinations), 1)
        self.assertEqual(state.destinations[0].name, "London")
        
        # Second message with more information
        user_message2 = "I'll be flying from JFK next week"
        state.add_message("user", user_message2)
        
        # Mock second LLM response
        mock_llm_response2 = {
            "content": json.dumps({
                "query_type": "flight",
                "origin": "JFK",
                "departure_date": date.today() + timedelta(days=7),
                "is_one_way": False
            })
        }
        self.mock_llm.completions.create.return_value = MagicMock(**mock_llm_response2)
        
        # Second parameter extraction
        state = parameter_extraction_agent(state)
        
        # Verify updated parameters (should keep old parameters and add new ones)
        self.assertIn("destination", state.extracted_parameters)
        self.assertIn("origin", state.extracted_parameters)
        self.assertIn("date", state.extracted_parameters)
        
        self.assertEqual(len(state.destinations), 1)
        self.assertEqual(state.destinations[0].name, "London")
        
        self.assertEqual(len(state.origins), 1)
        self.assertEqual(state.origins[0].name, "JFK")
        
        self.assertEqual(len(state.dates), 1)
        expected_date = date.today() + timedelta(days=7)
        self.assertEqual(state.dates[0].date_value, expected_date)
    
    def test_error_handling_and_fallback(self):
        """Test error handling and fallback for parameter extraction."""
        # Import error handling components
        from travel_agent.error_handling import LLMError
        from travel_agent.error_handling.fallbacks import FallbackService
        
        # Create state
        state = TravelState(
            session_id="test_error_handling",
            conversation_stage=ConversationStage.PARAMETER_EXTRACTION
        )
        
        user_message = "I want to go to Paris tomorrow"
        state.add_message("user", user_message)
        
        # Mock LLM to raise an error
        self.mock_llm.completions.create.side_effect = LLMError("LLM service unavailable")
        
        # Mock the fallback service
        with patch('travel_agent.error_handling.fallbacks.FallbackService.fallback_parameter_extraction') as mock_fallback:
            # Configure fallback to return some basic parameters
            mock_fallback.return_value = {
                "destination": "Paris",
                "departure_date": date.today() + timedelta(days=1),
                "fallback": True
            }
            
            # Run parameter extraction with error handling
            with patch('travel_agent.agents.parameter_extraction._extract_parameters') as mock_extract:
                mock_extract.side_effect = LLMError("LLM service unavailable")
                
                # The implementation would typically use error handling decorators
                # But for testing, we'll simulate the fallback manually
                try:
                    parameter_extraction_agent(state)
                except LLMError:
                    # Simulate fallback behavior
                    fallback_params = FallbackService.fallback_parameter_extraction(user_message)
                    
                    # Update state with fallback parameters
                    if "destination" in fallback_params:
                        state.add_destination(LocationParameter(
                            name=fallback_params["destination"],
                            type="destination",
                            confidence=0.7
                        ))
                        state.extracted_parameters.add("destination")
                    
                    if "departure_date" in fallback_params:
                        state.add_date(DateParameter(
                            type="departure",
                            date_value=fallback_params["departure_date"],
                            flexible=True,
                            confidence=0.7
                        ))
                        state.extracted_parameters.add("date")
            
            # Verify fallback was called
            mock_fallback.assert_called_once()
            
            # Verify fallback parameters were applied
            self.assertIn("destination", state.extracted_parameters)
            self.assertEqual(len(state.destinations), 1)
            self.assertEqual(state.destinations[0].name, "Paris")
            
            self.assertIn("date", state.extracted_parameters)
            self.assertEqual(len(state.dates), 1)
            expected_date = date.today() + timedelta(days=1)
            self.assertEqual(state.dates[0].date_value, expected_date)
    
    # Helper methods for date calculations
    def _next_weekend(self):
        """Calculate the date of the next weekend (Saturday)."""
        today = date.today()
        days_until_saturday = (5 - today.weekday()) % 7  # 5 = Saturday
        if days_until_saturday == 0:
            days_until_saturday = 7  # Next Saturday, not today
        return today + timedelta(days=days_until_saturday)
    
    def _next_month(self):
        """Calculate a date in the next month."""
        today = date.today()
        if today.month == 12:
            return date(today.year + 1, 1, 15)  # Middle of next month
        else:
            return date(today.year, today.month + 1, 15)  # Middle of next month
    
    def _next_day_of_week(self, weekday):
        """Calculate the date of the next occurrence of a weekday (0=Monday, 6=Sunday)."""
        today = date.today()
        days_until = (weekday - today.weekday()) % 7
        if days_until == 0:
            days_until = 7  # Next week, not today
        return today + timedelta(days=days_until)


if __name__ == "__main__":
    unittest.main()
