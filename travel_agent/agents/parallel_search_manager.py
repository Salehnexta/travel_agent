"""
Parallel Search Manager for travel agent.
Implements concurrent API calls for flight and hotel searches for faster responses.
"""

import logging
import asyncio
import concurrent.futures
from typing import Dict, List, Any, Optional

from travel_agent.state_definitions import TravelState, SearchResult
from travel_agent.search_tools import search_flights, search_hotels, search_destination_info
from travel_agent.error_tracking import error_tracker
from travel_agent.config.cache_manager import cached

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ParallelSearchManager:
    """
    Search manager that executes flight, hotel, and destination searches in parallel.
    Uses asyncio and concurrent execution for improved performance.
    """
    
    def __init__(self):
        """Initialize the parallel search manager."""
        logger.info("Parallel Search Manager initialized")
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
    
    async def _search_destination_async(self, location_name: str) -> Dict[str, Any]:
        """Execute destination info search asynchronously."""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor, 
                search_destination_info, 
                location_name
            )
        except Exception as e:
            error_id = error_tracker.track_error(
                e, {"component": "parallel_search", "search_type": "destination", "location": location_name}
            )
            logger.error(f"Error in destination search: {str(e)} (Error ID: {error_id})")
            return {"error": str(e), "error_id": error_id}
    
    async def _search_flights_async(
        self, 
        origin: str, 
        destination: str, 
        date: str, 
        travelers: int = 1
    ) -> Dict[str, Any]:
        """Execute flight search asynchronously."""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor,
                lambda: search_flights(origin, destination, date, travelers)
            )
        except Exception as e:
            error_id = error_tracker.track_error(
                e, {
                    "component": "parallel_search", 
                    "search_type": "flights",
                    "origin": origin,
                    "destination": destination,
                    "date": date
                }
            )
            logger.error(f"Error in flight search: {str(e)} (Error ID: {error_id})")
            return {"error": str(e), "error_id": error_id}
    
    async def _search_hotels_async(
        self, 
        location: str, 
        check_in: str, 
        check_out: str, 
        guests: int = 1,
        preferences: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Execute hotel search asynchronously."""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor,
                lambda: search_hotels(
                    location, 
                    check_in, 
                    check_out, 
                    guests, 
                    preferences or []
                )
            )
        except Exception as e:
            error_id = error_tracker.track_error(
                e, {
                    "component": "parallel_search", 
                    "search_type": "hotels",
                    "location": location,
                    "check_in": check_in,
                    "check_out": check_out
                }
            )
            logger.error(f"Error in hotel search: {str(e)} (Error ID: {error_id})")
            return {"error": str(e), "error_id": error_id}
    
    @cached(ttl=1800)  # Cache results for 30 minutes
    async def execute_parallel_searches(self, state: TravelState) -> TravelState:
        """
        Execute all necessary searches in parallel based on the current state.
        
        Args:
            state: Current TravelState with parameters
            
        Returns:
            Updated TravelState with search results
        """
        # Prepare search tasks
        search_tasks = []
        
        # Destination info searches
        for destination in state.destinations:
            if destination.name:
                logger.info(f"Queuing destination info search for: {destination.name}")
                task = self._search_destination_async(destination.name)
                search_tasks.append(("destination", destination.name, task))
        
        # Flight searches
        if state.destinations and state.dates:
            origin = state.origins[0].name if state.origins else "DMM"  # Default origin
            destination = state.destinations[0].name
            # Get the first departure date
            departure_date = next((d.date_value.strftime("%Y-%m-%d") for d in state.dates 
                                if d.type == "departure" and d.date_value), None)
            
            if departure_date:
                travelers = state.travelers.adults if state.travelers else 1
                logger.info(f"Queuing flight search from {origin} to {destination} on {departure_date}")
                task = self._search_flights_async(origin, destination, departure_date, travelers)
                search_tasks.append(("flight", f"{origin}-{destination}", task))
        
        # Hotel searches
        if state.destinations and state.dates:
            location = state.destinations[0].name
            check_in = next((d.date_value.strftime("%Y-%m-%d") for d in state.dates 
                           if d.type == "departure" and d.date_value), None)
            # Check out is either the return date or departure+3 days
            check_out = next((d.date_value.strftime("%Y-%m-%d") for d in state.dates 
                            if d.type == "return" and d.date_value), None)
            
            if not check_out and check_in:
                from datetime import datetime, timedelta
                check_in_date = datetime.strptime(check_in, "%Y-%m-%d")
                check_out = (check_in_date + timedelta(days=3)).strftime("%Y-%m-%d")
            
            if check_in and check_out:
                # Extract hotel preferences if available
                preferences = []
                for pref in state.preferences:
                    if pref.category.lower() == "hotel":
                        preferences.extend(pref.preferences)
                
                travelers = state.travelers.adults if state.travelers else 1
                logger.info(f"Queuing hotel search in {location} from {check_in} to {check_out}")
                task = self._search_hotels_async(location, check_in, check_out, travelers, preferences)
                search_tasks.append(("hotel", location, task))
        
        # Execute all search tasks in parallel
        if search_tasks:
            results = {}
            for search_type, search_id, task in search_tasks:
                try:
                    result = await task
                    if "error" not in result:
                        # Add the result to the state
                        search_result = SearchResult(
                            type=search_type,
                            source="serper",
                            data=result
                        )
                        state.add_search_result(search_result)
                        results[f"{search_type}_{search_id}"] = "Success"
                    else:
                        logger.error(f"Search error for {search_type} {search_id}: {result.get('error')}")
                        results[f"{search_type}_{search_id}"] = f"Error: {result.get('error')}"
                except Exception as e:
                    error_id = error_tracker.track_error(
                        e, {"component": "parallel_search", "search_type": search_type, "id": search_id}
                    )
                    logger.error(f"Error executing {search_type} search for {search_id}: {str(e)} (Error ID: {error_id})")
                    results[f"{search_type}_{search_id}"] = f"Exception: {str(e)}"
            
            logger.info(f"Parallel search results: {results}")
        else:
            logger.info("No search tasks to execute")
        
        return state
    
    def process(self, state: TravelState) -> TravelState:
        """
        Process the state to execute all necessary searches.
        This is the main entry point for the search manager.
        
        Args:
            state: Current TravelState with parameters
            
        Returns:
            Updated TravelState with search results
        """
        # Run the async search execution in an event loop
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result_state = loop.run_until_complete(self.execute_parallel_searches(state))
            loop.close()
            return result_state
        except Exception as e:
            error_id = error_tracker.track_error(e, {"component": "parallel_search_manager"})
            logger.error(f"Error in parallel search execution: {str(e)} (Error ID: {error_id})")
            state.log_error("search_execution", {"error": str(e), "error_id": error_id})
            return state
