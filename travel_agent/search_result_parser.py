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
        
        # Process ALL organic results to extract flight info
        for i, result in enumerate(search_results.get("organic", [])):
            flight_info = {
                "id": f"flight_{i+1}",
                "origin": origin_name,
                "destination": destination_name,
                "date": date,
                "confidence": 0.8 - (i * 0.05) if i < 15 else 0.1  # Adjusted confidence decay
            }
            
            # Extract title and content to search
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            link = result.get("link", "")
            content = f"{title} {snippet}"
            
            # Always include basic information
            flight_info["title"] = title
            flight_info["snippet"] = snippet
            flight_info["link"] = link
            
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
            
            # Extract stops
            if "Nonstop" in content or "0 stops" in content:
                flight_info["stops"] = 0
            elif "1 stop" in content:
                flight_info["stops"] = 1
            elif "2 stops" in content: # Can add more if needed
                flight_info["stops"] = 2
            else:
                flight_info["stops"] = None # Unknown
            
            # Add website source
            if "expedia" in link.lower():
                flight_info["source"] = "Expedia"
            elif "skyscanner" in link.lower():
                flight_info["source"] = "Skyscanner"
            elif "google" in link.lower():
                flight_info["source"] = "Google Flights"
            elif "kayak" in link.lower():
                flight_info["source"] = "Kayak"
            elif "booking" in link.lower():
                flight_info["source"] = "Booking.com"
            else:
                flight_info["source"] = "Travel Search"
            
            # Add every result to flights list regardless of specific flight info
            flights.append(flight_info)
        
        # Include related searches if present
        if "relatedSearches" in search_results:
            for i, related in enumerate(search_results.get("relatedSearches", [])):
                related_query = related.get("query", "")
                flights.append({
                    "id": f"related_{i+1}",
                    "title": f"Related Search: {related_query}",
                    "query": related_query,
                    "type": "related_search",
                    "origin": origin_name,
                    "destination": destination_name,
                    "date": date,
                    "confidence": 0.5
                })
        
        # Only use synthetic results if we have no results at all
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
        
        # Process ALL organic results
        for i, result in enumerate(search_results.get("organic", [])):
            hotel_info = {
                "id": f"hotel_{i+1}",
                "location": location,
                "check_in": check_in,
                "check_out": check_out,
                "confidence": 0.9 - (i * 0.05) if i < 15 else 0.1  # Adjusted confidence decay
            }
            
            # Extract title and content to search
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            link = result.get("link", "")
            content = f"{title} {snippet}"
            
            # Always include basic information
            hotel_info["title"] = title
            hotel_info["snippet"] = snippet
            hotel_info["link"] = link
            
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
            
            hotels.append(hotel_info)
        
        # Include related searches if present
        if "relatedSearches" in search_results:
            for i, related in enumerate(search_results.get("relatedSearches", [])):
                related_query = related.get("query", "")
                hotels.append({
                    "id": f"related_{i+1}",
                    "title": f"Related Search: {related_query}",
                    "query": related_query,
                    "type": "related_search",
                    "location": location,
                    "check_in": check_in,
                    "check_out": check_out,
                    "confidence": 0.5
                })
        
        # If knowledgeGraph is present, include it
        if "knowledgeGraph" in search_results:
            kg = search_results["knowledgeGraph"]
            hotels.append({
                "id": "knowledge_graph",
                "title": kg.get("title", "Location Information"),
                "type": "knowledge_graph",
                "attributes": kg.get("attributes", {}),
                "location": location,
                "description": kg.get("description", ""),
                "confidence": 0.95
            })
            
        # Only use synthetic results if we have no results at all
        if not hotels and search_results.get("organic"):
            hotels = SearchResultParser._generate_synthetic_hotels(location, check_in, check_out, search_results)
        
        return hotels
    
    @staticmethod
    def extract_activity_details(search_results: Dict[str, Any], location: str) -> List[Dict[str, Any]]:
        """
        Extract activity and attraction details from search results.

        Args:
            search_results: Raw search results from Serper API (expected query like "things to do in [location]")
            location: Activity location (city)

        Returns:
            List of structured activity data objects
        """
        activities = []
        logger.info(f"Attempting to extract activity details for {location}...")

        if not search_results or "organic" not in search_results:
            logger.warning(f"No organic search results found for activities in {location}")
            return activities

        # Basic patterns - These need significant refinement for real-world use
        # Looking for amounts preceded/followed by currency symbols/codes or keywords
        cost_pattern = re.compile(r'(?:SAR|\$|£|€|USD|EGP)\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*(?:SAR|Dollars?|Pounds?|Euros?|EGP|Egyptian Pounds?)|(?:(?:Entry|Ticket)\s*(?:Fee|Price)\s*[:\s\-]?)\s*(?:approx\.\s*)?(?:SAR|\$|£|€|USD|EGP)?\s*(\d+(?:[.,]\d+)?)\b', re.IGNORECASE)
        # Rough currency conversion rates (Example: update these as needed)
        conversion_rates = {
            "USD": 3.75,
            "$": 3.75,
            "EUR": 4.05,
            "€": 4.05,
            "GBP": 4.70,
            "£": 4.70,
            "EGP": 0.08, # Highly variable, example only
            "SAR": 1.0
        }

        for i, result in enumerate(search_results.get("organic", [])):
            activity_info = {
                "id": f"activity_{i+1}",
                "location": location,
                "confidence": 0.7 - (i * 0.05) if i < 10 else 0.2, # Confidence decreases faster for generic results
                "name": result.get("title", "Unknown Activity"),
                "description": result.get("snippet", "No description available."),
                "link": result.get("link", ""),
                "cost_text": None,
                "cost_value_sar": None
            }

            content = f"{activity_info['name']} {activity_info['description']}"

            # Extract Cost (Very basic attempt)
            cost_matches = cost_pattern.findall(content)
            extracted_cost_value = None
            extracted_currency_symbol = None

            if cost_matches:
                 # Find the first non-empty capture group value
                 for match_tuple in cost_matches:
                     for potential_value in match_tuple:
                         if potential_value:
                             try:
                                 # Clean up value (remove commas)
                                 value_str = potential_value.replace(',', '')
                                 extracted_cost_value = float(value_str)
                                 activity_info["cost_text"] = f"Approx. {potential_value}" # Store raw match
                                 # Try to guess currency (extremely basic)
                                 # Look around the found value for currency indicators
                                 idx = content.find(potential_value)
                                 search_window = content[max(0, idx - 10):min(len(content), idx + len(potential_value) + 10)]
                                 
                                 if "SAR" in search_window: extracted_currency_symbol = "SAR"
                                 elif "$" in search_window or "USD" in search_window or "Dollar" in search_window: extracted_currency_symbol = "$"
                                 elif "£" in search_window or "GBP" in search_window or "Pound" in search_window: extracted_currency_symbol = "£"
                                 elif "€" in search_window or "EUR" in search_window or "Euro" in search_window: extracted_currency_symbol = "€"
                                 elif "EGP" in search_window or "Egyptian" in search_window: extracted_currency_symbol = "EGP"
                                 else: extracted_currency_symbol = None # Unknown, assume local maybe?
                                 
                                 if extracted_currency_symbol: # Update text if symbol found
                                    activity_info["cost_text"] = f"Approx. {extracted_currency_symbol}{potential_value}"
                                 else:
                                     activity_info["cost_text"] = f"Approx. {potential_value} (Currency?)"

                                 # Convert to SAR if possible
                                 rate = conversion_rates.get(extracted_currency_symbol, None) if extracted_currency_symbol else None
                                 if rate:
                                     activity_info["cost_value_sar"] = round(extracted_cost_value * rate, 2)
                                 elif extracted_currency_symbol == "SAR":
                                     activity_info["cost_value_sar"] = extracted_cost_value
                                 else:
                                     # If currency unknown, cannot reliably convert
                                     logger.debug(f"Could not determine currency for cost '{potential_value}' in '{content[:100]}...'")


                                 break # Stop after first value found in tuple
                             except ValueError:
                                 logger.warning(f"Could not parse cost value '{potential_value}' as float.")
                                 extracted_cost_value = None # Reset if parsing fails
                     if extracted_cost_value is not None:
                         break # Stop after first match tuple yields a value

            # Improve name/description (basic cleanup)
            # Remove website names often included in titles
            common_sites = [" - TripAdvisor", " - Viator", " - GetYourGuide", " | Visit Saudi", " - Wikipedia"]
            for site in common_sites:
                if activity_info["name"].endswith(site):
                    activity_info["name"] = activity_info["name"][:-len(site)].strip()

            # Basic check if the result seems relevant (contains location name?)
            if location.lower() not in content.lower() and i > 3: # Less strict for top results
                 activity_info["confidence"] *= 0.5 # Lower confidence if location not mentioned

            # Filter out results that are clearly just booking sites or ads unless top results
            if any(site.lower() in activity_info["name"].lower() for site in ["Booking.com", "Expedia", "Agoda", "Hotels.com"]) and i > 2:
                logger.debug(f"Skipping likely booking site result: {activity_info['name']}")
                continue

            logger.debug(f"Extracted activity: {activity_info['name']} - Cost: {activity_info['cost_text']} SAR: {activity_info['cost_value_sar']}")
            activities.append(activity_info)

        logger.info(f"Extracted {len(activities)} potential activities for {location}.")
        return activities

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
        elif query_type.lower() == 'activity':
            # Assuming SearchManager uses 'activity' as query_type for such searches
            return SearchResultParser.extract_activity_details(
                search_results,
                params.get('location', '') # Pass the location parameter
            )
        else:
            # Return the raw results for other types of queries
            logger.info(f"Unknown query type '{query_type}' or type not handled for structured parsing. Returning raw organic results.")
            return search_results.get("organic", [])
