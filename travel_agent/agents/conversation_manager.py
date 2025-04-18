import logging
from typing import Dict, Any, List

from travel_agent.state_definitions import TravelState, ConversationStage
from travel_agent.llm_provider import LLMClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ConversationManager:
    """
    Manages the conversation flow, including greetings, error handling,
    and general conversational responses.
    """
    
    def __init__(self):
        """Initialize the conversation manager with an LLM client."""
        self.llm_client = LLMClient()
        logger.info("Conversation Manager initialized")
    
    def generate_greeting(self, state: TravelState) -> str:
        """
        Generate a greeting message for a new session.
        
        Args:
            state: The current TravelState
            
        Returns:
            A greeting message string
        """
        # Simple greeting without LLM for faster response
        greeting = (
            "Hello! I'm your AI travel assistant. I can help you plan trips, find flights and hotels, "
            "and provide information about destinations. How may I assist you with your travel plans today?"
        )
        
        return greeting
    
    def handle_error(self, state: TravelState) -> str:
        """
        Generate an error response based on the current state.
        
        Args:
            state: The current TravelState with error information
            
        Returns:
            An error response message
        """
        # Get the most recent error
        if state.errors:
            latest_error = state.errors[-1]
            error_type = latest_error.get("type", "unknown")
            
            if error_type == "api_error":
                return (
                    "I'm sorry, but I'm currently having trouble connecting to our travel information service. "
                    "Could you please try again in a moment?"
                )
            elif error_type == "parameter_extraction":
                return (
                    "I'm having trouble understanding some details about your trip. "
                    "Could you please provide more specific information about where and when you'd like to travel?"
                )
            elif error_type == "workflow_execution":
                return (
                    "I apologize, but I encountered an issue while processing your request. "
                    "Let's try a different approach. Could you rephrase your question or request?"
                )
        
        # Default error message
        return (
            "I apologize, but I encountered an unexpected issue. "
            "Let's start over. How can I help with your travel plans today?"
        )
    
    def generate_clarification_question(self, state: TravelState, missing_param: str) -> str:
        """
        Generate a question to clarify missing information.
        
        Args:
            state: The current TravelState
            missing_param: The parameter that needs clarification
            
        Returns:
            A clarification question
        """
        if missing_param == "destination":
            return "Where would you like to travel to?"
        elif missing_param == "dates":
            return "When are you planning to travel?"
        elif missing_param == "travelers":
            return "How many people will be traveling?"
        elif missing_param == "budget":
            return "Do you have a specific budget for this trip?"
        else:
            return f"Could you provide more information about your {missing_param}?"
    
    def generate_followup_question(self, state: TravelState) -> str:
        """
        Generate a follow-up question based on the current state.
        
        Args:
            state: The current TravelState
            
        Returns:
            A follow-up question
        """
        # Use LLM to generate a contextualized follow-up question
        system_prompt = (
            "You are a helpful travel assistant. Generate a natural follow-up question based on the "
            "conversation so far. Focus on learning more about the user's preferences or "
            "offering additional travel services that might be relevant."
        )
        
        # Prepare conversation history for the LLM
        # Only include the most recent exchanges to keep context relevant
        conversation_context = state.get_conversation_context(num_messages=5)
        
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add conversation history
        for message in conversation_context:
            messages.append(message)
        
        try:
            # Generate the follow-up question using the LLM
            follow_up = self.llm_client.generate_response(
                messages=messages,
                temperature=0.7,
                max_tokens=100
            )
            
            return follow_up
            
        except Exception as e:
            logger.error(f"Error generating follow-up question: {str(e)}")
            
            # Fallback options if LLM fails
            fallbacks = [
                "Is there anything else you'd like to know about your destination?",
                "Would you like recommendations for activities or restaurants at your destination?",
                "Can I help you with anything else for your trip?",
                "Would you like to explore hotel or flight options?"
            ]
            
            import random
            return random.choice(fallbacks)
