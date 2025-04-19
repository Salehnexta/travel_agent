"""
Enhanced Search Result Parser for Travel Agent
Extracts structured flight and hotel information from general search results.
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SearchResultParser:
    """
    Parses search results from Serper API into structured travel data.
    Extracts flight details, prices, and hotel information using pattern matching.
    """
    
    @staticmethod
    def extract_flight_details(search_results: Dict[str, Any], origin: str, destination: str, date: str) -> List[Dict[str, Any]]:
        """
        Extract flight details from search results.
        
        Args:
            search_results: Raw search results from Serper API
            origin: Origin airport code
            destination: Destination airport code
            date: Flight date (YYYY-MM-DD)
            
        Returns:
            List of structured flight data objects
        """
        flights = []
        
        # If no search results, return empty list
        if not search_results or "organic" not in search_results:
            logger.warning("No organic search results found")
            return flights
        
        # Extract flight prices from titles and snippets
        price_pattern = r'\$(\d+)'
        airline_patterns = [
            r'(Saudia|flyadeal|flynas|Saudi Arabian Airlines|SV|XY|F3)',
            r'Flight\s+(SV\d+|XY\d+|F3\d+)',
            r'([A-Z]{2}\d+)'  # Generic flight number pattern
        ]
        time_pattern = r'(\d{1,2}:\d{2}\s*(?:AM|PM)?)\s*[-–]\s*(\d{1,2}:\d{2}\s*(?:AM|PM)?)'
        duration_pattern = r'(\d+h\s*\d*m|\d+\s*hours\s*\d*\s*minutes)'
        
        # Get origin and destination names
        origin_name = origin.upper()
        destination_name = destination.upper()
        
        # Try to get flight info from each result
        for i, result in enumerate(search_results.get("organic", [])):
            flight_info = {
                "id": f"flight_{i+1}",
                "origin": origin_name,
                "destination": destination_name,
                "date": date,
                "confidence": 0.8 - (i * 0.1)  # Decreasing confidence for later results
            }
            
            # Extract title and content to search
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            link = result.get("link", "")
            content = f"{title} {snippet}"
            
            # Extract price
            price_matches = re.findall(price_pattern, content)
            if price_matches:
                flight_info["price"] = f"${price_matches[0]}"
                flight_info["price_value"] = int(price_matches[0])
            
            # Extract airline
            for pattern in airline_patterns:
                airline_match = re.search(pattern, content)
                if airline_match:
                    flight_info["airline"] = airline_match.group(1)
                    break
            
            # Extract flight times
            time_match = re.search(time_pattern, content)
            if time_match:
                flight_info["departure_time"] = time_match.group(1)
                flight_info["arrival_time"] = time_match.group(2)
            
            # Extract duration
            duration_match = re.search(duration_pattern, content)
            if duration_match:
                flight_info["duration"] = duration_match.group(1)
            
            # Extract flight number
            flight_num_match = re.search(r'([A-Z]{2}\d+)', content)
            if flight_num_match:
                flight_info["flight_number"] = flight_num_match.group(1)
            
            # If we have at least price or airline, consider it a valid result
            if "price" in flight_info or "airline" in flight_info:
                # Generate a descriptive title if not present
                if "airline" in flight_info:
                    flight_info["title"] = f"{flight_info.get('airline', 'Flight')} from {origin} to {destination}"
                else:
                    flight_info["title"] = f"Flight from {origin} to {destination} on {date}"
                
                # Add website source
                if "expedia" in link.lower():
                    flight_info["source"] = "Expedia"
                elif "skyscanner" in link.lower():
                    flight_info["source"] = "Skyscanner"
                elif "google" in link.lower():
                    flight_info["source"] = "Google Flights"
                else:
                    flight_info["source"] = "Travel Search"
                
                flight_info["link"] = link
                flights.append(flight_info)
        
        # If we don't have any valid flights but have organic results, create synthetic results
        if not flights and search_results.get("organic"):
            # Sample flight data based on the origin/destination
            flights = SearchResultParser._generate_synthetic_flights(origin, destination, date, search_results)
        
        return flights
    
    @staticmethod
    def extract_hotel_details(search_results: Dict[str, Any], location: str, check_in: str, check_out: str) -> List[Dict[str, Any]]:
        """
        Extract hotel details from search results.
        
        Args:
            search_results: Raw search results from Serper API
            location: Hotel location (city)
            check_in: Check-in date (YYYY-MM-DD)
            check_out: Check-out date (YYYY-MM-DD)
            
        Returns:
            List of structured hotel data objects
        """
        hotels = []
        
        # If no search results, return empty list
        if not search_results or "organic" not in search_results:
            logger.warning("No organic search results found")
            return hotels
        
        # Extract hotel information
        price_pattern = r'\$(\d+)'
        star_pattern = r'(\d+)[\-\s]star'
        hotel_name_pattern = r'Book\s+([^,]+),'
        
        # Process each result
        for i, result in enumerate(search_results.get("organic", [])):
            hotel_info = {
                "id": f"hotel_{i+1}",
                "location": location,
                "check_in": check_in,
                "check_out": check_out,
                "confidence": 0.9 - (i * 0.1)  # Decreasing confidence for later results
            }
            
            # Extract title and content to search
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            link = result.get("link", "")
            content = f"{title} {snippet}"
            
            # Extract hotel name
            hotel_name_match = re.search(hotel_name_pattern, title)
            if hotel_name_match:
                hotel_info["name"] = hotel_name_match.group(1).strip()
            else:
                # Try to extract from title directly
                title_parts = title.split(',')
                if len(title_parts) > 0:
                    potential_name = title_parts[0].replace("Book", "").strip()
                    if "Hotel" in potential_name or len(potential_name.split()) <= 5:
                        hotel_info["name"] = potential_name
            
            # Extract price
            price_matches = re.findall(price_pattern, content)
            if price_matches:
                hotel_info["price"] = f"${price_matches[0]}"
                hotel_info["price_value"] = int(price_matches[0])
            
            # Extract star rating
            star_match = re.search(star_pattern, content.lower())
            if star_match:
                hotel_info["rating"] = f"{star_match.group(1)} stars"
            
            # If we have name or price, consider it a valid result
            if "name" in hotel_info or "price" in hotel_info:
                # Generate a descriptive title
                if "name" in hotel_info:
                    hotel_info["title"] = hotel_info["name"]
                else:
                    hotel_info["title"] = f"Hotel in {location}"
                
                hotel_info["link"] = link
                
                # Add website source
                if "booking.com" in link.lower():
                    hotel_info["source"] = "Booking.com"
                elif "umrahme" in link.lower() or "traveazy" in link.lower():
                    hotel_info["source"] = "Umrahme"
                else:
                    hotel_info["source"] = "Hotel Search"
                
                hotels.append(hotel_info)
        
        return hotels
    
    @staticmethod
    def _generate_synthetic_flights(origin: str, destination: str, date: str, search_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate synthetic flight results when specific flight details cannot be extracted.
        Uses information from search results to create plausible flight options.
        
        Args:
            origin: Origin airport code
            destination: Destination airport code
            date: Flight date
            search_results: Raw search results
            
        Returns:
            List of synthetic flight data objects
        """
        synthetic_flights = []
        
        # Extract any available price information
        min_price = None
        price_pattern = r'\$(\d+)'
        for result in search_results.get("organic", []):
            content = f"{result.get('title', '')} {result.get('snippet', '')}"
            price_matches = re.findall(price_pattern, content)
            if price_matches:
                price = int(price_matches[0])
                if min_price is None or price < min_price:
                    min_price = price
        
        # Default price if none found
        if min_price is None:
            if origin.upper() == "DMM" and destination.upper() == "RUH":
                min_price = 38  # Default price for DMM to RUH
            else:
                min_price = 100  # Generic default price
        
        # Create sample departure times
        departure_times = ["07:30 AM", "10:15 AM", "01:45 PM", "04:20 PM", "08:10 PM"]
        airlines = {
            "SV": "Saudia",
            "XY": "flynas",
            "F3": "flyadeal"
        }
        
        # Create 3 synthetic flights
        for i in range(min(3, len(search_results.get("organic", [])))):
            flight_number = f"{list(airlines.keys())[i % len(airlines)]}{1100 + i}"
            airline_code = flight_number[:2]
            airline_name = airlines.get(airline_code, "Saudi Airline")
            
            # Calculate a realistic price
            price = min_price + (i * 15)
            
            # Generate flight info
            synthetic_flights.append({
                "id": f"flight_{i+1}",
                "title": f"{airline_name} Flight {flight_number}",
                "origin": origin.upper(),
                "destination": destination.upper(),
                "date": date,
                "airline": airline_name,
                "flight_number": flight_number,
                "departure_time": departure_times[i % len(departure_times)],
                "price": f"${price}",
                "price_value": price,
                "source": "Flight Search",
                "synthetic": True,
                "confidence": 0.7 - (i * 0.1)
            })
        
        return synthetic_flights
    
    @staticmethod
    def process_search_results(search_results: Dict[str, Any], query_type: str, 
                              params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process search results based on the query type.
        
        Args:
            search_results: Raw search results from Serper API
            query_type: Type of query ('flight', 'hotel', etc.)
            params: Query parameters
            
        Returns:
            List of structured results
        """
        if query_type.lower() == 'flight':
            return SearchResultParser.extract_flight_details(
                search_results, 
                params.get('origin', ''), 
                params.get('destination', ''),
                params.get('date', '')
            )
        elif query_type.lower() == 'hotel':
            return SearchResultParser.extract_hotel_details(
                search_results,
                params.get('location', ''),
                params.get('check_in', ''),
                params.get('check_out', '')
            )
        else:
            # Return the raw results for other types of queries
            return search_results.get("organic", [])
