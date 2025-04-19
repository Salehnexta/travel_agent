import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from travel_agent.state_definitions import TravelState, ConversationStage, SearchResult
from travel_agent.search_tools import SearchToolManager
from travel_agent.search_result_parser import SearchResultParser

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SearchManager:
    """
    Manages search operations for travel-related information.
    Coordinates with external APIs via the SearchToolManager.
    """
    
    def __init__(self):
        """Initialize the search manager with search tools."""
        self.search_tools = SearchToolManager()
        logger.info("Search Manager initialized")
    
    def process(self, state: TravelState) -> TravelState:
        """
        Process the search request based on the current state.
        
        Args:
            state: The current TravelState
            
        Returns:
            Updated TravelState with search results
        """
        # Check if we have the minimum required parameters
        if not state.has_minimum_parameters():
            logger.warning("Cannot execute search: missing required parameters")
            return state
        
        try:
            # Get primary destination and dates
            destination = state.get_primary_destination()
            dates = state.get_primary_date_range()
            
            if not destination:
                logger.warning("Cannot execute search: no destination found")
                return state
            
            # First, get destination information
            destination_info = self._search_destination_info(destination.name)
            if destination_info:
                destination_result = SearchResult(
                    type="destination",
                    source="serper",
                    data=destination_info
                )
                state.add_search_result(destination_result)
            
            # Check for specific search intents in recent messages
            user_query = state.get_latest_user_query()
            
            if any(term in user_query.lower() for term in ["hotel", "stay", "accommodation", "room"]):
                # Search for hotels
                self._search_hotels(state)
            
            elif any(term in user_query.lower() for term in ["flight", "fly", "airline", "plane"]):
                # Search for flights
                self._search_flights(state)
            
            elif any(term in user_query.lower() for term in ["weather", "temperature", "climate"]):
                # Search for weather
                self._search_weather(state)
            
            elif any(term in user_query.lower() for term in ["visa", "passport", "requirement", "document"]):
                # Search for visa requirements
                self._search_visa_requirements(state)
            
            else:
                # Default searches
                self._search_hotels(state)
                self._search_flights(state)
            
            # Update conversation stage to response generation
            state.update_conversation_stage(ConversationStage.RESPONSE_GENERATION)
            
        except Exception as e:
            logger.error(f"Error in search execution: {str(e)}")
            state.log_error("search_execution", {"error": str(e)})
            
            # Update stage to error handling
            state.update_conversation_stage(ConversationStage.ERROR_HANDLING)
        
        return state
    
    def _search_destination_info(self, destination: str) -> Dict[str, Any]:
        """
        Search for general information about a destination.
        
        Args:
            destination: The destination name
            
        Returns:
            Dictionary with destination information
        """
        try:
            logger.info(f"Searching destination info for: {destination}")
            result = self.search_tools.search_destination_info(destination)
            return result
        except Exception as e:
            logger.error(f"Error in destination search: {str(e)}")
            return {}
    
    def _search_hotels(self, state: TravelState) -> None:
        """
        Search for hotels based on the state parameters.
        
        Args:
            state: The current TravelState
        """
        destination = state.get_primary_destination()
        dates = state.get_primary_date_range()
        
        if not destination:
            return
        
        # Prepare check-in and check-out dates if available
        check_in = None
        check_out = None
        
        if dates and dates.start_date:
            check_in = dates.start_date.isoformat()
            
            if dates.end_date:
                check_out = dates.end_date.isoformat()
        
        # Get number of travelers
        num_people = 2  # Default
        if state.travelers:
            num_people = state.travelers.total
        
        try:
            logger.info(f"Searching hotels in: {destination.name}")
            # First, get raw search results
            query = f"hotels in {destination.name} check in {check_in} check out {check_out} for {num_people} guests"
            raw_result = self.search_tools.search(
                query=query,
                search_type="organic",
                location=destination.name
            )
            
            # Parse the results into structured hotel data using our enhanced parser
            search_params = {
                "location": destination.name,
                "check_in": check_in,
                "check_out": check_out
            }
            structured_hotels = SearchResultParser.process_search_results(
                raw_result, "hotel", search_params
            )
            
            # Create and add search result with both raw and structured data
            hotel_result = SearchResult(
                type="hotel",
                source="serper",
                data={
                    "structured": structured_hotels,
                    "raw": raw_result.get("organic", [])[:5]  # Include top 5 raw results
                }
            )
            
            state.add_search_result(hotel_result)
            
        except Exception as e:
            logger.error(f"Error in hotel search: {str(e)}")
    
    def _search_flights(self, state: TravelState) -> None:
        """
        Search for flights based on the state parameters.
        
        Args:
            state: The current TravelState
        """
        destination = state.get_primary_destination()
        origin = state.origins[0] if state.origins else None
        dates = state.get_primary_date_range()
        
        if not destination or not origin:
            return
        
        # Prepare departure and return dates if available
        departure_date = None
        return_date = None
        
        if dates and dates.start_date:
            departure_date = dates.start_date.isoformat()
            
            if dates.end_date:
                return_date = dates.end_date.isoformat()
        
        # Extract time preference from user query if available
        time_preference = None
        user_query = state.get_latest_user_query().lower()
        
        # Check for time preferences in the query
        if any(term in user_query for term in ["morning", "am", "early"]):
            time_preference = "morning"
        elif any(term in user_query for term in ["afternoon", "noon", "midday"]):
            time_preference = "afternoon"
        elif any(term in user_query for term in ["evening", "night", "pm", "late"]):
            time_preference = "evening"
        
        try:
            logger.info(f"Searching flights from {origin.name} to {destination.name}")
            
            # Handle temporal references in dates (e.g., 'tomorrow', 'next week')
            parsed_departure_date = self._resolve_temporal_reference(departure_date)
            parsed_return_date = self._resolve_temporal_reference(return_date) if return_date else None
            
            # First, get raw search results
            date_str = parsed_departure_date
            query = f"flights from {origin.name} to {destination.name} on {date_str}"
            if time_preference:
                query += f" {time_preference}"
            
            raw_result = self.search_tools.search(
                query=query,
                search_type="organic",
                location=None
            )
            
            # Parse the results into structured flight data using our enhanced parser
            search_params = {
                "origin": origin.name,
                "destination": destination.name,
                "date": parsed_departure_date
            }
            structured_flights = SearchResultParser.process_search_results(
                raw_result, "flight", search_params
            )
            
            # Create and add search result with both raw and structured data
            flight_result = SearchResult(
                type="flight",
                source="serper",
                data={
                    "structured": structured_flights,
                    "raw": raw_result.get("organic", [])[:5],  # Include top 5 raw results
                    "query": query
                }
            )
            
            state.add_search_result(flight_result)
            
        except Exception as e:
            logger.error(f"Error in flight search: {str(e)}")
    
    def _resolve_temporal_reference(self, date_str: str) -> str:
        """
        Resolve temporal references like 'tomorrow', 'next week' to actual dates.
        
        Args:
            date_str: Date string that might contain temporal references
            
        Returns:
            Resolved date string in YYYY-MM-DD format
        """
        if not date_str:
            return None
            
        # Convert common temporal references to actual dates
        today = datetime.now().date()
        
        # Handle 'tomorrow' and variations
        if date_str == "tomorrow":
            return (today + timedelta(days=1)).isoformat()
            
        # Handle 'next week' and variations
        elif "next week" in date_str.lower() or "nextweek" in date_str.lower():
            return (today + timedelta(days=7)).isoformat()
            
        # Handle 'weekend' (next Saturday)
        elif "weekend" in date_str.lower():
            days_until_saturday = (5 - today.weekday()) % 7
            return (today + timedelta(days=days_until_saturday)).isoformat()
            
        # Handle 'next month'
        elif "next month" in date_str.lower():
            return (today + timedelta(days=30)).isoformat()
            
        # Handle specific day references
        day_mapping = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, 
            "friday": 4, "saturday": 5, "sunday": 6
        }
        
        for day, weekday in day_mapping.items():
            if day in date_str.lower():
                days_until_day = (weekday - today.weekday()) % 7
                if days_until_day == 0:  # If it's the same day, go to next week
                    days_until_day = 7
                return (today + timedelta(days=days_until_day)).isoformat()
        
        # If no temporal reference is found, return the original string
        return date_str
    
    def _search_weather(self, state: TravelState) -> None:
        """
        Search for weather information based on the state parameters.
        
        Args:
            state: The current TravelState
        """
        destination = state.get_primary_destination()
        dates = state.get_primary_date_range()
        
        if not destination:
            return
        
        # Prepare date for weather search
        date_str = None
        if dates and dates.start_date:
            date_str = dates.start_date.isoformat()
        
        try:
            logger.info(f"Searching weather for: {destination.name}")
            result = self.search_tools.search_weather(
                location=destination.name,
                date=date_str
            )
            
            # Create and add search result
            weather_result = SearchResult(
                type="weather",
                source="serper",
                data=result
            )
            
            state.add_search_result(weather_result)
            
        except Exception as e:
            logger.error(f"Error in weather search: {str(e)}")
    
    def _search_visa_requirements(self, state: TravelState) -> None:
        """
        Search for visa requirements based on the state parameters.
        
        Args:
            state: The current TravelState
        """
        destination = state.get_primary_destination()
        origin = state.origins[0] if state.origins else None
        
        if not destination or not origin:
            return
        
        # Extract countries from origin and destination
        from_country = origin.country if origin.country else origin.name
        to_country = destination.country if destination.country else destination.name
        
        try:
            logger.info(f"Searching visa requirements from {from_country} to {to_country}")
            result = self.search_tools.search_visa_requirements(
                from_country=from_country,
                to_country=to_country
            )
            
            # Create and add search result
            visa_result = SearchResult(
                type="visa",
                source="serper",
                data=result
            )
            
            state.add_search_result(visa_result)
            
        except Exception as e:
            logger.error(f"Error in visa search: {str(e)}")
