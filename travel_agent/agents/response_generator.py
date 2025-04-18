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
                    hotels = result.data.get("hotels", [])
                    formatted_text += f"Found {len(hotels)} hotels for {result.data.get('query_location', 'the location')}:\n"
                    
                    for j, hotel in enumerate(hotels[:3], 1):  # Limit to 3 hotels
                        formatted_text += f"- {hotel.get('name', 'Unknown Hotel')}: {hotel.get('description', 'No description')}. URL: {hotel.get('link', 'No link')}\n"
                
                elif result_type == "flight":
                    flights = result.data.get("flights", [])
                    formatted_text += f"Found {len(flights)} flight options from {result.data.get('origin', 'origin')} to {result.data.get('destination', 'destination')}:\n"
                    
                    for j, flight in enumerate(flights[:3], 1):  # Limit to 3 flights
                        formatted_text += f"- {flight.get('title', 'Unknown Flight')}: {flight.get('description', 'No description')}. URL: {flight.get('link', 'No link')}\n"
                    
                    providers = result.data.get("providers", [])
                    if providers:
                        formatted_text += f"Booking providers: {', '.join(providers)}\n"
                
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
            else:
                return "I need a bit more information to help plan your trip. Could you tell me more about your travel plans?"
        
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
