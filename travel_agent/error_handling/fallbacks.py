"""
Fallback mechanisms for travel agent components.
Provides degraded but functional alternatives when primary services fail.
"""

import logging
import json
import os
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger('travel_agent.fallbacks')

class FallbackService:
    """
    Provides fallback implementations for critical services.
    Ensures system continues functioning in degraded mode.
    """
    
    @staticmethod
    def fallback_llm_response(prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Fallback for when LLM service is unavailable.
        Returns pre-defined responses for common queries.
        
        Args:
            prompt: The LLM prompt that failed
            context: Additional context
            
        Returns:
            Simple templated response
        """
        logger.warning(f"Using fallback LLM response for prompt: {prompt[:100]}...")
        
        # Extract potential keywords from prompt
        lower_prompt = prompt.lower()
        
        # Try to determine if this is a travel-related query
        response = {
            "content": "I'm sorry, but I'm experiencing temporary issues with my advanced thinking capabilities. "
                       "I can help with basic travel inquiries, but may not be able to process complex requests right now. "
                       "Please try again later or ask a simpler question.",
            "fallback": True
        }
        
        # If we can detect a specific query type, give a more helpful response
        if "flight" in lower_prompt or "fly" in lower_prompt:
            response["content"] = "I'm having trouble accessing flight information right now. Please try again later or contact customer service for immediate assistance with your flight."
        
        elif "hotel" in lower_prompt or "stay" in lower_prompt or "room" in lower_prompt:
            response["content"] = "I'm having trouble accessing hotel information right now. Please try again later or contact customer service for immediate assistance with your accommodation."
        
        elif "cancel" in lower_prompt:
            response["content"] = "If you're trying to cancel a booking, please contact customer service directly at support@travelagent.example.com or call 1-800-TRAVEL."
        
        return response

    @staticmethod
    def fallback_flight_search(origin: str, destination: str, date: str) -> List[Dict[str, Any]]:
        """
        Fallback for when flight search service is unavailable.
        Returns cached or static flight data.
        
        Args:
            origin: Origin location
            destination: Destination location
            date: Travel date
            
        Returns:
            List of basic flight options
        """
        logger.warning(f"Using fallback flight search for {origin} to {destination} on {date}")
        
        # Generate placeholder results
        search_time = datetime.now()
        departure_time = datetime.strptime(date, "%Y-%m-%d").replace(hour=10, minute=0)
        
        # Create a few realistic-looking flights with different times
        flights = [
            {
                "airline": "Fallback Airways",
                "flight_number": f"FB{abs(hash(origin + destination)) % 1000}",
                "origin": origin,
                "destination": destination,
                "departure_date": date,
                "departure_time": (departure_time).strftime("%H:%M"),
                "arrival_time": (departure_time + timedelta(hours=2)).strftime("%H:%M"),
                "price": "$---",
                "currency": "USD",
                "fallback": True,
                "message": "Note: This is estimated data due to service disruption"
            },
            {
                "airline": "Backup Airlines",
                "flight_number": f"BU{abs(hash(destination + origin)) % 1000}",
                "origin": origin,
                "destination": destination,
                "departure_date": date,
                "departure_time": (departure_time + timedelta(hours=4)).strftime("%H:%M"),
                "arrival_time": (departure_time + timedelta(hours=6)).strftime("%H:%M"),
                "price": "$---",
                "currency": "USD",
                "fallback": True,
                "message": "Note: This is estimated data due to service disruption"
            }
        ]
        
        return flights

    @staticmethod
    def fallback_hotel_search(location: str, check_in: str, check_out: str) -> List[Dict[str, Any]]:
        """
        Fallback for when hotel search service is unavailable.
        Returns cached or static hotel data.
        
        Args:
            location: Location to search in
            check_in: Check-in date
            check_out: Check-out date
            
        Returns:
            List of basic hotel options
        """
        logger.warning(f"Using fallback hotel search for {location} from {check_in} to {check_out}")
        
        # Generate placeholder results based on location
        hotels = [
            {
                "name": f"Fallback Hotel {location}",
                "address": f"123 Main St, {location}",
                "rating": "?",
                "price": "$---",
                "currency": "USD",
                "check_in": check_in,
                "check_out": check_out,
                "fallback": True,
                "message": "Note: This is placeholder data due to service disruption"
            },
            {
                "name": f"Backup Resort {location}",
                "address": f"456 Beach Rd, {location}",
                "rating": "?",
                "price": "$---",
                "currency": "USD",
                "check_in": check_in,
                "check_out": check_out,
                "fallback": True,
                "message": "Note: This is placeholder data due to service disruption"
            }
        ]
        
        return hotels

    @staticmethod
    def fallback_parameter_extraction(user_message: str) -> Dict[str, Any]:
        """
        Fallback for when parameter extraction fails.
        Attempts basic pattern matching to extract travel parameters.
        
        Args:
            user_message: User's message
            
        Returns:
            Best-effort parameter extraction
        """
        logger.warning(f"Using fallback parameter extraction for: {user_message}")
        
        parameters = {"fallback": True}
        lower_message = user_message.lower()
        
        # Extremely basic extraction of common patterns using string matching
        # This is a very simplified version and won't handle complex queries well
        
        # Try to determine query type
        if "flight" in lower_message or "fly" in lower_message:
            parameters["query_type"] = "flight"
        elif "hotel" in lower_message or "stay" in lower_message or "room" in lower_message:
            parameters["query_type"] = "hotel"
        
        # Extract dates - very simplistic with regex
        import re
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
            r'(\d{2}/\d{2}/\d{4})',  # MM/DD/YYYY
            r'(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{4})'  # 15 January 2023
        ]
        
        dates = []
        for pattern in date_patterns:
            dates.extend(re.findall(pattern, lower_message, re.IGNORECASE))
        
        if len(dates) >= 1:
            parameters["date"] = dates[0]
        if len(dates) >= 2:
            parameters["return_date"] = dates[1]
        
        # Extract locations - look for common patterns like "from X to Y"
        from_to_pattern = r'from\s+([a-zA-Z\s]+)\s+to\s+([a-zA-Z\s]+)'
        matches = re.findall(from_to_pattern, lower_message)
        if matches:
            parameters["origin"] = matches[0][0].strip()
            parameters["destination"] = matches[0][1].strip()
        
        return parameters

    @staticmethod
    def fallback_redis(operation: str, key: str, value: Any = None) -> Optional[Any]:
        """
        Fallback for when Redis is unavailable.
        Uses temporary file-based storage for critical operations.
        
        Args:
            operation: Redis operation (get, set, delete)
            key: Redis key
            value: Value to set (for set operation)
            
        Returns:
            Stored value for get operations, None otherwise
        """
        logger.warning(f"Using fallback Redis for {operation} on key: {key}")
        
        # Create a temporary cache directory if it doesn't exist
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'temp_cache')
        os.makedirs(cache_dir, exist_ok=True)
        
        # Use the key to create a file path, replacing any special characters
        safe_key = "".join(c if c.isalnum() else "_" for c in key)
        file_path = os.path.join(cache_dir, f"{safe_key}.json")
        
        if operation.lower() == 'get':
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                        return data.get('value')
                return None
            except Exception as e:
                logger.error(f"Fallback Redis get failed: {str(e)}")
                return None
                
        elif operation.lower() == 'set':
            try:
                data = {'value': value, 'timestamp': time.time()}
                with open(file_path, 'w') as f:
                    json.dump(data, f)
                return True
            except Exception as e:
                logger.error(f"Fallback Redis set failed: {str(e)}")
                return None
                
        elif operation.lower() == 'delete':
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                return True
            except Exception as e:
                logger.error(f"Fallback Redis delete failed: {str(e)}")
                return None
                
        return None
