import os
import json
import logging
import time
from typing import Dict, Any, List, Optional
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SearchException(Exception):
    """Base exception class for search-related errors."""
    pass


class RateLimitException(SearchException):
    """Exception raised when search API rate limits are hit."""
    pass


class APIKeyException(SearchException):
    """Exception raised when there are issues with the API key."""
    pass


class SearchRequestException(SearchException):
    """Exception raised for general search request errors."""
    pass


class SearchToolManager:
    """
    Manages search operations through the Google Serper API.
    Handles search queries for travel-related information.
    """
    
    def __init__(self, cache_enabled: bool = True):
        """
        Initialize the search tool manager.
        
        Args:
            cache_enabled: Whether to enable caching of search results
        """
        self.api_key = os.getenv("SERPER_API_KEY")
        if not self.api_key:
            logger.warning("Serper API key not found in environment variables.")
        
        self.base_url = "https://google.serper.dev"
        self.cache_enabled = cache_enabled
        self.cache = {}  # Simple in-memory cache
        self.cache_ttl = 3600  # Cache TTL in seconds (1 hour)
    
    def _generate_cache_key(self, query: str, search_type: str, location: Optional[str]) -> str:
        """Generate a unique key for caching search results."""
        location_str = location if location else "global"
        return f"{query}::{search_type}::{location_str}"
    
    def _is_cache_valid(self, timestamp: float) -> bool:
        """Check if a cached item is still valid based on TTL."""
        return (time.time() - timestamp) < self.cache_ttl
    
    @retry(
        retry=retry_if_exception_type((RateLimitException, requests.exceptions.Timeout, 
                                       requests.exceptions.ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def search(
        self, 
        query: str, 
        search_type: str = 'organic', 
        location: Optional[str] = None,
        num_results: int = 5
    ) -> Dict[str, Any]:
        """
        Perform a search using Google Serper API.
        
        Args:
            query: Search query string
            search_type: Type of search ('organic', 'places', 'images', 'news')
            location: Optional location for geographically relevant results
            num_results: Number of results to return
            
        Returns:
            Dictionary containing search results
            
        Raises:
            RateLimitException: If API rate limits are exceeded
            APIKeyException: If there are issues with the API key
            SearchRequestException: For other request errors
        """
        # Check cache first if enabled
        if self.cache_enabled:
            cache_key = self._generate_cache_key(query, search_type, location)
            if cache_key in self.cache:
                timestamp, cached_data = self.cache[cache_key]
                if self._is_cache_valid(timestamp):
                    logger.info(f"Cache hit for query: {query}")
                    return cached_data
        
        # Proceed with API request if no valid cache found
        if not self.api_key:
            raise APIKeyException("Serper API key not configured")
        
        headers = {
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }
        
        payload = {
            'q': query,
            'num': num_results
        }
        
        if location:
            payload['gl'] = location
        
        # The correct Serper API endpoint is just '/search' (no search type in the path)
        endpoint = "/search"
        url = f"{self.base_url}{endpoint}"
        
        # Add search type as a parameter in the payload if not 'organic'
        if search_type != 'organic':
            payload['type'] = search_type
        
        try:
            start_time = time.time()
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            end_time = time.time()
            
            # Handle HTTP errors
            if response.status_code == 429:
                logger.warning("Serper API rate limit exceeded")
                raise RateLimitException("Search API rate limit exceeded")
            
            elif response.status_code == 401 or response.status_code == 403:
                logger.error("Serper API key invalid or unauthorized")
                raise APIKeyException("Invalid or unauthorized API key")
            
            elif response.status_code != 200:
                logger.error(f"Serper API error: {response.status_code}")
                raise SearchRequestException(f"Search API returned error: {response.status_code}")
            
            # Parse successful response
            result = response.json()
            
            # Add metadata to the result
            result['_metadata'] = {
                'query': query,
                'search_type': search_type,
                'location': location,
                'latency': end_time - start_time,
                'timestamp': time.time()
            }
            
            # Cache the result if caching is enabled
            if self.cache_enabled:
                cache_key = self._generate_cache_key(query, search_type, location)
                self.cache[cache_key] = (time.time(), result)
            
            return result
            
        except (RateLimitException, APIKeyException):
            # Re-raise these specific exceptions to be handled separately
            raise
            
        except requests.exceptions.Timeout:
            logger.warning("Serper API request timed out")
            raise
            
        except requests.exceptions.ConnectionError:
            logger.warning("Connection error when accessing Serper API")
            raise
            
        except Exception as e:
            logger.error(f"Unexpected error in search: {str(e)}")
            raise SearchRequestException(f"Search failed: {str(e)}")
    
    def search_hotels(self, location: str, check_in: Optional[str] = None, 
                     check_out: Optional[str] = None, num_people: int = 2) -> Dict[str, Any]:
        """
        Search for hotels in a specific location.
        
        Args:
            location: Location to search for hotels
            check_in: Check-in date (optional)
            check_out: Check-out date (optional)
            num_people: Number of people (adults)
            
        Returns:
            Search results for hotels
        """
        # Construct a query string that's likely to return relevant hotel results
        query_parts = [f"best hotels in {location}"]
        
        if check_in and check_out:
            query_parts.append(f"from {check_in} to {check_out}")
        
        if num_people > 1:
            query_parts.append(f"for {num_people} people")
        
        query = " ".join(query_parts)
        
        # Use organic search for comprehensive results
        results = self.search(query, search_type='organic')
        
        # Process and structure hotel results
        processed_results = self._process_hotel_results(results, location)
        
        return processed_results
    
    def search_flights(self, origin: str, destination: str, 
                      departure_date: Optional[str] = None, 
                      return_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Search for flights between locations.
        
        Args:
            origin: Origin location
            destination: Destination location
            departure_date: Departure date (optional)
            return_date: Return date (optional)
            
        Returns:
            Search results for flights
        """
        # Construct a query string for flights
        query_parts = [f"flights from {origin} to {destination}"]
        
        if departure_date:
            query_parts.append(f"on {departure_date}")
            
            if return_date:
                query_parts.append(f"return {return_date}")
        
        query = " ".join(query_parts)
        
        # Use organic search for flight results
        results = self.search(query, search_type='organic')
        
        # Process and structure flight results
        processed_results = self._process_flight_results(results, origin, destination)
        
        return processed_results
    
    def search_destination_info(self, destination: str) -> Dict[str, Any]:
        """
        Search for general information about a destination.
        
        Args:
            destination: Destination to get information about
            
        Returns:
            Search results for destination information
        """
        # First query for general information
        general_query = f"travel guide to {destination} things to do attractions"
        general_results = self.search(general_query, search_type='organic')
        
        # Second query for images of the destination
        images_query = f"{destination} travel destination landmarks"
        image_results = self.search(images_query, search_type='images')
        
        # Combine and process results
        combined_results = {
            'general': general_results,
            'images': image_results,
            '_metadata': {
                'destination': destination,
                'timestamp': time.time()
            }
        }
        
        return combined_results
    
    def search_weather(self, location: str, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Search for weather information for a location.
        
        Args:
            location: Location to check weather for
            date: Date to check weather for (optional)
            
        Returns:
            Search results for weather information
        """
        query_parts = [f"weather forecast {location}"]
        
        if date:
            query_parts.append(f"on {date}")
        
        query = " ".join(query_parts)
        
        # Use organic search for weather information
        results = self.search(query, search_type='organic')
        
        # Process and structure weather results
        processed_results = self._process_weather_results(results, location)
        
        return processed_results
    
    def search_visa_requirements(self, from_country: str, to_country: str) -> Dict[str, Any]:
        """
        Search for visa requirements between countries.
        
        Args:
            from_country: Origin country
            to_country: Destination country
            
        Returns:
            Search results for visa requirements
        """
        query = f"visa requirements for {from_country} citizens traveling to {to_country}"
        
        # Use organic search for visa information
        results = self.search(query, search_type='organic')
        
        # Process and structure visa results
        processed_results = self._process_visa_results(results, from_country, to_country)
        
        return processed_results
    
    def _process_hotel_results(self, results: Dict[str, Any], location: str) -> Dict[str, Any]:
        """Process and structure hotel search results."""
        processed = {
            'query_location': location,
            'hotels': [],
            'meta_information': {}
        }
        
        # Extract organic results if available
        if 'organic' in results:
            for item in results['organic'][:5]:  # Limit to top 5 results
                hotel = {
                    'name': item.get('title', '').replace(' - Booking.com', '').replace(' | Hotels.com', ''),
                    'description': item.get('snippet', ''),
                    'link': item.get('link', ''),
                    'source': self._extract_domain(item.get('link', '')),
                }
                
                # Add thumbnail if available
                if 'thumbnail' in item:
                    hotel['image_url'] = item['thumbnail']
                
                processed['hotels'].append(hotel)
        
        # Extract any relevant knowledge graph information
        if 'knowledgeGraph' in results:
            kg = results['knowledgeGraph']
            processed['meta_information']['location_info'] = {
                'title': kg.get('title', ''),
                'type': kg.get('type', ''),
                'description': kg.get('description', ''),
                'image_url': kg.get('thumbnail', '')
            }
        
        return processed
    
    def _process_flight_results(self, results: Dict[str, Any], 
                              origin: str, destination: str) -> Dict[str, Any]:
        """Process and structure flight search results."""
        processed = {
            'origin': origin,
            'destination': destination,
            'flights': [],
            'providers': []
        }
        
        # Extract organic results if available
        if 'organic' in results:
            # Process flight options
            for item in results['organic'][:5]:  # Limit to top 5 results
                # Skip results that don't seem flight-related
                title = item.get('title', '').lower()
                if not any(kw in title for kw in ['flight', 'air', 'book', 'cheap']):
                    continue
                    
                flight = {
                    'title': item.get('title', ''),
                    'description': item.get('snippet', ''),
                    'link': item.get('link', ''),
                    'source': self._extract_domain(item.get('link', '')),
                }
                
                processed['flights'].append(flight)
            
            # Extract flight booking providers
            providers = set()
            for item in results['organic']:
                domain = self._extract_domain(item.get('link', ''))
                if domain and any(kw in domain for kw in ['expedia', 'kayak', 'booking', 'skyscanner', 
                                                         'trip', 'flight', 'air']):
                    providers.add(domain)
            
            processed['providers'] = list(providers)
        
        return processed
    
    def _process_weather_results(self, results: Dict[str, Any], location: str) -> Dict[str, Any]:
        """Process and structure weather search results."""
        processed = {
            'location': location,
            'weather_info': None,
            'forecast': []
        }
        
        # Extract weather answer box if present
        if 'answerBox' in results:
            answer = results['answerBox']
            
            # Try to extract structured weather data
            if 'answer' in answer:
                processed['weather_info'] = answer['answer']
            
            if 'snippet' in answer:
                processed['weather_info'] = answer['snippet']
        
        # Extract organic results that might contain forecast information
        if 'organic' in results:
            for item in results['organic'][:3]:  # Limit to top 3 results
                if any(kw in item.get('title', '').lower() for kw in ['weather', 'forecast', 'temperature']):
                    forecast_item = {
                        'title': item.get('title', ''),
                        'description': item.get('snippet', ''),
                        'link': item.get('link', ''),
                        'source': self._extract_domain(item.get('link', '')),
                    }
                    processed['forecast'].append(forecast_item)
        
        return processed
    
    def _process_visa_results(self, results: Dict[str, Any], 
                             from_country: str, to_country: str) -> Dict[str, Any]:
        """Process and structure visa requirement search results."""
        processed = {
            'from_country': from_country,
            'to_country': to_country,
            'visa_info': None,
            'requirements': [],
            'official_sources': []
        }
        
        # Extract answer box if present
        if 'answerBox' in results:
            answer = results['answerBox']
            if 'answer' in answer:
                processed['visa_info'] = answer['answer']
            elif 'snippet' in answer:
                processed['visa_info'] = answer['snippet']
        
        # Extract organic results
        if 'organic' in results:
            # Process potential requirements information
            for item in results['organic'][:5]:
                source = self._extract_domain(item.get('link', ''))
                
                # Categorize the result
                if any(kw in source for kw in ['gov', 'embassy', 'official', 'ministry']):
                    processed['official_sources'].append({
                        'title': item.get('title', ''),
                        'description': item.get('snippet', ''),
                        'link': item.get('link', ''),
                        'source': source
                    })
                else:
                    processed['requirements'].append({
                        'title': item.get('title', ''),
                        'description': item.get('snippet', ''),
                        'link': item.get('link', ''),
                        'source': source
                    })
        
        return processed
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain name from URL."""
        if not url:
            return ""
        
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            # Remove 'www.' if present
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            # Fallback to simple splitting if parsing fails
            try:
                domain = url.split('//')[1].split('/')[0]
                if domain.startswith('www.'):
                    domain = domain[4:]
                return domain
            except:
                return ""
