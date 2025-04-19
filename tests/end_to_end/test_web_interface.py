#!/usr/bin/env python3
"""
End-to-end tests for the travel agent web interface.
Tests the complete flow from web UI to backend and response rendering.
"""

import unittest
import sys
import os
import json
import time
from unittest.mock import MagicMock, patch
import multiprocessing
import requests
import threading
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import Flask app for testing
from travel_agent.app import create_app

class TravelAgentTestServer:
    """Test server for running the travel agent application."""
    
    def __init__(self, host='localhost', port=5050):
        """Initialize the test server."""
        self.host = host
        self.port = port
        self.url = f"http://{host}:{port}"
        self.process = None
    
    def _run_app(self):
        """Run the Flask application."""
        app = create_app(testing=True)
        app.run(host=self.host, port=self.port, use_reloader=False)
    
    def start(self):
        """Start the test server in a separate process."""
        self.process = multiprocessing.Process(target=self._run_app)
        self.process.daemon = True
        self.process.start()
        
        # Wait for the server to start
        max_retries = 5
        for _ in range(max_retries):
            try:
                response = requests.get(f"{self.url}/api/health")
                if response.status_code == 200:
                    return True
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(1)
        
        raise RuntimeError("Failed to start test server")
    
    def stop(self):
        """Stop the test server."""
        if self.process:
            self.process.terminate()
            self.process.join(timeout=1)
            self.process = None

