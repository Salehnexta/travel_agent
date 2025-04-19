import logging
import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from travel_agent.date_processor import post_process_date_values

from travel_agent.state_definitions import (
    TravelState, ConversationStage, 
    LocationParameter, DateParameter, TravelerParameter, 
    BudgetParameter, PreferenceParameter
)
from travel_agent.llm_provider import LLMClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ParameterExtractionAgent:
    """
    Agent responsible for extracting travel parameters from user messages.
    Identifies destinations, dates, travelers, budget, and preferences.
    """
    
    def __init__(self):
        """Initialize the parameter extraction agent with an LLM client."""
        self.llm_client = LLMClient()
        logger.info("Parameter Extraction Agent initialized")
    
    def process(self, state: TravelState) -> TravelState:
        """
        Process the user's message to extract travel parameters.
        
        Args:
            state: The current TravelState
            
        Returns:
            Updated TravelState with extracted parameters
        """
        # Get the latest user message
        user_message = state.get_latest_user_query()
        if not user_message:
            return state
        
        # Extract parameters using LLM
        extracted_params = self._extract_parameters(user_message, state)
        
        # Update state with extracted parameters
        state = self._update_state_with_parameters(state, extracted_params)
        
        # Enhanced hotel preference extraction with various patterns
        if "hotel" in user_message.lower():
            # Different patterns for hotel preferences
            hotel_patterns = [
                # Near a location
                (r'hotel\s+(?:near|close to|by|around)\s+(?:the\s+)?(.*?)(?:\s+in|\s+for|\s+and|\s+with|$)', "location"),
                # In a specific area
                (r'hotel\s+in\s+(?:the\s+)?(.*?)(?:\s+near|\s+for|\s+and|\s+with|$)', "area"),
                # With specific amenities
                (r'hotel\s+with\s+(.*?)(?:\s+in|\s+near|\s+for|\s+and|$)', "amenity")
            ]
            
            for pattern, pref_type in hotel_patterns:
                matches = re.finditer(pattern, user_message.lower())
                for match in matches:
                    preference = match.group(1).strip()
                    if preference and len(preference) > 2:  # Avoid meaningless short matches
                        logger.info(f"Detected hotel {pref_type} preference: {preference}")
                        
                        # Add as a hotel preference if not already present
                        hotel_pref_exists = False
                        for pref in state.preferences:
                            if pref.category.lower() == "hotel":
                                if preference not in pref.preferences:
                                    pref.preferences.append(preference)
                                hotel_pref_exists = True
                                break
                        
                        if not hotel_pref_exists:
                            # Create new hotel preference
                            state.preferences.append(PreferenceParameter(
                                category="hotel",
                                preferences=[preference],
                                confidence=0.9
                            ))
                            logger.info(f"Added hotel {pref_type} preference: {preference}")
        
        # Enhanced temporal reference extraction (e.g., "tomorrow", "next week")
        if len(state.destinations) > 0 and len(state.dates) == 0:
            # Map of temporal references and their corresponding date values
            temporal_references = {
                "tomorrow": date.today() + timedelta(days=1),
                "tmrw": date.today() + timedelta(days=1),      # Common abbreviation
                "tmw": date.today() + timedelta(days=1),       # Another abbreviation
                "today": date.today(),
                "next week": date.today() + timedelta(days=7),
                "in a week": date.today() + timedelta(days=7),
                "after 7 days": date.today() + timedelta(days=7),
                "weekend": date.today() + timedelta(days=(5 - date.today().weekday()) % 7),
                "next month": date.today() + timedelta(days=30),
                "in a month": date.today() + timedelta(days=30)
            }
            
            # Text normalization for better matching
            normalized_message = user_message.lower()
            
            # First check for exact matches
            found_match = False
            for reference, date_value in temporal_references.items():
                if reference in normalized_message:
                    state.add_date(DateParameter(
                        type="departure",
                        date_value=date_value,
                        flexible=reference not in ["today", "tomorrow", "tmrw", "tmw"],
                        confidence=0.9
                    ))
                    logger.info(f"Added {reference} as departure date: {date_value}")
                    found_match = True
                    break
            
            # If no exact match found, try pattern matching for variations
            if not found_match:
                # Check for variations like 'for tomorrow', 'by tomorrow', etc.
                tomorrow_patterns = [
                    r'\b(for|by|on|this|coming)\s+tomorrow\b',
                    r'\btomorrow\'s\b',
                    r'\btmrw\b',  # Common abbreviation
                    r'\btmw\b',   # Another abbreviation
                    r'\bfor\s+tmrw\b',
                    r'\btmr\b',   # Another variant
                    r'\bfor\s+tomorrow\b',  # Explicit pattern for 'for tomorrow'
                    r'flight.*for\s+tomorrow'  # Pattern for 'flight... for tomorrow'
                ]
                
                for pattern in tomorrow_patterns:
                    if re.search(pattern, normalized_message):
                        tomorrow_date = date.today() + timedelta(days=1)
                        state.add_date(DateParameter(
                            type="departure",
                            date_value=tomorrow_date,
                            flexible=False,
                            confidence=0.9
                        ))
                        logger.info(f"Added tomorrow (from pattern match) as departure date: {tomorrow_date}")
                        found_match = True
                        break
                
                # Check for day references (e.g., 'Monday', 'Tuesday', etc.)
                if not found_match:
                    days_of_week = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                    today_idx = date.today().weekday()  # 0 = Monday, 6 = Sunday
                    
                    for idx, day in enumerate(days_of_week):
                        if day in normalized_message:
                            # Calculate days to add to get to the mentioned day
                            target_idx = idx  # 0 = Monday, 6 = Sunday
                            days_to_add = (target_idx - today_idx) % 7
                            if days_to_add == 0:  # If mentioned day is today, assume next week
                                days_to_add = 7
                            
                            target_date = date.today() + timedelta(days=days_to_add)
                            state.add_date(DateParameter(
                                type="departure",
                                date_value=target_date,
                                flexible=False,
                                confidence=0.8
                            ))
                            logger.info(f"Added {day} as departure date: {target_date}")
                            break
            
        # ALWAYS set default travelers if none exist
        # This is critical to prevent NoneType errors in search execution
        if not state.travelers:
            # Default to 1 adult
            state.add_traveler(TravelerParameter(type="adult", count=1))
            logger.info("Added default traveler: 1 adult")
            
        # Determine if we can move to the next stage
        if state.has_minimum_parameters():
            # If we have at least destination and dates, we can proceed to search
            logger.info(f"Minimum parameters check passed: {state.has_minimum_parameters()}")
            state.update_conversation_stage(ConversationStage.SEARCH_EXECUTION)
        else:
            # Ask for missing parameters
            missing_params = state.get_missing_parameters()
            logger.info(f"Missing parameters: {missing_params}")
            if missing_params:
                clarification_param = missing_params[0]  # Start with the first missing param
                
                # Generate clarification question using conversation manager
                from travel_agent.agents.conversation_manager import ConversationManager
                conversation_manager = ConversationManager()
                
                clarification_question = conversation_manager.generate_clarification_question(
                    state, clarification_param
                )
                
                state.add_message("assistant", clarification_question)
                state.update_conversation_stage(ConversationStage.CLARIFICATION)
        
        return state
    
    def _extract_parameters(self, message: str, state: TravelState) -> Dict[str, Any]:
        """
        Extract travel parameters from the user's message using LLM.
        
        Args:
            message: The user's message
            state: The current TravelState for context
            
        Returns:
            Dictionary with extracted parameters
        """
        # Pre-process for flight queries with airport codes
        # Look for direct airport code patterns
        flight_params = {}
        
        if "flight" in message.lower():
            # Common patterns: "from X to Y", "X to Y", etc.
            flight_patterns = [
                r'from\s+([a-zA-Z]{3})\s+to\s+([a-zA-Z]{3})',  # from DMM to RUH
                r'([a-zA-Z]{3})\s+to\s+([a-zA-Z]{3})'  # DMM to RUH
            ]
            
            for pattern in flight_patterns:
                matches = re.search(pattern, message, re.IGNORECASE)
                if matches:
                    origin = matches.group(1).upper()
                    destination = matches.group(2).upper()
                    logger.info(f"Extracted flight codes directly: {origin} to {destination}")
                    flight_params["origin"] = {"name": origin, "code": origin}
                    flight_params["destination"] = {"name": destination, "code": destination}
                    break
        
            # Look for one-way or round-trip indicators
            if "one way" in message.lower() or "one-way" in message.lower():
                flight_params["trip_type"] = "one_way"
            elif "round trip" in message.lower() or "round-trip" in message.lower():
                flight_params["trip_type"] = "round_trip"
        
        # Define the parameter extraction schema
        parameter_schema = {
            "type": "object",
            "properties": {
                "destinations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "confidence": {"type": "number"},
                            "country": {"type": "string"},
                            "city": {"type": "string"}
                        },
                        "required": ["name"]
                    }
                },
                "origins": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "confidence": {"type": "number"},
                            "country": {"type": "string"},
                            "city": {"type": "string"}
                        },
                        "required": ["name"]
                    }
                },
                "dates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "date_range": {"type": "boolean"},
                            "start_date": {"type": "string"},
                            "end_date": {"type": "string"},
                            "flexible": {"type": "boolean"},
                            "confidence": {"type": "number"}
                        }
                    }
                },
                "travelers": {
                    "type": "object",
                    "properties": {
                        "adults": {"type": "integer"},
                        "children": {"type": "integer"},
                        "infants": {"type": "integer"},
                        "confidence": {"type": "number"}
                    }
                },
                "budget": {
                    "type": "object",
                    "properties": {
                        "min_value": {"type": "number"},
                        "max_value": {"type": "number"},
                        "currency": {"type": "string"},
                        "type": {"type": "string"},
                        "confidence": {"type": "number"}
                    }
                },
                "preferences": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string"},
                            "preferences": {"type": "array", "items": {"type": "string"}},
                            "exclusions": {"type": "array", "items": {"type": "string"}},
                            "confidence": {"type": "number"}
                        },
                        "required": ["category", "preferences"]
                    }
                }
            }
        }
        
        # Get recent conversation context
        conversation_context = state.get_conversation_context(num_messages=5)
        
        # Get current date for temporal references
        current_date = datetime.now().date()
        tomorrow_date = (current_date + timedelta(days=1)).strftime("%Y-%m-%d")
        next_week_date = (current_date + timedelta(days=7)).strftime("%Y-%m-%d")
        weekend_date = (current_date + timedelta(days=(5 - current_date.weekday()) % 7)).strftime("%Y-%m-%d")
        
        # Create system prompt with explicit current date information
        system_prompt = f"""
        You are an AI assistant specialized in travel planning. Extract travel parameters from the user's message.
        Pay special attention to airport codes (like JFK, LAX, DMM, RUH, BKK) which should be recognized as locations.
        
        For airport codes, apply the following mappings:
        - BKK = Bangkok, Thailand
        - DMM = Dammam, Saudi Arabia
        - JED = Jeddah, Saudi Arabia
        - RUH = Riyadh, Saudi Arabia
        - DXB = Dubai, UAE
        - AUH = Abu Dhabi, UAE
        - DOH = Doha, Qatar
        - CAI = Cairo, Egypt
        
        When a user mentions an airport code in a hotel search (e.g., "hotel in BKK"), interpret this as the city name (e.g., "hotel in Bangkok").
        
        If you detect flight information, make sure to identify origin and destination correctly.
        Pay attention to timeframes like "1 day" which should be interpreted as the duration of stay.
        
        TODAY'S DATE: The current date is {current_date.strftime("%Y-%m-%d")}. Use this as the reference point.
        For temporal references, use these EXACT dates:
        - "today" = {current_date.strftime("%Y-%m-%d")}
        - "tomorrow" = {tomorrow_date}
        - "next week" = {next_week_date}
        - "weekend" = {weekend_date}
        
        Focus on identifying:
        1. Destinations (where the user wants to go)
        2. Origins (where the user is traveling from)
        3. Dates (departure, return, flexible dates)
        4. Travelers (number of adults, children, infants)
        5. Budget information (min, max, currency)
        6. Preferences (for hotels, flights, activities, etc.)
        7. Duration of stay (important for hotel bookings)
        
        For temporal expressions, always convert them to actual dates in YYYY-MM-DD format.
        For example, if today is {current_date.strftime("%Y-%m-%d")}:
        - "tomorrow" → "{tomorrow_date}"
        - "next week" → "{next_week_date}"
        - "weekend" → "{weekend_date}"
        
        Format dates as YYYY-MM-DD. Assign confidence scores (0.0-1.0) to each extraction based on clarity.
        If a parameter isn't mentioned, don't include it in the JSON or leave its array empty.
        Your response must be valid JSON according to the schema provided.
        """
        
        # Construct LLM messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract travel parameters from this message: {message}"}
        ]
        
        # If we already detected flight parameters directly, include them in the context
        if flight_params:
            messages.append({"role": "assistant", "content": f"I've detected these flight parameters: {json.dumps(flight_params)}"})
        
        try:
            # Start with any directly extracted flight parameters
            params = flight_params.copy() if flight_params else {}
            
            # Use structured output generation
            extracted_data = None
            try:
                extracted_data = self.llm_client.generate_structured_output(
                    messages=messages,
                    output_schema=parameter_schema,
                    temperature=0.2  # Lower temperature for more deterministic results
                )
                logger.info(f"Extracted parameters: {json.dumps(extracted_data)}")
            except Exception as llm_error:
                logger.error(f"Error in LLM structured output: {str(llm_error)}")
                # Continue with any parameters we've already extracted directly
                if flight_params:
                    logger.info("Using directly extracted flight parameters only")
                else:
                    # Re-raise if we don't have any fallback parameters
                    raise
            
            # Make sure we have properly structured data for destinations/origins arrays
            if flight_params:
                if "origin" in flight_params and "origins" not in flight_params:
                    # Convert direct origin to origins array format
                    flight_params["origins"] = [{
                        "name": flight_params["origin"].get("name", ""),
                        "code": flight_params["origin"].get("code", ""),
                        "confidence": 0.9
                    }]
                
                if "destination" in flight_params and "destinations" not in flight_params:
                    # Convert direct destination to destinations array format
                    flight_params["destinations"] = [{
                        "name": flight_params["destination"].get("name", ""),
                        "code": flight_params["destination"].get("code", ""),
                        "confidence": 0.9
                    }]
                
                # Add tomorrow's date for one-way flights if mentioned
                if ("trip_type" in flight_params and flight_params["trip_type"] == "one_way" and
                    "tomorrow" in message.lower() and "dates" not in flight_params):
                    tomorrow = datetime.now() + timedelta(days=1)
                    flight_params["dates"] = [{
                        "type": "departure",
                        "start_date": tomorrow.strftime("%Y-%m-%d"),
                        "flexible": False,
                        "confidence": 0.9
                    }]
            
            # Merge directly extracted flight params with LLM results
            if flight_params and extracted_data:
                # Make sure flight params take precedence
                if "origin" in flight_params and "origins" in extracted_data:
                    # Keep origins from LLM but ensure our direct extraction is first
                    for origin in extracted_data.get("origins", []):
                        if origin.get("name") != flight_params["origin"].get("name"):
                            flight_params.setdefault("origins", []).append(origin)
                
                if "destination" in flight_params and "destinations" in extracted_data:
                    # Same for destinations
                    for dest in extracted_data.get("destinations", []):
                        if dest.get("name") != flight_params["destination"].get("name"):
                            flight_params.setdefault("destinations", []).append(dest)
                
                # Add other parameters from extracted data
                if "dates" in extracted_data:
                    flight_params["dates"] = extracted_data["dates"]
                if "travelers" in extracted_data:
                    flight_params["travelers"] = extracted_data["travelers"]
                if "budget" in extracted_data:
                    flight_params["budget"] = extracted_data["budget"]
                if "preferences" in extracted_data:
                    flight_params["preferences"] = extracted_data["preferences"]
                
                params = flight_params
            elif extracted_data:
                params = extracted_data
            else:
                params = flight_params
                
            # Post-process dates to ensure correct temporal references
            if params and "dates" in params and params["dates"]:
                post_process_date_values(params["dates"])
            
            # Always include a default traveler count
            if "travelers" not in params:
                params["travelers"] = {
                    "type": "adult",
                    "count": 1
                }
                
            return params
            
        except Exception as e:
            logger.error(f"Error in parameter extraction: {str(e)}")
            # If we have direct flight parameters, use those even if everything else failed
            if flight_params:
                logger.info("Fallback to directly extracted flight parameters")
                return flight_params
            
            # Return empty dict as last resort
            return {}
    
    def _update_state_with_parameters(self, state: TravelState, params: Dict[str, Any]) -> TravelState:
        """
        Update state with the extracted parameters.
        
        Args:
            state: The current TravelState
            params: Dictionary of extracted parameters
            
        Returns:
            Updated TravelState
        """
        # Log the parameters we're working with to help debugging
        logger.info(f"Updating state with parameters: {json.dumps(params) if params else 'None'}")
        
        # Process destinations
        if "destinations" in params and params["destinations"]:
            for dest_data in params["destinations"]:
                # Create a new location parameter
                destination = LocationParameter(
                    name=dest_data["name"],
                    type="destination",
                    confidence=dest_data.get("confidence", 0.8),
                    country=dest_data.get("country"),
                    city=dest_data.get("city"),
                    extracted_from=state.get_latest_user_query() or ""
                )
                
                # Add to state
                state.destinations.append(destination)
                state.extracted_parameters.add("destination")
                
                logger.info(f"Extracted destination: {destination.name}")
        
        # Process origins
        if "origins" in params and params["origins"]:
            for origin_data in params["origins"]:
                # Create a new location parameter
                origin = LocationParameter(
                    name=origin_data["name"],
                    type="origin",
                    confidence=origin_data.get("confidence", 0.8),
                    country=origin_data.get("country"),
                    city=origin_data.get("city"),
                    extracted_from=state.get_latest_user_query() or ""
                )
                
                # Add to state
                state.origins.append(origin)
                state.extracted_parameters.add("origin")
                
                logger.info(f"Extracted origin: {origin.name}")
                
        # Direct flight parameters (from regex pattern matching)
        if "origin" in params and isinstance(params["origin"], dict):
            origin_dict = params["origin"]
            # Skip adding origin if it's already in state to avoid duplicates
            if not any(o.name == origin_dict.get("name", "") for o in state.origins):
                state.add_origin(LocationParameter(
                    name=origin_dict.get("name", ""),
                    city=origin_dict.get("city", ""),
                    country=origin_dict.get("country", ""),
                    code=origin_dict.get("code", ""),
                    confidence=origin_dict.get("confidence", 0.9)
                ))
                logger.info(f"Added origin from flight code: {origin_dict.get('name', '')}")
            
        if "destination" in params and isinstance(params["destination"], dict):
            dest_dict = params["destination"]
            # Skip adding destination if it's already in state to avoid duplicates
            if not any(d.name == dest_dict.get("name", "") for d in state.destinations):
                state.add_destination(LocationParameter(
                    name=dest_dict.get("name", ""),
                    city=dest_dict.get("city", ""),
                    country=dest_dict.get("country", ""),
                    code=dest_dict.get("code", ""),
                    confidence=dest_dict.get("confidence", 0.9)
                ))
                logger.info(f"Added destination from flight code: {dest_dict.get('name', '')}")
                
        # For flight queries, if we have a trip type, add it to state preferences
        if "trip_type" in params:
            trip_type = params["trip_type"]
            state.add_preference(PreferenceParameter(category="trip_type", value=trip_type))
            logger.info(f"Added trip type preference: {trip_type}")
        
        # Process dates
        if "dates" in params and params["dates"]:
            for date_data in params["dates"]:
                start_date = None
                end_date = None
                
                if "start_date" in date_data and date_data["start_date"]:
                    try:
                        start_date = datetime.strptime(date_data["start_date"], "%Y-%m-%d").date()
                    except ValueError:
                        logger.warning(f"Invalid start date format: {date_data['start_date']}")
                
                if "end_date" in date_data and date_data["end_date"]:
                    try:
                        end_date = datetime.strptime(date_data["end_date"], "%Y-%m-%d").date()
                    except ValueError:
                        logger.warning(f"Invalid end date format: {date_data['end_date']}")
                
                # Create a new date parameter
                date_param = DateParameter(
                    type=date_data.get("type", "departure"),
                    date_range=date_data.get("date_range", False),
                    start_date=start_date,
                    end_date=end_date,
                    flexible=date_data.get("flexible", False),
                    confidence=date_data.get("confidence", 0.8),
                    extracted_from=state.get_latest_user_query() or ""
                )
                
                # Add to state
                state.dates.append(date_param)
                state.extracted_parameters.add("dates")
                
                date_info = f"{start_date} to {end_date}" if end_date else start_date
                logger.info(f"Extracted dates: {date_info}")
        
        # Process travelers
        if "travelers" in params and params["travelers"]:
            travelers_data = params["travelers"]
            
            # Create or update traveler parameter
            if state.travelers:
                # Update existing
                state.travelers.adults = travelers_data.get("adults", state.travelers.adults)
                state.travelers.children = travelers_data.get("children", state.travelers.children)
                state.travelers.infants = travelers_data.get("infants", state.travelers.infants)
                state.travelers.update_total()
                state.travelers.update_confidence(travelers_data.get("confidence", 0.8))
            else:
                # Create new
                state.travelers = TravelerParameter(
                    adults=travelers_data.get("adults", 1),
                    children=travelers_data.get("children", 0),
                    infants=travelers_data.get("infants", 0),
                    confidence=travelers_data.get("confidence", 0.8),
                    extracted_from=state.get_latest_user_query() or ""
                )
                state.travelers.update_total()
            
            state.extracted_parameters.add("travelers")
            logger.info(f"Extracted travelers: {state.travelers.total} total")
        
        # Process budget
        if "budget" in params and params["budget"]:
            budget_data = params["budget"]
            
            # Create or update budget parameter
            if state.budget:
                # Update existing
                state.budget.min_value = budget_data.get("min_value", state.budget.min_value)
                state.budget.max_value = budget_data.get("max_value", state.budget.max_value)
                state.budget.currency = budget_data.get("currency", state.budget.currency)
                state.budget.type = budget_data.get("type", state.budget.type)
                state.budget.update_confidence(budget_data.get("confidence", 0.8))
            else:
                # Create new
                state.budget = BudgetParameter(
                    min_value=budget_data.get("min_value"),
                    max_value=budget_data.get("max_value"),
                    currency=budget_data.get("currency", "USD"),
                    type=budget_data.get("type", "total"),
                    confidence=budget_data.get("confidence", 0.8),
                    extracted_from=state.get_latest_user_query() or ""
                )
            
            state.extracted_parameters.add("budget")
            
            budget_info = f"{state.budget.min_value}-{state.budget.max_value} {state.budget.currency}"
            logger.info(f"Extracted budget: {budget_info}")
        
        # Process preferences
        if "preferences" in params and params["preferences"]:
            for pref_data in params["preferences"]:
                # Create a new preference parameter
                preference = PreferenceParameter(
                    category=pref_data["category"],
                    preferences=pref_data.get("preferences", []),
                    exclusions=pref_data.get("exclusions", []),
                    confidence=pref_data.get("confidence", 0.8),
                    extracted_from=state.get_latest_user_query() or ""
                )
                
                # Add to state
                state.preferences.append(preference)
                state.extracted_parameters.add("preferences")
                
                logger.info(f"Extracted preferences for {preference.category}: {preference.preferences}")
        
        # Update missing parameters
        missing = state.get_missing_parameters()
        state.missing_parameters = set(missing)
        
        return state
