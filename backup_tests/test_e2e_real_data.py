#!/usr/bin/env python3
"""
End-to-End test for the travel agent using real data.
Tests a flight search from DMM to RUH and hotel search near the Ministry of Manufacturing.
Uses:
- Real LLM calls (DeepSeek/Groq)
- Real Serper search data
- LangGraph for orchestration
- Flask test client for HTTP API testing
"""

import os
import sys
import json
import logging
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('e2e_test')

# Import application
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app
from travel_agent.graph_builder import TravelAgentGraph
from travel_agent.error_tracking import ErrorTracker
from travel_agent.config.llm_provider import llm_provider

# Initialize error tracker
error_tracker = ErrorTracker('e2e_test')

class TravelAgentE2ETest(unittest.TestCase):
    """End-to-end test for the travel agent using real services"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        logger.info("Setting up E2E test environment")
        
        # Validate API keys
        cls.deepseek_available = bool(os.getenv('DEEPSEEK_API_KEY'))
        cls.groq_available = bool(os.getenv('GROQ_API_KEY'))
        cls.serper_available = bool(os.getenv('SERPER_API_KEY'))
        
        logger.info(f"DeepSeek API available: {cls.deepseek_available}")
        logger.info(f"Groq API available: {cls.groq_available}")
        logger.info(f"Serper API available: {cls.serper_available}")
        
        if not (cls.deepseek_available or cls.groq_available):
            logger.warning("No LLM API keys available. Test will be limited.")
        
        if not cls.serper_available:
            logger.warning("Serper API key not available. Search functionality will be limited.")
        
        # Initialize LangGraph
        cls.agent_graph = TravelAgentGraph()
        
        # Initialize Flask test client
        cls.client = app.test_client()
        cls.client.testing = True
    
    def setUp(self):
        """Set up before each test"""
        logger.info("Starting test")
    
    def tearDown(self):
        """Clean up after each test"""
        logger.info("Test completed")
    
    def test_llm_provider_initialization(self):
        """Test that LLM providers are correctly initialized"""
        logger.info("Testing LLM provider initialization")
        
        # Check that at least one client is available
        self.assertTrue(
            llm_provider.clients, 
            "No LLM clients were initialized"
        )
        
        # Log available models
        logger.info(f"Available LLM models: {list(llm_provider.clients.keys())}")
    
    def test_flight_dmm_to_ruh_direct(self):
        """Test direct LangGraph processing of flight query"""
        logger.info("Testing direct flight query from DMM to RUH using LangGraph")
        
        # Skip if no LLM API keys
        if not (self.deepseek_available or self.groq_available):
            self.skipTest("No LLM API keys available")
        
        # Create session
        session_id = "test-direct-1"
        state = self.agent_graph.create_session(session_id)
        
        # Process the query
        query = "I need a flight from DMM to RUH tomorrow"
        updated_state = self.agent_graph.process_message(state, query)
        
        # Check that conversation history was updated
        self.assertGreater(
            len(updated_state.conversation_history), 
            1, 
            "Conversation history not updated"
        )
        
        # Check that the locations were extracted
        has_origin = any(origin.name.upper() == "DMM" for origin in updated_state.origins)
        has_destination = any(dest.name.upper() == "RUH" for dest in updated_state.destinations)
        
        self.assertTrue(has_origin, "Origin (DMM) not recognized")
        self.assertTrue(has_destination, "Destination (RUH) not recognized")
        
        # Check that tomorrow's date was extracted
        tomorrow = date.today() + timedelta(days=1)
        has_tomorrow = any(
            (date_param.date_value == tomorrow) for date_param in updated_state.dates
            if date_param.date_value
        )
        
        self.assertTrue(has_tomorrow, "Tomorrow's date not recognized")
        
        # Print the assistant's response
        assistant_messages = [
            msg["content"] for msg in updated_state.conversation_history
            if msg["role"] == "assistant"
        ]
        
        if assistant_messages:
            logger.info(f"Assistant's response: {assistant_messages[-1]}")
    
    def test_hotel_near_ministry_direct(self):
        """Test direct LangGraph processing of hotel query"""
        logger.info("Testing direct hotel query near Ministry of Manufacturing")
        
        # Skip if no LLM API keys
        if not (self.deepseek_available or self.groq_available):
            self.skipTest("No LLM API keys available")
        
        # Create session
        session_id = "test-direct-2"
        state = self.agent_graph.create_session(session_id)
        
        # Process the query
        query = "I need a hotel near the Ministry of Manufacturing in Riyadh for 1 night"
        updated_state = self.agent_graph.process_message(state, query)
        
        # Check that conversation history was updated
        self.assertGreater(
            len(updated_state.conversation_history), 
            1, 
            "Conversation history not updated"
        )
        
        # Check that the location was extracted
        has_riyadh = any(
            "riyadh" in dest.name.lower() for dest in updated_state.destinations
        )
        
        self.assertTrue(has_riyadh, "Riyadh not recognized as destination")
        
        # Check for preferences
        has_hotel_preference = False
        has_ministry_preference = False
        
        for pref in updated_state.preferences:
            if pref.category.lower() == "hotel":
                has_hotel_preference = True
                
                # Check if ministry is mentioned in preferences
                for preference in pref.preferences:
                    if "ministry" in preference.lower():
                        has_ministry_preference = True
                        break
        
        self.assertTrue(has_hotel_preference, "Hotel preference not recognized")
        self.assertTrue(has_ministry_preference, "Ministry location not recognized")
        
        # Print the assistant's response
        assistant_messages = [
            msg["content"] for msg in updated_state.conversation_history
            if msg["role"] == "assistant"
        ]
        
        if assistant_messages:
            logger.info(f"Assistant's response: {assistant_messages[-1]}")
    
    def test_combined_query_direct(self):
        """Test direct LangGraph processing of combined flight and hotel query"""
        logger.info("Testing direct combined flight and hotel query")
        
        # Skip if no LLM API keys
        if not (self.deepseek_available or self.groq_available):
            self.skipTest("No LLM API keys available")
        
        # Create session
        session_id = "test-direct-3"
        state = self.agent_graph.create_session(session_id)
        
        # Process the query
        query = "I need a flight from DMM to RUH tomorrow and a hotel near the Ministry of Manufacturing"
        updated_state = self.agent_graph.process_message(state, query)
        
        # Check that conversation history was updated
        self.assertGreater(
            len(updated_state.conversation_history), 
            1, 
            "Conversation history not updated"
        )
        
        # Check that the locations were extracted
        has_origin = any(origin.name.upper() == "DMM" for origin in updated_state.origins)
        has_destination = any(dest.name.upper() == "RUH" for dest in updated_state.destinations)
        
        self.assertTrue(has_origin, "Origin (DMM) not recognized")
        self.assertTrue(has_destination, "Destination (RUH) not recognized")
        
        # Check that tomorrow's date was extracted
        tomorrow = date.today() + timedelta(days=1)
        has_tomorrow = any(
            (date_param.date_value == tomorrow) for date_param in updated_state.dates
            if date_param.date_value
        )
        
        self.assertTrue(has_tomorrow, "Tomorrow's date not recognized")
        
        # Check for hotel preferences
        has_hotel_preference = False
        has_ministry_preference = False
        
        for pref in updated_state.preferences:
            if pref.category.lower() == "hotel":
                has_hotel_preference = True
                
                # Check if ministry is mentioned in preferences
                for preference in pref.preferences:
                    if "ministry" in preference.lower():
                        has_ministry_preference = True
                        break
        
        self.assertTrue(has_hotel_preference, "Hotel preference not recognized")
        self.assertTrue(has_ministry_preference, "Ministry location not recognized")
        
        # Print the assistant's response
        assistant_messages = [
            msg["content"] for msg in updated_state.conversation_history
            if msg["role"] == "assistant"
        ]
        
        if assistant_messages:
            logger.info(f"Assistant's response: {assistant_messages[-1]}")
    
    def test_api_endpoint(self):
        """Test the Flask API endpoint for chat"""
        logger.info("Testing Flask API endpoint for chat")
        
        # Send a request to the chat endpoint
        response = self.client.post(
            '/api/chat',
            json={
                'message': 'I need a flight from DMM to RUH tomorrow'
            }
        )
        
        # Check the response
        self.assertEqual(response.status_code, 200, "API request failed")
        data = json.loads(response.data)
        
        # Check that a response and session_id were returned
        self.assertIn('response', data, "No response in API result")
        self.assertIn('session_id', data, "No session_id in API result")
        
        logger.info(f"API response: {data['response'][:100]}...")
    
    def test_arabic_query(self):
        """Test processing an Arabic query"""
        logger.info("Testing Arabic query processing")
        
        # Skip if no LLM API keys
        if not (self.deepseek_available or self.groq_available):
            self.skipTest("No LLM API keys available")
        
        # Create session
        session_id = "test-arabic-1"
        state = self.agent_graph.create_session(session_id)
        
        # Process an Arabic query
        query = "أحتاج رحلة طيران من الدمام إلى الرياض غدا وفندق قريب من وزارة الصناعة"
        updated_state = self.agent_graph.process_message(state, query)
        
        # Check that conversation history was updated
        self.assertGreater(
            len(updated_state.conversation_history), 
            1, 
            "Conversation history not updated"
        )
        
        # Check that the locations were extracted (either as DMM/RUH or by full name)
        has_origin = any(
            origin.name.upper() == "DMM" or "دمام" in origin.name.lower()
            for origin in updated_state.origins
        )
        
        has_destination = any(
            dest.name.upper() == "RUH" or "رياض" in dest.name.lower()
            for dest in updated_state.destinations
        )
        
        self.assertTrue(has_origin, "Origin (Dammam) not recognized in Arabic")
        self.assertTrue(has_destination, "Destination (Riyadh) not recognized in Arabic")
        
        # Print the assistant's response
        assistant_messages = [
            msg["content"] for msg in updated_state.conversation_history
            if msg["role"] == "assistant"
        ]
        
        if assistant_messages:
            logger.info(f"Assistant's response to Arabic query: {assistant_messages[-1]}")
    
    def test_search_execution(self):
        """Test the search execution for flights"""
        logger.info("Testing search execution for flights")
        
        # Skip if no Serper API key
        if not self.serper_available:
            self.skipTest("Serper API key not available")
        
        # Skip if no LLM API keys
        if not (self.deepseek_available or self.groq_available):
            self.skipTest("No LLM API keys available")
        
        # Create session and advance to search stage
        session_id = "test-search-1"
        state = self.agent_graph.create_session(session_id)
        
        # First add flight parameters
        query = "I need a flight from DMM to RUH tomorrow"
        updated_state = self.agent_graph.process_message(state, query)
        
        # Print search results if available
        if updated_state.search_results:
            logger.info("Search results available:")
            for category, results in updated_state.search_results.items():
                logger.info(f"Category: {category}, Results: {len(results)}")
                
                # Print details of first result
                if results:
                    logger.info(f"Sample result: {results[0].data}")
            
            # Check that flight results were found
            has_flight_results = "flight" in updated_state.search_results
            self.assertTrue(has_flight_results, "No flight search results found")
        else:
            logger.warning("No search results available")


if __name__ == '__main__':
    unittest.main(verbosity=2)