class TestWebInterface(unittest.TestCase):
    """End-to-end tests for the web interface."""
    
    @classmethod
    def setUpClass(cls):
        """Set up the test environment once for all tests."""
        # Start test server
        cls.server = TravelAgentTestServer()
        try:
            cls.server.start()
        except RuntimeError as e:
            cls.skipTest(cls, f"Failed to start test server: {str(e)}")
            return
        
        # Set up headless Chrome WebDriver
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Try to initialize WebDriver, skip tests if not available
        try:
            service = Service(ChromeDriverManager().install())
            cls.driver = webdriver.Chrome(service=service, options=chrome_options)
            cls.driver.implicitly_wait(10)
        except Exception as e:
            cls.server.stop()
            cls.skipTest(cls, f"WebDriver setup failed: {str(e)}")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up the test environment."""
        # Close WebDriver if initialized
        if hasattr(cls, 'driver'):
            cls.driver.quit()
        
        # Stop test server
        if hasattr(cls, 'server'):
            cls.server.stop()
    
    def test_page_title_and_elements(self):
        """Test that the page loads with the correct title and elements."""
        self.driver.get(self.server.url)
        
        # Check page title
        self.assertIn("Travel Agent", self.driver.title)
        
        # Check main elements exist
        self.assertIsNotNone(self.driver.find_element(By.ID, "chat-container"))
        self.assertIsNotNone(self.driver.find_element(By.ID, "user-input"))
        self.assertIsNotNone(self.driver.find_element(By.ID, "send-button"))
        self.assertIsNotNone(self.driver.find_element(By.ID, "reset-button"))
    
    @patch('travel_agent.app.travel_agent.handle_message')
    def test_send_message_flow(self, mock_handle_message):
        """Test sending a message and receiving a response."""
        # Configure mock to return a test response
        mock_handle_message.return_value = ("I can help you plan your trip to Paris. When would you like to travel?", True)
        
        # Navigate to the page
        self.driver.get(self.server.url)
        
        # Wait for page to load completely
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "user-input"))
        )
        
        # Send a message
        input_field = self.driver.find_element(By.ID, "user-input")
        input_field.send_keys("I want to travel to Paris")
        input_field.send_keys(Keys.RETURN)
        
        # Wait for response to appear
        WebDriverWait(self.driver, 10).until(
            EC.text_to_be_present_in_element(
                (By.CLASS_NAME, "message-content"),
                "I can help you plan your trip to Paris"
            )
        )
        
        # Check that message and response are displayed
        messages = self.driver.find_elements(By.CLASS_NAME, "message")
        
        # Should have at least 2 messages (user + response)
        self.assertGreaterEqual(len(messages), 2)
        
        # User message should contain the input text
        user_messages = self.driver.find_elements(By.CLASS_NAME, "user-message")
        self.assertGreaterEqual(len(user_messages), 1)
        self.assertIn("I want to travel to Paris", user_messages[-1].text)
        
        # Assistant message should contain the response
        assistant_messages = self.driver.find_elements(By.CLASS_NAME, "assistant-message")
        self.assertGreaterEqual(len(assistant_messages), 1)
        self.assertIn("I can help you plan your trip to Paris", assistant_messages[-1].text)
    
    def test_error_handling_in_ui(self):
        """Test that errors are properly displayed in the UI."""
        # Navigate to the page
        self.driver.get(self.server.url)
        
        # Wait for page to load completely
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "user-input"))
        )
        
        # Create a situation where an error will occur (by sending malformed message)
        # We'll use JavaScript to modify the underlying function to trigger an error
        error_script = """
        const originalFetch = window.fetch;
        window.fetch = function(url, options) {
            if (url.includes('/api/chat') && options.method === 'POST') {
                return new Promise((resolve) => {
                    resolve({
                        ok: false,
                        status: 500,
                        json: () => Promise.resolve({
                            error: 'LLMError',
                            message: 'Test error for UI display',
                            error_id: 'E-TEST-123456-1234567890'
                        })
                    });
                });
            }
            return originalFetch(url, options);
        };
        """
        self.driver.execute_script(error_script)
        
        # Send a message
        input_field = self.driver.find_element(By.ID, "user-input")
        input_field.send_keys("This will trigger an error")
        input_field.send_keys(Keys.RETURN)
        
        # Wait for error message to appear
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "error-message"))
        )
        
        # Check error message content
        error_messages = self.driver.find_elements(By.CLASS_NAME, "error-message")
        self.assertGreaterEqual(len(error_messages), 1)
        
        # Error message should contain the error details
        self.assertIn("Error", error_messages[-1].text)
        self.assertIn("E-TEST-123456-1234567890", error_messages[-1].text)
    
    def test_reset_conversation(self):
        """Test that the reset button clears the conversation."""
        # Navigate to the page
        self.driver.get(self.server.url)
        
        # Wait for page to load completely
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "user-input"))
        )
        
        # Send a message
        input_field = self.driver.find_element(By.ID, "user-input")
        input_field.send_keys("Hello travel agent")
        input_field.send_keys(Keys.RETURN)
        
        # Wait for message to appear
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "user-message"))
        )
        
        # Click reset button
        reset_button = self.driver.find_element(By.ID, "reset-button")
        reset_button.click()
        
        # Wait for reset to take effect (session ID should change)
        # This might be visible in the UI, or we can check if messages are cleared
        time.sleep(1)
        
        # Check that no messages are displayed
        messages = self.driver.find_elements(By.CLASS_NAME, "message")
        self.assertEqual(len(messages), 0)
    
    def test_flight_search_results_display(self):
        """Test that flight search results are displayed correctly."""
        # Navigate to the page
        self.driver.get(self.server.url)
        
        # Wait for page to load completely
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "user-input"))
        )
        
        # Inject mock flight search results
        mock_results_script = """
        // Mock function to display search results
        function displayMockResults() {
            const mockFlights = [
                {
                    airline: "Test Airlines",
                    flight_number: "TA123",
                    origin: "JFK",
                    destination: "LAX",
                    departure_date: "2025-05-01",
                    departure_time: "08:00",
                    arrival_time: "11:30",
                    price: "$299",
                    currency: "USD"
                },
                {
                    airline: "Mock Airways",
                    flight_number: "MA456",
                    origin: "JFK",
                    destination: "LAX",
                    departure_date: "2025-05-01",
                    departure_time: "10:15",
                    arrival_time: "13:45",
                    price: "$349",
                    currency: "USD"
                }
            ];
            
            // Get the formatting function from the page
            if (typeof formatFlightResults === 'function') {
                // Create container for the assistant message
                const messagesContainer = document.getElementById('chat-messages');
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message assistant-message';
                
                // Create the message content with formatted flight results
                const contentDiv = document.createElement('div');
                contentDiv.className = 'message-content';
                contentDiv.innerHTML = formatFlightResults(mockFlights);
                
                // Add to the message and container
                messageDiv.appendChild(contentDiv);
                messagesContainer.appendChild(messageDiv);
            }
        }
        
        // Call the function to display results
        displayMockResults();
        """
        self.driver.execute_script(mock_results_script)
        
        # Wait for flight results to appear
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "flight-card"))
        )
        
        # Check that flight cards are displayed
        flight_cards = self.driver.find_elements(By.CLASS_NAME, "flight-card")
        self.assertGreaterEqual(len(flight_cards), 2)
        
        # Check content of first flight card
        first_card = flight_cards[0]
        self.assertIn("Test Airlines", first_card.text)
        self.assertIn("JFK", first_card.text)
        self.assertIn("LAX", first_card.text)
        self.assertIn("$299", first_card.text)
    
    def test_hotel_search_results_display(self):
        """Test that hotel search results are displayed correctly."""
        # Navigate to the page
        self.driver.get(self.server.url)
        
        # Wait for page to load completely
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "user-input"))
        )
        
        # Inject mock hotel search results
        mock_results_script = """
        // Mock function to display search results
        function displayMockResults() {
            const mockHotels = [
                {
                    name: "Test Grand Hotel",
                    address: "123 Main St, New York, NY",
                    rating: "4.5",
                    price: "$199",
                    currency: "USD",
                    check_in: "2025-05-10",
                    check_out: "2025-05-15",
                    amenities: ["WiFi", "Pool", "Breakfast"]
                },
                {
                    name: "Mock Luxury Resort",
                    address: "456 Broadway, New York, NY",
                    rating: "4.8",
                    price: "$299",
                    currency: "USD",
                    check_in: "2025-05-10",
                    check_out: "2025-05-15",
                    amenities: ["WiFi", "Spa", "Restaurant"]
                }
            ];
            
            // Get the formatting function from the page
            if (typeof formatHotelResults === 'function') {
                // Create container for the assistant message
                const messagesContainer = document.getElementById('chat-messages');
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message assistant-message';
                
                // Create the message content with formatted hotel results
                const contentDiv = document.createElement('div');
                contentDiv.className = 'message-content';
                contentDiv.innerHTML = formatHotelResults(mockHotels);
                
                // Add to the message and container
                messageDiv.appendChild(contentDiv);
                messagesContainer.appendChild(messageDiv);
            }
        }
        
        // Call the function to display results
        displayMockResults();
        """
        self.driver.execute_script(mock_results_script)
        
        # Wait for hotel results to appear
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "hotel-card"))
        )
        
        # Check that hotel cards are displayed
        hotel_cards = self.driver.find_elements(By.CLASS_NAME, "hotel-card")
        self.assertGreaterEqual(len(hotel_cards), 2)
        
        # Check content of first hotel card
        first_card = hotel_cards[0]
        self.assertIn("Test Grand Hotel", first_card.text)
        self.assertIn("New York", first_card.text)
        self.assertIn("$199", first_card.text)
        self.assertIn("4.5", first_card.text)

if __name__ == "__main__":
    unittest.main()
