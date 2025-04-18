import logging
from typing import Dict, Any, List
import json

from travel_agent.state_definitions import TravelState, ConversationStage
from travel_agent.llm_provider import LLMClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class IntentRecognitionAgent:
    """
    Agent responsible for identifying user intent from messages.
    Determines what the user is trying to accomplish.
    """
    
    def __init__(self):
        """Initialize the intent recognition agent with an LLM client."""
        self.llm_client = LLMClient()
        logger.info("Intent Recognition Agent initialized")
    
    def process(self, state: TravelState) -> TravelState:
        """
        Process the user's message to identify intent.
        
        Args:
            state: The current TravelState
            
        Returns:
            Updated TravelState with recognized intent
        """
        # Get the latest user message
        user_message = state.get_latest_user_query()
        if not user_message:
            return state
        
        # Get recent conversation context
        conversation_context = state.get_conversation_context(num_messages=3)
        
        # Identify intent using LLM
        intent = self._identify_intent(user_message, conversation_context)
        
        # Update state based on identified intent
        logger.info(f"Identified intent: {intent['intent']}")
        
        if intent["intent"] == "book_trip":
            # User wants to book or plan a trip
            
            # Check if it's a flight query with direct parameters
            user_message = state.get_latest_user_query()
            if "flight" in user_message.lower() and (" to " in user_message.lower() or "from" in user_message.lower()):
                # This looks like a direct flight query with parameters - prioritize parameter extraction
                logger.info("Direct flight query detected with parameters")
                
            # Move to parameter extraction
            state.update_conversation_stage(ConversationStage.PARAMETER_EXTRACTION)
            
        elif intent["intent"] == "get_information":
            # User is asking for information about a place or travel-related topic
            if intent.get("requires_search", True):
                state.update_conversation_stage(ConversationStage.SEARCH_EXECUTION)
            else:
                state.update_conversation_stage(ConversationStage.RESPONSE_GENERATION)
            
        elif intent["intent"] == "modify_parameters":
            # User is updating or changing travel parameters
            state.update_conversation_stage(ConversationStage.PARAMETER_EXTRACTION)
            
        elif intent["intent"] == "compare_options":
            # User wants to compare different travel options
            state.update_conversation_stage(ConversationStage.SEARCH_EXECUTION)
            
        elif intent["intent"] == "greeting":
            # User sent a greeting
            assistant_response = "Hello! I'm your AI travel assistant. How can I help you plan your next trip?"
            state.add_message("assistant", assistant_response)
            state.update_conversation_stage(ConversationStage.FOLLOW_UP)
            
        elif intent["intent"] == "thank_you":
            # User expressed gratitude
            assistant_response = "You're welcome! Is there anything else I can help you with for your trip?"
            state.add_message("assistant", assistant_response)
            state.update_conversation_stage(ConversationStage.FOLLOW_UP)
            
        elif intent["intent"] == "goodbye":
            # User is ending the conversation
            assistant_response = "It was great helping you with your travel plans. Feel free to come back anytime you need assistance with your travels!"
            state.add_message("assistant", assistant_response)
            state.update_conversation_stage(ConversationStage.FOLLOW_UP)
            
        else:
            # Default to parameter extraction for unrecognized intents
            state.update_conversation_stage(ConversationStage.PARAMETER_EXTRACTION)
        
        return state
    
    def _identify_intent(self, message: str, conversation_context: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Identify the user's intent from their message using LLM.
        
        Args:
            message: The user's message
            conversation_context: Recent conversation history
            
        Returns:
            Dictionary with intent details
        """
        # Define the intent recognition schema
        intent_schema = {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "enum": [
                        "book_trip",          # User wants to book or plan a trip
                        "get_information",    # User is asking for information
                        "modify_parameters",  # User is changing trip parameters
                        "compare_options",    # User wants to compare options
                        "greeting",           # User sent a greeting
                        "thank_you",          # User expressed gratitude
                        "goodbye",            # User is ending the conversation
                        "other"               # Unrecognized intent
                    ]
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1
                },
                "requires_search": {
                    "type": "boolean"
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "destination",
                        "hotel",
                        "flight",
                        "activity",
                        "general",
                        "none"
                    ]
                }
            },
            "required": ["intent", "confidence"]
        }
        
        # Create system prompt
        system_prompt = """
        You are an AI assistant specialized in travel planning. Analyze the user's message and identify their intent.
        Respond with a JSON object that categorizes the intent according to the schema.
        
        For example:
        - If the user says "I want to go to Paris next month", classify as "book_trip"
        - If the user says "find me flight from dmm to ruh tomorrow one way", classify as "book_trip" with category "flight"
        - If the user mentions airport codes like JFK, LAX, DMM, RUH, etc., these are locations and should be recognized as part of a "book_trip" intent
        - If the user asks "What are the best hotels in Tokyo?", classify as "get_information" with category "hotel"
        - If the user says "Actually, make that 2 adults and 1 child", classify as "modify_parameters"
        
        Your response must be valid JSON.
        """
        
        # Prepare the messages for the LLM
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add conversation context
        for message_dict in conversation_context:
            messages.append(message_dict)
        
        try:
            # Use structured output generation
            intent_data = self.llm_client.generate_structured_output(
                messages=messages,
                output_schema=intent_schema,
                temperature=0.2  # Lower temperature for more deterministic results
            )
            
            return intent_data
            
        except Exception as e:
            logger.error(f"Error in intent recognition: {str(e)}")
            
            # Fallback to a default intent if LLM fails
            return {
                "intent": "book_trip",
                "confidence": 0.5,
                "requires_search": True,
                "category": "general"
            }
