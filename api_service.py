import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
import streamlit as st
import json

class TravelAgentAPI:
    BASE_URL = "http://localhost:5001/api"
    
    def __init__(self):
        self.session = requests.Session()
        self.last_request = None
        self.last_response = None
        # Configure more robust retry strategy
        retries = Retry(
            total=5,  # Increased from 3
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504, 408, 429],
            allowed_methods=["GET", "POST"],  # Allow POST retries
            raise_on_status=False,  # Don't raise exceptions on status
            respect_retry_after_header=True  # Honor Retry-After headers
        )
        self.session.mount('http://', HTTPAdapter(max_retries=retries))
    
    def send_chat(self, prompt, session_id, params):
        """Send chat to backend, track request/response"""
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        payload = {"message": prompt, "session_id": session_id, "params": params}
        self.last_request = payload
        
        try:
            response = self.session.post(f"{self.BASE_URL}/chat", headers=headers, json=payload, timeout=30)  # Increased timeout for LLM operations
            self.last_response = response.text
            if not response.text:
                st.error("Empty response from backend")
                return None
            try:
                return response.json()
            except json.JSONDecodeError:
                st.error("Invalid JSON from backend. Is Flask running?")
                return None
        except Exception as e:
            st.error(f"Connection error: {str(e)}")
            return None
