import os
import json
import time
import logging
import redis
import hashlib
import concurrent.futures
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure Redis connection
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
redis_client = redis.from_url(
    redis_url,
    socket_timeout=10,  # Faster timeout for cache operations
    socket_connect_timeout=5,
    retry_on_timeout=True
)


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
        self.cache_ttl = 86400  # Cache TTL in seconds (24 hours)
        self.session = requests.Session()  # Persistent session for connection pooling
        
        # Configure session for better performance
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=3
        )
        self.session.mount('https://', adapter)
    
    def _generate_cache_key(self, query: str, search_type: str, location: Optional[str]) -> str:
        """Generate a unique key for caching search results."""
        location_str = location if location else "global"
        # Create a hash of the query parameters for shorter keys
        combined = f"{query}::{search_type}::{location_str}"
        return f"search:{hashlib.md5(combined.encode()).hexdigest()}"
        
    def _find_similar_query_cache(self, query: str, search_type: str, location: Optional[str]) -> Optional[Dict]:
        """Find cached results for similar queries to reduce API calls."""
        if not self.cache_enabled:
            return None
            
        try:
            # Get all search cache keys
            search_keys = redis_client.keys("search:*")
            
            # Clean the query for comparison (lowercase, remove extra spaces)
            clean_query = " ".join(query.lower().split())
            
            # Extract key terms from the query
            query_terms = set(clean_query.split())
            key_terms = {word for word in query_terms if len(word) > 3 and word not in {
                "from", "to", "the", "and", "for", "with", "this", "that", "what", "when", "where", "how", "flight", "hotel"
            }}
            
            for key in search_keys:
                # Get the cached data
                cached_data = redis_client.get(key)
                if not cached_data:
                    continue
                    
                try:
                    data = json.loads(cached_data)
                    # Check if this is a relevant cache entry
                    if "query" in data and search_type in data.get("type", ""):
                        cached_query = data["query"].lower()
                        
                        # Check for significant term overlap
                        cached_terms = set(cached_query.split())
                        key_cached_terms = {word for word in cached_terms if len(word) > 3}
                        
                        # If there's significant overlap in key terms, use this cache
                        overlap = key_terms.intersection(key_cached_terms)
                        if len(overlap) >= min(2, len(key_terms)):
                            logger.info(f"Found similar query cache: {data['query']} for query: {query}")
                            return data
                except:
                    continue
                    
            return None
        except Exception as e:
            logger.warning(f"Error finding similar query cache: {str(e)}")
            return None
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict]:
        """Get results from Redis cache if they exist and are valid."""
        if not self.cache_enabled:
            return None
            
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                logger.info(f"Cache hit for key: {cache_key}")
                return json.loads(cached_data)
            return None
        except Exception as e:
            logger.warning(f"Error accessing cache: {str(e)}")
            return None
            
    def _save_to_cache(self, cache_key: str, data: Dict) -> None:
        """Save results to Redis cache with TTL."""
        if not self.cache_enabled:
            return
            
        try:
            redis_client.setex(cache_key, self.cache_ttl, json.dumps(data))
            logger.info(f"Saved to cache: {cache_key}")
        except Exception as e:
            logger.warning(f"Error saving to cache: {str(e)}")
    
    @retry(
        retry=retry_if_exception_type((RateLimitException, requests.exceptions.Timeout, 
                                       requests.exceptions.ConnectionError)),
        stop=stop_after_attempt(5),  # Increase max retry attempts
        wait=wait_exponential(multiplier=2, min=4, max=60)  # More aggressive backoff strategy
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
        # Generate cache key
        cache_key = self._generate_cache_key(query, search_type, location)
        
        # Check Redis cache first if enabled
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result
            
        # Try to find similar query in cache
        similar_result = self._find_similar_query_cache(query, search_type, location)
        if similar_result:
            # Save this result under the current query's cache key for future direct hits
            self._save_to_cache(cache_key, similar_result)
            return similar_result
            
        # Check rate limiting before making API call
        rate_limit_key = "serper_api_rate_limit"
        current_hour = datetime.now().strftime("%Y-%m-%d-%H")
        hourly_key = f"{rate_limit_key}:{current_hour}"
        
        # Get current count of API calls this hour
        try:
            call_count = redis_client.get(hourly_key)
            call_count = int(call_count) if call_count else 0
            
            # If we're approaching the limit (20 per hour), wait longer between calls
            if call_count >= 15:
                logger.warning(f"Approaching rate limit: {call_count}/20 calls this hour")
                time.sleep(5)  # Add delay to spread out requests
                
            # If we're at or over the limit, raise exception to trigger retry with backoff
            if call_count >= 19:
                logger.error(f"Rate limit reached: {call_count}/20 calls this hour")
                raise RateLimitException("Serper API rate limit reached for this hour")
        except Exception as e:
            logger.warning(f"Error checking rate limits: {str(e)}")
            # Continue with the request even if rate limit checking fails
        
        # Proceed with API request if no valid cache found
        if not self.api_key:
            raise APIKeyException("Serper API key not configured")
        
        headers = {
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }
        
        payload = {
            'q': query,
            'gl': 'us',  # Geolocation parameter - could be dynamically set
            'hl': 'en',  # Language parameter
            'autocorrect': True,
            'num': min(num_results, 10)  # Limit number of results to improve speed
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
            response = self.session.post(
                f"{self.base_url}{endpoint}", 
                headers=headers, 
                json=payload,
                timeout=5  # Reduced timeout for faster API requests
            )
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
            
            # Cache the successful result in Redis
            self._save_to_cache(cache_key, result)
            
            # Increment the API call counter for rate limiting
            try:
                # Increment counter and set expiry to ensure it resets after the hour
                redis_client.incr(hourly_key)
                redis_client.expire(hourly_key, 3600)  # Expire after 1 hour
                
                # Log current usage
                new_count = redis_client.get(hourly_key)
                new_count = int(new_count) if new_count else 1
                logger.info(f"Serper API usage: {new_count}/20 calls this hour")
                
                # If we're getting close to the limit, increase cache TTL to reduce future calls
                if new_count >= 15:
                    self.cache_ttl = 172800  # 48 hours when approaching limits
            except Exception as e:
                logger.warning(f"Error updating rate limit counter: {str(e)}")
            
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
    
    def search_parallel(self, queries: List[Dict]) -> List[Dict[str, Any]]:
        """
        Perform multiple search queries in parallel using threading.
        
        Args:
            queries: List of query dictionaries, each containing query parameters
                    (query, search_type, location, num_results)
                    
        Returns:
            List of search result dictionaries
        """
        results = []
        
        # Use ThreadPoolExecutor for parallel execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all search tasks
            future_to_query = {}
            for query_params in queries:
                future = executor.submit(
                    self.search,
                    query=query_params.get('query', ''),
                    search_type=query_params.get('search_type', 'organic'),
                    location=query_params.get('location'),
                    num_results=query_params.get('num_results', 5)
                )
                future_to_query[future] = query_params
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_query):
                query_params = future_to_query[future]
                try:
                    result = future.result()
                    results.append({
                        'query': query_params,
                        'result': result
                    })
                except Exception as e:
                    logger.error(f"Error in parallel search: {str(e)}")
                    results.append({
                        'query': query_params,
                        'error': str(e)
                    })
        
        return results
    
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
        # Map common airport codes to city names for better search results
        airport_to_city = {
            "BKK": "Bangkok",
            "DMM": "Dammam",
            "JED": "Jeddah",
            "RUH": "Riyadh",
            "DXB": "Dubai",
            "AUH": "Abu Dhabi",
            "DOH": "Doha",
            "CAI": "Cairo",
            "NYC": "New York City",
            "LAX": "Los Angeles",
            "LHR": "London",
            "CDG": "Paris"
        }
        
        # Check if the location is an airport code and map to city if needed
        search_location = location
        if location.upper() in airport_to_city:
            search_location = airport_to_city[location.upper()]
            logger.info(f"Mapped airport code {location} to city {search_location} for hotel search")
        
        # Construct a query string that's likely to return relevant hotel results
        query_parts = [f"best hotels in {search_location}"]
        
        if check_in and check_out:
            query_parts.append(f"from {check_in} to {check_out}")
        elif check_in:  # If only check-in is provided (common for "tomorrow" queries)
            query_parts.append(f"available on {check_in}")
        
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
                      return_date: Optional[str] = None,
                      num_passengers: int = 1,
                      time_preference: Optional[str] = None) -> Dict[str, Any]:
        """
        Search for flights between locations.
        
        Args:
            origin: Origin location
            destination: Destination location
            departure_date: Departure date (optional)
            return_date: Return date (optional)
            time_preference: Time of day preference (e.g., 'morning', 'afternoon', 'evening')
            
        Returns:
            Search results for flights
        """
        # Construct a query string for flights
        query_parts = [f"flights from {origin} to {destination}"]
        
        if departure_date:
            query_parts.append(f"on {departure_date}")
            
            if return_date:
                query_parts.append(f"return {return_date}")
        
        # Add time preference if provided
        if time_preference:
            query_parts.append(f"{time_preference} flights")
        
        query = " ".join(query_parts)
        
        # Use organic search for flight results
        results = self.search(query, search_type='organic', num_results=10)  # Increased to get more options
        
        # Process and structure flight results
        processed_results = self._process_flight_results(results, origin, destination)
        
        # Add search parameters to metadata
        processed_results['_query_params'] = {
            'origin': origin,
            'destination': destination,
            'departure_date': departure_date,
            'return_date': return_date,
            'time_preference': time_preference
        }
        
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
            'flight_times': [],
            'airlines': [],
            'prices': {},
            'providers': []
        }
        
        # Extract organic results if available
        if 'organic' in results:
            # Process flight options
            for item in results['organic'][:10]:  # Increased limit to get more options
                # Skip results that don't seem flight-related
                title = item.get('title', '').lower()
                snippet = item.get('snippet', '').lower()
                
                if not any(kw in title for kw in ['flight', 'air', 'book', 'cheap', 'ticket']):
                    continue
                    
                flight = {
                    'title': item.get('title', ''),
                    'description': item.get('snippet', ''),
                    'link': item.get('link', ''),
                    'source': self._extract_domain(item.get('link', '')),
                }
                
                # Extract departure times if available
                times = self._extract_flight_times(title, snippet)
                if times:
                    flight['departure_time'] = times.get('departure')
                    flight['arrival_time'] = times.get('arrival')
                
                # Extract airline if available
                airline = self._extract_airline(title, snippet)
                if airline:
                    flight['airline'] = airline
                    if airline not in processed['airlines']:
                        processed['airlines'].append(airline)
                
                # Extract flight number if available
                flight_number = self._extract_flight_number(title, snippet)
                if flight_number:
                    flight['flight_number'] = flight_number
                
                # Extract duration if available
                duration = self._extract_duration(title, snippet)
                if duration:
                    flight['duration'] = duration
                
                # Extract price if available
                price = self._extract_price(title, snippet)
                if price:
                    flight['price'] = price
                    
                processed['flights'].append(flight)
                
                # Add to flight_times if we have departure info
                if times and times.get('departure'):
                    time_info = {
                        'departure': times.get('departure'),
                        'arrival': times.get('arrival'),
                        'airline': airline,
                        'flight_number': flight_number
                    }
                    processed['flight_times'].append(time_info)
            
            # Extract flight booking providers
            providers = set()
            for item in results['organic']:
                domain = self._extract_domain(item.get('link', ''))
                if domain and any(kw in domain for kw in ['expedia', 'kayak', 'booking', 'skyscanner', 
                                                         'trip', 'flight', 'air', 'airlines']):
                    providers.add(domain)
            
            processed['providers'] = list(providers)
            
            # Extract price information from specific sites
            price_info = self._extract_price_info(results['organic'])
            if price_info:
                processed['prices'] = price_info
        
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
    
    def _extract_flight_times(self, title: str, description: str) -> Dict[str, str]:
        """Extract departure and arrival times from flight information."""
        import re
        times = {}
        
        # Combined text to search through
        text = f"{title} {description}".lower()
        
        # Common time patterns (both 12h and 24h formats)
        time_patterns = [
            r'depart\w*\s+(?:at\s+)?(\d{1,2}:\d{2}\s*(?:am|pm)?)',  # departs at 10:30am
            r'departure\s+(?:at\s+)?(\d{1,2}:\d{2}\s*(?:am|pm)?)',    # departure at 10:30am
            r'leaves?\s+(?:at\s+)?(\d{1,2}:\d{2}\s*(?:am|pm)?)',     # leaves at 10:30am
            r'(\d{1,2}:\d{2}\s*(?:am|pm)?)\s+to\s+(\d{1,2}:\d{2}\s*(?:am|pm)?)',  # 10:30am to 12:45pm
            r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s*[-–—]\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))'  # 10:30am-12:45pm
        ]
        
        # Look for departure time
        for pattern in time_patterns:
            matches = re.search(pattern, text, re.IGNORECASE)
            if matches:
                if len(matches.groups()) == 1:
                    times['departure'] = matches.group(1).strip()
                elif len(matches.groups()) == 2:
                    times['departure'] = matches.group(1).strip()
                    times['arrival'] = matches.group(2).strip()
                break
        
        # Look for morning/afternoon/evening specifications if no specific time
        if not times:
            if 'morning' in text:
                times['departure'] = 'morning flight'
            elif 'afternoon' in text:
                times['departure'] = 'afternoon flight'
            elif 'evening' in text or 'night' in text:
                times['departure'] = 'evening flight'
        
        return times
    
    def _extract_airline(self, title: str, description: str) -> Optional[str]:
        """Extract airline name from flight information."""
        # Common airlines to look for
        airlines = [
            'Emirates', 'Qatar Airways', 'Etihad', 'Saudia', 'Flynas', 'Flyadeal',
            'Turkish Airlines', 'Pegasus', 'EgyptAir', 'Air Arabia', 'Gulf Air',
            'Royal Jordanian', 'Middle East Airlines', 'Oman Air', 'Kuwait Airways',
            'American', 'Delta', 'United', 'Southwest', 'JetBlue', 'British Airways',
            'Lufthansa', 'Air France', 'KLM', 'Iberia', 'Ryanair', 'easyJet',
            'Air Canada', 'Singapore Airlines', 'Cathay Pacific', 'ANA', 'JAL'
        ]
        
        # Combined text to search through
        text = f"{title} {description}"
        
        # Check for each airline
        for airline in airlines:
            if airline.lower() in text.lower():
                return airline
            # Check for abbreviations
            abbr = ''.join([word[0] for word in airline.split() if word])
            if len(abbr) > 1 and abbr.upper() in text.upper():
                return airline
        
        return None
    
    def _extract_flight_number(self, title: str, description: str) -> Optional[str]:
        """Extract flight number from flight information."""
        import re
        
        # Combined text to search through
        text = f"{title} {description}"
        
        # Common flight number patterns
        patterns = [
            r'flight\s+(?:number\s+)?([A-Z]{2}\d{1,4})',  # Flight EK123
            r'([A-Z]{2})\s*(\d{1,4})\s+flight',           # EK 123 flight
            r'flight\s+(?:number\s+)?(\d{1,4})'           # Flight 123
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Handle different group configurations
                if len(match.groups()) == 1:
                    return match.group(1).strip()
                elif len(match.groups()) == 2:
                    return f"{match.group(1)}{match.group(2)}".strip()
        
        return None
    
    def _extract_duration(self, title: str, description: str) -> Optional[str]:
        """Extract flight duration from flight information."""
        import re
        
        # Combined text to search through
        text = f"{title} {description}".lower()
        
        # Duration patterns
        patterns = [
            r'(?:flight|duration|time)\s+(?:of\s+)?(\d+\s*h(?:ours?)?(?:\s*and\s*|\s*)?\d*\s*m(?:inutes?)?)',  # flight time of 2h 30m
            r'(\d+\s*h(?:ours?)?(?:\s*and\s*|\s*)?\d*\s*m(?:inutes?)?)\s+(?:flight|duration|time)',  # 2h 30m flight time
            r'(\d+\s*hours?(?:\s*and\s*|\s*)?\d*\s*minutes?)',  # 2 hours and 30 minutes
            r'(?:takes|duration|time)\s+(?:of\s+)?(\d+:\d{2})'  # takes 2:30
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_price(self, title: str, description: str) -> Optional[str]:
        """Extract price information from flight details."""
        import re
        
        # Combined text to search through
        text = f"{title} {description}".lower()
        
        # Price patterns
        patterns = [
            r'\$\s*(\d+(?:,\d+)*(?:\.\d+)?)',  # $123 or $1,234.56
            r'(\d+(?:,\d+)*(?:\.\d+)?)\s*usd',  # 123 USD or 1,234.56 USD
            r'(?:price|cost|fare)\s*(?:from|:)?\s*\$\s*(\d+(?:,\d+)*(?:\.\d+)?)',  # price from $123
            r'(?:price|cost|fare)\s*(?:from|:)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*usd',  # price from 123 USD
            r'(?:price|cost|fare)\s*(?:from|:)?\s*(?:USD|\$)?\s*(\d+(?:,\d+)*(?:\.\d+)?)'  # price from 123
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                price = match.group(1).strip()
                return f"${price}" if not price.startswith('$') else price
        
        return None
    
    def _extract_price_info(self, organic_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract detailed price information from search results."""
        price_info = {
            'lowest_price': None,
            'one_way': None,
            'round_trip': None,
            'by_provider': {}
        }
        
        for item in organic_results:
            title = item.get('title', '').lower()
            snippet = item.get('snippet', '').lower()
            text = f"{title} {snippet}"
            
            # Skip non-price related entries
            if not any(term in text for term in ['price', 'cost', '$', 'usd', 'fare']):
                continue
                
            # Extract provider
            provider = self._extract_domain(item.get('link', ''))
            
            # Extract price with context
            import re
            price_matches = re.findall(r'\$\s*(\d+(?:,\d+)*(?:\.\d+)?)', text)
            
            if price_matches:
                # Convert first found price to float for comparison
                try:
                    price_value = float(price_matches[0].replace(',', ''))
                    
                    # Update lowest price if this is the first or a lower price
                    if price_info['lowest_price'] is None or price_value < price_info['lowest_price']:
                        price_info['lowest_price'] = price_value
                    
                    # Check context for one-way vs round-trip
                    if 'one way' in text or 'one-way' in text:
                        if price_info['one_way'] is None or price_value < price_info['one_way']:
                            price_info['one_way'] = price_value
                    elif 'round trip' in text or 'round-trip' in text or 'return' in text:
                        if price_info['round_trip'] is None or price_value < price_info['round_trip']:
                            price_info['round_trip'] = price_value
                    
                    # Add to provider-specific pricing
                    if provider:
                        if provider not in price_info['by_provider']:
                            price_info['by_provider'][provider] = price_value
                        elif price_value < price_info['by_provider'][provider]:
                            price_info['by_provider'][provider] = price_value
                            
                except ValueError:
                    pass  # Skip if price can't be converted to float
        
        # Convert all prices back to formatted strings
        if price_info['lowest_price'] is not None:
            price_info['lowest_price'] = f"${price_info['lowest_price']:.2f}"
        if price_info['one_way'] is not None:
            price_info['one_way'] = f"${price_info['one_way']:.2f}"
        if price_info['round_trip'] is not None:
            price_info['round_trip'] = f"${price_info['round_trip']:.2f}"
            
        for provider in price_info['by_provider']:
            price_info['by_provider'][provider] = f"${price_info['by_provider'][provider]:.2f}"
        
        return price_info
