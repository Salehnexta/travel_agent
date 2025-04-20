import logging
from typing import Dict, Any, List, Optional
import json

from travel_agent.state_definitions import TravelState, ConversationStage, SearchResult
from travel_agent.llm_provider import LLMClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ResponseGenerator:
    """
    Generates natural language responses based on search results and travel state.
    Creates user-friendly, informative responses with structured data.
    """
    
    def __init__(self):
        """Initialize the response generator with an LLM client."""
        self.llm_client = LLMClient()
        logger.info("Response Generator initialized")
    
    def process(self, state: TravelState) -> TravelState:
        """
        Process the state to generate an appropriate response.
        
        Args:
            state: The current TravelState
            
        Returns:
            Updated TravelState with assistant response
        """
        try:
            # Generate response based on the current stage and search results
            response = self._generate_response(state)
            
            # Add the response to the conversation history
            state.add_message("assistant", response)
            
            # Update the conversation stage to follow-up
            state.update_conversation_stage(ConversationStage.FOLLOW_UP)
            
        except Exception as e:
            logger.error(f"Error in response generation: {str(e)}")
            state.log_error("response_generation", {"error": str(e)})
            
            # Generate a fallback response
            fallback = self._generate_fallback_response(state)
            state.add_message("assistant", fallback)
            state.update_conversation_stage(ConversationStage.ERROR_HANDLING)
        
        return state
    
    def _generate_response(self, state: TravelState) -> str:
        """
        Generate a response based on the current state and search results.
        
        Args:
            state: The current TravelState
            
        Returns:
            A response string
        """
        # Get the latest user query
        user_query = state.get_latest_user_query()
        
        # Check if we have search results
        if not state.search_results:
            # No search results, generate a generic response
            return self._generate_generic_response(state)
        
        # Prepare the system prompt
        system_prompt = """
        You are an AI travel assistant helping a user plan their trip. 
        Generate a helpful, friendly response based on the search results provided.
        Your response should be informative yet concise, highlighting the most relevant information.
        
        Use the following guidelines:
        1. Address the user's query directly
        2. Present the key information from search results in a natural way
        3. Be conversational and encouraging
        4. If showing multiple options (hotels, flights), present them in a structured, easy-to-read format
        5. End with a natural follow-up question or suggestion when appropriate
        
        Remember to maintain a helpful and friendly tone throughout.
        """
        
        # Prepare search results for the prompt
        search_results_text = self._format_search_results_for_prompt(state.search_results)
        
        # Prepare conversation context
        conversation_context = state.get_conversation_context(num_messages=5)
        conversation_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_context])
        
        # Prepare the travel parameters summary
        parameters_text = self._format_parameters_for_prompt(state)
        
        # Create the user message with all the context
        prompt = f"""
        User query: {user_query}
        
        Recent conversation:
        {conversation_text}
        
        Travel parameters:
        {parameters_text}
        
        Search results:
        {search_results_text}
        
        Please generate a helpful response to the user's query.
        """
        
        # Create the messages for LLM
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        # Generate the response using LLM
        try:
            response = self.llm_client.generate_response(
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error in LLM response generation: {str(e)}")
            return self._generate_fallback_response(state)
    
    def _format_search_results_for_prompt(self, search_results: Dict[str, List[SearchResult]]) -> str:
        """
        Format search results for inclusion in the prompt.
        
        Args:
            search_results: Dictionary of search results by type
            
        Returns:
            Formatted string of search results
        """
        if not search_results:
            return "No search results available."
        
        formatted_text = ""
        
        # Process each type of search result
        for result_type, results in search_results.items():
            formatted_text += f"\n{result_type.upper()} RESULTS:\n"
            
            for i, result in enumerate(results, 1):
                formatted_text += f"Result {i}:\n"
                
                # Format data based on result type
                if result_type == "hotel":
                    # Get structured hotels from the enhanced parser
                    structured_hotels = result.data.get("structured", [])
                    
                    if structured_hotels:
                        formatted_text += f"Found {len(structured_hotels)} hotels for {result.data.get('location', 'the location')}:\n"
                        
                        for j, hotel in enumerate(structured_hotels[:3], 1):  # Limit to 3 hotels
                            hotel_text = f"- {hotel.get('title', 'Unknown Hotel')}"
                            
                            # Add details if available
                            if hotel.get("price"):
                                hotel_text += f" - {hotel.get('price')}"
                            if hotel.get("rating"):
                                hotel_text += f" - {hotel.get('rating')}"
                                
                            # Add source and link
                            hotel_text += f" (via {hotel.get('source', 'Hotel Search')})"
                            if hotel.get("link"):
                                hotel_text += f"\n  Booking link: {hotel.get('link')}"
                            
                            formatted_text += f"{hotel_text}\n"
                    else:
                        # Fall back to raw hotels data if available
                        raw_hotels = result.data.get("raw", [])
                        formatted_text += f"Found hotel options for {result.data.get('location', 'the location')}:\n"
                        
                        for j, hotel in enumerate(raw_hotels[:3], 1):  # Limit to 3 hotels
                            formatted_text += f"- {hotel.get('title', 'Unknown Hotel')}: {hotel.get('snippet', 'No description')}\n"
                
                elif result_type == "flight":
                    # Get structured flights from the enhanced parser
                    structured_flights = result.data.get("structured", [])
                    
                    # --- New Flight Filtering Logic ---
                    if structured_flights:
                        # Apply basic filters (e.g., duration, airline - assuming 'stops' is added by parser)
                        # TODO: Use SEARCH_CONFIG if available and robust
                        all_valid_flights = [
                            f for f in structured_flights 
                            # Add duration/airline filters here if needed later
                        ]
                        
                        # Separate direct and one-stop flights
                        direct_flights = [f for f in all_valid_flights if f.get('stops') == 0]
                        one_stop_flights = [f for f in all_valid_flights if f.get('stops') == 1]
                        
                        # -- Store final flights for package cost calculation --
                        final_flights_for_cost = direct_flights + one_stop_flights[:max(0, 8 - len(direct_flights))]
                        
                        # Combine results: all direct + up to (8 - num_direct) one-stop
                        final_flights = direct_flights
                        needed_one_stop = 8 - len(direct_flights)
                        
                        # --- Package Itinerary Generation --- 
                        package_details = {}
                        activity_results = None
                        hotel_results = None # Fetch hotel results too
                        
                        # Fetch Activity & Hotel Results (Assume SearchManager adds these)
                        for res in search_results:
                            if res.type == "activity":
                                activity_results = res.data.get("structured", [])
                            elif res.type == "hotel":
                                hotel_results = res.data.get("structured", [])
                                
                        # Calculate Estimated Costs 
                        total_flight_cost = sum(f.get('price_value', 0) for f in final_flights_for_cost if f.get('price_value')) 
                        # Estimate hotel cost (e.g., first hotel price * nights)
                        num_nights = (state.get_primary_date_range() or {}).get('duration', 4) # Default 4 nights if duration unknown
                        estimated_hotel_price_per_night = (hotel_results[0].get('price_value', 300) if hotel_results and hotel_results[0].get('price_value') else 300) # Default 300 SAR/night
                        total_hotel_cost = estimated_hotel_price_per_night * num_nights
                        total_activity_cost = 500 # Placeholder SAR
                        
                        estimated_total_cost = total_flight_cost + total_hotel_cost + total_activity_cost
                        
                        # Structure the Day-by-Day Itinerary 
                        num_days = num_nights + 1 # 5 days for 4 nights
                        dest_name = state.get_primary_destination().name if state.get_primary_destination() else "your destination"
                        origin_name = state.origins[0].name if state.origins else "your origin"
                        
                        itinerary_text = f"\n**Draft {num_days}-Day {dest_name.title()} Package from {origin_name.title()} (Approx. SAR {estimated_total_cost}):**\n"
                        itinerary_text += f"*   Flights: Approx. SAR {total_flight_cost} (Round Trip)\n"
                        itinerary_text += f"*   Hotel: Approx. SAR {total_hotel_cost} ({num_nights} nights - based on {estimated_hotel_price_per_night} SAR/night estimate)\n"
                        itinerary_text += f"*   Activities/Misc: Approx. SAR {total_activity_cost}\n"
                        itinerary_text += "------------------------------------\n"
                        
                        # TODO: Use actual activity_results with descriptions when available from SearchManager/Parser
                        # Using placeholders for Bangkok example with descriptions:
                        # Structure: {'name': 'Name', 'description': 'Desc', 'cost': 'Cost Info'} 
                        daily_plan_with_details = {
                            # Using Bangkok placeholders for a 7-day trip example
                             1: [{"name": "Arrive in Bangkok (BKK), Check into hotel", "description": "Settle in and prepare for your adventure.", "cost": "Varies"},
                                 {"name": "Evening: Explore Sukhumvit Road", "description": "Experience Bangkok's vibrant nightlife, street food, and shopping.", "cost": "Varies"}],
                             2: [{"name": "Morning: Grand Palace & Wat Phra Kaew", "description": "Visit the stunning former royal residence and the Temple of the Emerald Buddha.", "cost": "Est. SAR 60 entry"},
                                 {"name": "Afternoon: Wat Pho & Wat Arun", "description": "See the giant Reclining Buddha at Wat Pho and climb the iconic Temple of Dawn.", "cost": "Est. SAR 30 entry total"}],
                             3: [{"name": "Full Day: Floating Market Tour", "description": "Experience a traditional market via longtail boat (e.g., Damnoen Saduak).", "cost": "Est. SAR 150-250 tour"},
                                 {"name": "Evening: Asiatique The Riverfront", "description": "Enjoy shopping, dining, and entertainment by the river.", "cost": "Varies"}],
                             4: [{"name": "Morning: Chatuchak Market (Weekend) / Mall", "description": "Explore one of the world's largest outdoor markets or a modern shopping mall (MBK/Siam Paragon).", "cost": "Varies"},
                                 {"name": "Afternoon: Jim Thompson House Museum", "description": "Discover the beautiful Thai house and art collection of the American silk entrepreneur.", "cost": "Est. SAR 25 entry"}],
                             5: [{"name": "Full Day: Ayutthaya Historical Park", "description": "Explore the ruins of the former Siamese capital, a UNESCO site, via day trip.", "cost": "Est. SAR 200-300 tour + entry"}],
                             6: [{"name": "Morning: Thai Cooking Class", "description": "Learn to cook authentic Thai dishes hands-on.", "cost": "Est. SAR 120-180"},
                                  {"name": "Afternoon: Relax/Spa", "description": "Enjoy some downtime or indulge in a traditional Thai massage.", "cost": "SAR 100+"},
                                  {"name": "Evening: Rooftop Bar Experience", "description": "Enjoy panoramic city views from a sky bar (e.g., Lebua at State Tower).", "cost": "Drinks SAR 50+" }],
                             7: [{"name": "Morning: Last minute shopping", "description": "Grab any remaining souvenirs or revisit a favourite spot.", "cost": "Varies"},
                                 {"name": "Depart from Bangkok (BKK)", "description": "Head to Suvarnabhumi Airport for your return flight."}]
                        }
 
                        for day in range(1, num_days + 1):
                            itinerary_text += f"**Day {day}:**\n"
                            if day in daily_plan_with_details:
                                for activity in daily_plan_with_details[day]:
                                    cost_str = f" ({activity.get('cost', 'Cost varies')})" 
                                    itinerary_text += f"- **{activity.get('name', 'Activity')}**{cost_str}: {activity.get('description', 'Details not available.')}\n" # Include description
                            else:
                                itinerary_text += f"- Explore {dest_name.title()} (Details vary)\n"
                            itinerary_text += "\n" 
                            
                        formatted_text += itinerary_text
                        # --- End Package Itinerary Generation ---
                        
                        # Format the final list (final_flights) for display
                        if final_flights:
                            formatted_text += f"\nFound {len(final_flights)} suitable outbound flights for {origin_name} to {dest_name.title()}:\n"
                            # TODO: Refine flight display for round trip clarity
                            for i, flight in enumerate(final_flights, 1):
                                stops_desc = f"{flight.get('stops', '?')} stops"
                                if flight.get('stops') == 0:
                                    stops_desc = "Direct"
                                if flight.get('stops') == 1:
                                    stops_desc = "1 stop"
                                 
                                price_str = f"SAR {flight.get('price_value', 'N/A')}" if flight.get('price_value') else flight.get('price', 'N/A') # Use price_value if available
                                formatted_text += f"{i}. Airline: {flight.get('airline', 'N/A')}, Price: {price_str}, Stops: {stops_desc}, Departure: {flight.get('departure_time', 'N/A')}, Arrival: {flight.get('arrival_time', 'N/A')}\n"
                            formatted_text += "\n*(Return flight options matching your dates would also be presented here. Cost estimate below assumes round trip.)*\n"
                        else:
                            formatted_text += "\nCould not find suitable flights based on the initial search.\n"
                     
                        # TEMP: Double the cheapest outbound for a rough round-trip estimate if only outbound shown
                        if final_flights_for_cost and total_flight_cost > 0:
                            cheapest_outbound = min(f.get('price_value', float('inf')) for f in final_flights_for_cost if f.get('price_value'))
                            if cheapest_outbound != float('inf'):
                                # Assume return is roughly same price for estimation for now
                                total_flight_cost = cheapest_outbound * 2 
                            else: # Fallback if no prices found
                                total_flight_cost = 2500 # Default placeholder
                        else:
                            total_flight_cost = 2500 # Default placeholder
                    # --- End New Flight Filtering Logic ---
                
                elif result_type == "destination":
                    general = result.data.get("general", {})
                    if "organic" in general:
                        for j, item in enumerate(general.get("organic", [])[:3], 1):
                            formatted_text += f"- {item.get('title', 'Information')}: {item.get('snippet', 'No description')}\n"
                
                elif result_type == "weather":
                    weather_info = result.data.get("weather_info")
                    if weather_info:
                        formatted_text += f"Weather: {weather_info}\n"
                    
                    forecast = result.data.get("forecast", [])
                    for j, item in enumerate(forecast[:2], 1):
                        formatted_text += f"- {item.get('title', 'Forecast')}: {item.get('description', 'No details')}\n"
                
                elif result_type == "visa":
                    visa_info = result.data.get("visa_info")
                    if visa_info:
                        formatted_text += f"Visa information: {visa_info}\n"
                    
                    requirements = result.data.get("requirements", [])
                    for j, item in enumerate(requirements[:2], 1):
                        formatted_text += f"- {item.get('title', 'Requirement')}: {item.get('description', 'No details')}\n"
                
                formatted_text += "\n"
        
        return formatted_text
    
    def _format_parameters_for_prompt(self, state: TravelState) -> str:
        """
        Format travel parameters for inclusion in the prompt.
        
        Args:
            state: The current TravelState
            
        Returns:
            Formatted string of travel parameters
        """
        formatted_text = ""
        
        # Add destinations
        if state.destinations:
            destinations = [d.name for d in state.destinations]
            formatted_text += f"Destinations: {', '.join(destinations)}\n"
        
        # Add origins
        if state.origins:
            origins = [o.name for o in state.origins]
            formatted_text += f"Origins: {', '.join(origins)}\n"
        
        # Add dates
        if state.dates:
            dates_str = []
            for date_param in state.dates:
                if date_param.date_range and date_param.start_date and date_param.end_date:
                    date_str = f"{date_param.start_date} to {date_param.end_date}"
                elif date_param.start_date:
                    date_str = str(date_param.start_date)
                else:
                    date_str = "Unspecified date"
                
                dates_str.append(f"{date_param.type}: {date_str}")
            
            formatted_text += f"Dates: {'; '.join(dates_str)}\n"
        
        # Add travelers
        if state.travelers:
            travelers_str = f"Adults: {state.travelers.adults}, Children: {state.travelers.children}, Infants: {state.travelers.infants}"
            formatted_text += f"Travelers: {travelers_str}\n"
        
        # Add budget
        if state.budget:
            budget_str = f"{state.budget.min_value}-{state.budget.max_value} {state.budget.currency}" if state.budget.min_value and state.budget.max_value else "Unspecified"
            formatted_text += f"Budget: {budget_str}\n"
        
        # Add preferences
        if state.preferences:
            pref_strs = []
            for pref in state.preferences:
                pref_str = f"{pref.category}: {', '.join(pref.preferences)}"
                pref_strs.append(pref_str)
            
            formatted_text += f"Preferences: {'; '.join(pref_strs)}\n"
        
        return formatted_text
    
    def _generate_generic_response(self, state: TravelState) -> str:
        """
        Generate a generic response when no search results are available.
        
        Args:
            state: The current TravelState
            
        Returns:
            A generic response string
        """
        # Check if we have missing parameters
        missing_params = state.get_missing_parameters()
        
        if missing_params:
            # Generate a response asking for missing parameters
            if "destination" in missing_params:
                return "To help plan your trip, I need to know where you'd like to go. Could you please tell me your desired destination?"
            elif "dates" in missing_params:
                return "When are you planning to travel? Knowing your travel dates will help me find the best options for you."
            elif "origin" in missing_params and any(term in state.get_latest_user_query().lower() for term in ["flight", "fly", "plane"]):
                return "I can help you find flights, but I need to know where you'll be flying from. Could you please tell me your departure city or airport?"
            else:
                return "I need a bit more information to help plan your trip. Could you tell me more about your travel plans?"
        
        # Check for temporal references that didn't resolve properly
        if state.dates:
            for date_param in state.dates:
                if date_param.start_date in ["tomorrow", "next week", "weekend", "this weekend", "nextweek"]:
                    # Update the generic response to acknowledge the temporal reference
                    return (
                        "I understand you want to travel "  + date_param.start_date + ". "
                        "I'll convert that to an actual date for searching. "
                        "Is there anything specific you're looking for in your travel options?"
                    )
        
        # Default response
        return (
            "Thank you for providing those details. I'm working on finding the best options for your trip. "
            "Is there anything specific you'd like to know about your destination, such as hotels, flights, or activities?"
        )
    
    def _generate_fallback_response(self, state: TravelState) -> str:
        """
        Generate a fallback response when response generation encounters an error.
        
        Args:
            state: The current TravelState
            
        Returns:
            A fallback response string
        """
        return (
            "I apologize, but I'm having trouble processing that request right now. "
            "Could you please rephrase your question or ask something else about your travel plans?"
        )
