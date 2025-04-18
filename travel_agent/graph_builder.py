import logging
from typing import Dict, Any
from uuid import uuid4

from travel_agent.state_definitions import TravelState, ConversationStage
from travel_agent.agents.conversation_manager import ConversationManager
from travel_agent.agents.intent_recognition import IntentRecognitionAgent
from travel_agent.agents.parameter_extraction import ParameterExtractionAgent
from travel_agent.agents.search_manager import SearchManager
from travel_agent.agents.response_generator import ResponseGenerator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TravelAgentGraph:
    """
    Builds and manages the workflow graph for the travel agent.
    Orchestrates the transitions between different agents and stages.
    """
    
    def __init__(self):
        """Initialize the graph with all required agents."""
        # Initialize agents
        self.conversation_manager = ConversationManager()
        self.intent_recognition = IntentRecognitionAgent()
        self.parameter_extraction = ParameterExtractionAgent()
        self.search_manager = SearchManager()
        self.response_generator = ResponseGenerator()
        
        logger.info("Travel Agent Graph initialized")
    
    def create_session(self, session_id: str = None) -> TravelState:
        """
        Create a new session with initial state.
        
        Args:
            session_id: Optional session ID, generated if not provided
            
        Returns:
            Initial TravelState for the session
        """
        if not session_id:
            session_id = str(uuid4())
        
        # Create initial state
        state = TravelState(
            session_id=session_id,
            conversation_stage=ConversationStage.INITIAL_GREETING
        )
        
        # Generate initial greeting
        greeting = self.conversation_manager.generate_greeting(state)
        state.add_message("assistant", greeting)
        
        logger.info(f"Created new session with ID {session_id}")
        return state
    
    def process_message(self, state: TravelState, user_message: str) -> TravelState:
        """
        Process a user message through the agent workflow.
        
        Args:
            state: Current TravelState
            user_message: Message from the user
            
        Returns:
            Updated TravelState after processing
        """
        # Add user message to state
        state.add_message("user", user_message)
        
        # Execute workflow based on current stage
        try:
            # Identify user intent
            state = self.intent_recognition.process(state)
            
            # Extract parameters if needed
            if state.conversation_stage == ConversationStage.PARAMETER_EXTRACTION:
                state = self.parameter_extraction.process(state)
            
            # Execute search if we have minimum parameters
            if state.has_minimum_parameters() and state.conversation_stage == ConversationStage.SEARCH_EXECUTION:
                state = self.search_manager.process(state)
            
            # Generate response based on current state
            state = self.response_generator.process(state)
            
        except Exception as e:
            logger.error(f"Error in workflow execution: {str(e)}")
            state.log_error("workflow_execution", {"error": str(e), "stage": state.conversation_stage})
            state.update_conversation_stage(ConversationStage.ERROR_HANDLING)
            
            # Generate error response
            error_message = self.conversation_manager.handle_error(state)
            state.add_message("assistant", error_message)
        
        return state
    
    def get_recommended_next_steps(self, state: TravelState) -> Dict[str, Any]:
        """
        Get recommended next steps for the user based on current state.
        
        Args:
            state: Current TravelState
            
        Returns:
            Dictionary of next steps and suggestions
        """
        missing_params = state.get_missing_parameters()
        
        recommendations = {
            "missing_parameters": missing_params,
            "conversation_stage": state.conversation_stage,
            "suggestions": []
        }
        
        # Add suggestions based on current stage
        if state.conversation_stage == ConversationStage.PARAMETER_EXTRACTION:
            if "destination" in missing_params:
                recommendations["suggestions"].append("Tell me where you'd like to go")
            if "dates" in missing_params:
                recommendations["suggestions"].append("When are you planning to travel?")
        
        elif state.conversation_stage == ConversationStage.SEARCH_EXECUTION:
            recommendations["suggestions"].append("Would you like to see hotels or flights?")
        
        elif state.conversation_stage == ConversationStage.FOLLOW_UP:
            recommendations["suggestions"].append("Any other information you'd like about your trip?")
        
        return recommendations
