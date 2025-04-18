"""
LangGraph-based Travel Agent Workflow

This module implements a proper LangGraph workflow for the travel agent,
following LangGraph best practices.
"""
import os
import logging
from typing import Dict, Any, List, TypedDict, Annotated
from enum import Enum

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, FunctionMessage
from langchain_core.output_parsers import JsonOutputParser
from travel_agent.state_definitions import TravelState, ConversationStage

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define workflow state
class WorkflowState(TypedDict):
    """State that is passed between nodes in the graph."""
    messages: List[Dict[str, Any]]
    travel_state: Dict[str, Any]
    current_stage: str
    parameters: Dict[str, Any]
    search_results: Dict[str, Any]
    next_stage: str

# Define workflow stages
class WorkflowStage(str, Enum):
    """Stages in the travel agent workflow."""
    GREETING = "greeting"
    INTENT_RECOGNITION = "intent_recognition"
    PARAMETER_EXTRACTION = "parameter_extraction"
    SEARCH_EXECUTION = "search_execution"
    RESPONSE_GENERATION = "response_generation"
    FOLLOW_UP = "follow_up"
    ERROR_HANDLING = "error_handling"
    END = "end"

# Define node functions
def greeting(state: WorkflowState) -> WorkflowState:
    """Generate an initial greeting for the user."""
    logger.info("Executing greeting node")
    # Implementation would connect to LLM for greeting generation
    state["messages"].append({
        "role": "assistant", 
        "content": "Hello! I'm your AI travel assistant. How can I help you plan your next trip?"
    })
    # Skip intent recognition for initial greeting, just wait for user input
    state["next_stage"] = WorkflowStage.END
    return state

def recognize_intent(state: WorkflowState) -> WorkflowState:
    """Recognize the user's intent from their message."""
    logger.info("Executing intent recognition node")
    # Get the last user message
    last_message = next((m for m in reversed(state["messages"]) if m["role"] == "user"), None)
    if not last_message:
        logger.warning("No user message found, ending conversation")
        state["next_stage"] = WorkflowStage.END
        return state
    
    # Implementation would connect to LLM for intent recognition
    # For now, we'll use a simple rule-based approach
    message = last_message["content"].lower()
    
    if any(word in message for word in ["plan", "book", "travel", "trip", "vacation"]):
        state["next_stage"] = WorkflowStage.PARAMETER_EXTRACTION
    elif any(word in message for word in ["hotel", "flight", "price", "cost"]):
        state["next_stage"] = WorkflowStage.SEARCH_EXECUTION
    elif any(word in message for word in ["thank", "thanks", "appreciate"]):
        state["next_stage"] = WorkflowStage.FOLLOW_UP
    elif any(word in message for word in ["goodbye", "bye"]):
        state["next_stage"] = WorkflowStage.END
    else:
        state["next_stage"] = WorkflowStage.PARAMETER_EXTRACTION
    
    return state

def extract_parameters(state: WorkflowState) -> WorkflowState:
    """Extract travel parameters from the user's message."""
    logger.info("Executing parameter extraction node")
    # Implementation would connect to LLM for parameter extraction
    # For now, we'll use a simple extraction demo
    
    # Get the last user message
    last_message = next((m for m in reversed(state["messages"]) if m["role"] == "user"), None)
    if not last_message:
        state["next_stage"] = WorkflowStage.ERROR_HANDLING
        return state
    
    message = last_message["content"].lower()
    
    # Simple parameter extraction
    if "paris" in message:
        state["parameters"]["destination"] = "Paris, France"
    if "next month" in message:
        state["parameters"]["dates"] = "Next month"
    if any(num in message for num in ["1", "2", "3", "4", "5", "6", "7"]):
        for num in ["1", "2", "3", "4", "5", "6", "7"]:
            if num in message and "day" in message:
                state["parameters"]["duration"] = f"{num} days"
    
    # Determine if we have enough parameters to proceed
    if "destination" in state["parameters"]:
        state["next_stage"] = WorkflowStage.SEARCH_EXECUTION
    else:
        # Ask for missing parameters
        state["messages"].append({
            "role": "assistant", 
            "content": "To help plan your trip, I need to know where you'd like to go. Could you please tell me your desired destination?"
        })
        state["next_stage"] = WorkflowStage.INTENT_RECOGNITION
    
    return state

def execute_search(state: WorkflowState) -> WorkflowState:
    """Execute search for travel options."""
    logger.info("Executing search node")
    # Implementation would connect to search API
    # For demo, we'll use mock data
    
    destination = state["parameters"].get("destination", "")
    if not destination:
        state["next_stage"] = WorkflowStage.PARAMETER_EXTRACTION
        return state
    
    # Mock search results
    state["search_results"] = {
        "hotels": [
            {"name": "Grand Hotel Paris", "rating": 4.7, "price": "$250/night", "location": "City Center"},
            {"name": "Luxury Suites", "rating": 4.5, "price": "$180/night", "location": "Near Eiffel Tower"},
        ],
        "flights": [
            {"airline": "Air France", "departure": "New York", "arrival": "Paris", "price": "$750"},
            {"airline": "Delta", "departure": "New York", "arrival": "Paris", "price": "$820"},
        ]
    }
    
    state["next_stage"] = WorkflowStage.RESPONSE_GENERATION
    return state

def generate_response(state: WorkflowState) -> WorkflowState:
    """Generate a response based on the current state."""
    logger.info("Executing response generation node")
    # Implementation would connect to LLM for response generation
    
    # For now, use a template-based approach
    if "search_results" in state and state["search_results"]:
        hotels = state["search_results"].get("hotels", [])
        flights = state["search_results"].get("flights", [])
        
        response = f"I found some options for your trip to {state['parameters'].get('destination', 'your destination')}.\n\n"
        
        if hotels:
            response += "Hotels:\n"
            for hotel in hotels:
                response += f"- {hotel['name']}: {hotel['rating']} stars, {hotel['price']}, {hotel['location']}\n"
        
        if flights:
            response += "\nFlights:\n"
            for flight in flights:
                response += f"- {flight['airline']}: {flight['departure']} to {flight['arrival']}, {flight['price']}\n"
        
        response += "\nWould you like more details about any of these options?"
    else:
        response = "I'm processing your request. Could you provide more details about your travel plans?"
    
    state["messages"].append({"role": "assistant", "content": response})
    state["next_stage"] = WorkflowStage.FOLLOW_UP
    return state

def handle_follow_up(state: WorkflowState) -> WorkflowState:
    """Handle follow-up from the user."""
    logger.info("Executing follow-up node")
    # Decide whether to end or continue
    last_message = next((m for m in reversed(state["messages"]) if m["role"] == "user"), None)
    if not last_message:
        state["next_stage"] = WorkflowStage.END
        return state
    
    message = last_message["content"].lower()
    if any(word in message for word in ["thanks", "thank", "goodbye", "bye"]):
        state["messages"].append({
            "role": "assistant", 
            "content": "You're welcome! Feel free to come back if you need more help planning your trip."
        })
        state["next_stage"] = WorkflowStage.END
    else:
        state["next_stage"] = WorkflowStage.INTENT_RECOGNITION
    
    return state

def handle_error(state: WorkflowState) -> WorkflowState:
    """Handle errors in the workflow."""
    logger.info("Executing error handling node")
    
    # Track error count to prevent infinite loops
    state["error_count"] = state.get("error_count", 0) + 1
    
    state["messages"].append({
        "role": "assistant", 
        "content": "I apologize, but I encountered an issue processing your request. Could you please rephrase or provide more details?"
    })
    
    # After 3 errors, exit the conversation
    if state["error_count"] > 2:
        state["next_stage"] = WorkflowStage.END
    else:
        state["next_stage"] = WorkflowStage.INTENT_RECOGNITION
    
    return state

def router(state: WorkflowState) -> str:
    """Route to the next node based on the current state."""
    next_stage = state["next_stage"]
    
    # Safety check to prevent infinite recursion
    if next_stage == WorkflowStage.ERROR_HANDLING and state.get("error_count", 0) > 2:
        logger.warning("Too many errors encountered, ending conversation")
        return WorkflowStage.END
    
    return next_stage

def create_travel_agent_workflow() -> StateGraph:
    """Create the travel agent workflow graph."""
    # Initialize the workflow graph
    workflow = StateGraph(WorkflowState)
    
    # Add nodes to the graph
    workflow.add_node(WorkflowStage.GREETING, greeting)
    workflow.add_node(WorkflowStage.INTENT_RECOGNITION, recognize_intent)
    workflow.add_node(WorkflowStage.PARAMETER_EXTRACTION, extract_parameters)
    workflow.add_node(WorkflowStage.SEARCH_EXECUTION, execute_search)
    workflow.add_node(WorkflowStage.RESPONSE_GENERATION, generate_response)
    workflow.add_node(WorkflowStage.FOLLOW_UP, handle_follow_up)
    workflow.add_node(WorkflowStage.ERROR_HANDLING, handle_error)
    
    # Set the entry point
    workflow.set_entry_point(WorkflowStage.GREETING)
    
    # Add conditional edges
    workflow.add_conditional_edges(
        WorkflowStage.GREETING,
        router,
        {
            WorkflowStage.INTENT_RECOGNITION: WorkflowStage.INTENT_RECOGNITION,
            WorkflowStage.ERROR_HANDLING: WorkflowStage.ERROR_HANDLING
        }
    )
    
    workflow.add_conditional_edges(
        WorkflowStage.INTENT_RECOGNITION,
        router,
        {
            WorkflowStage.PARAMETER_EXTRACTION: WorkflowStage.PARAMETER_EXTRACTION,
            WorkflowStage.SEARCH_EXECUTION: WorkflowStage.SEARCH_EXECUTION,
            WorkflowStage.FOLLOW_UP: WorkflowStage.FOLLOW_UP,
            WorkflowStage.END: END,
            WorkflowStage.ERROR_HANDLING: WorkflowStage.ERROR_HANDLING
        }
    )
    
    workflow.add_conditional_edges(
        WorkflowStage.PARAMETER_EXTRACTION,
        router,
        {
            WorkflowStage.SEARCH_EXECUTION: WorkflowStage.SEARCH_EXECUTION,
            WorkflowStage.INTENT_RECOGNITION: WorkflowStage.INTENT_RECOGNITION,
            WorkflowStage.ERROR_HANDLING: WorkflowStage.ERROR_HANDLING
        }
    )
    
    workflow.add_conditional_edges(
        WorkflowStage.SEARCH_EXECUTION,
        router,
        {
            WorkflowStage.RESPONSE_GENERATION: WorkflowStage.RESPONSE_GENERATION,
            WorkflowStage.PARAMETER_EXTRACTION: WorkflowStage.PARAMETER_EXTRACTION,
            WorkflowStage.ERROR_HANDLING: WorkflowStage.ERROR_HANDLING
        }
    )
    
    workflow.add_conditional_edges(
        WorkflowStage.RESPONSE_GENERATION,
        router,
        {
            WorkflowStage.FOLLOW_UP: WorkflowStage.FOLLOW_UP,
            WorkflowStage.ERROR_HANDLING: WorkflowStage.ERROR_HANDLING
        }
    )
    
    workflow.add_conditional_edges(
        WorkflowStage.FOLLOW_UP,
        router,
        {
            WorkflowStage.INTENT_RECOGNITION: WorkflowStage.INTENT_RECOGNITION,
            WorkflowStage.END: END,
            WorkflowStage.ERROR_HANDLING: WorkflowStage.ERROR_HANDLING
        }
    )
    
    workflow.add_conditional_edges(
        WorkflowStage.ERROR_HANDLING,
        router,
        {
            WorkflowStage.INTENT_RECOGNITION: WorkflowStage.INTENT_RECOGNITION,
            WorkflowStage.END: END
        }
    )
    
    # Compile the graph
    return workflow.compile()

class TravelAgentGraphLang:
    """
    LangGraph implementation of the Travel Agent workflow.
    """
    
    def __init__(self):
        """Initialize the travel agent graph."""
        self.graph = create_travel_agent_workflow()
        logger.info("Travel Agent LangGraph initialized")
    
    def create_session(self, session_id: str = None) -> Dict[str, Any]:
        """
        Create a new session with initial state.
        
        Args:
            session_id: Optional session ID
            
        Returns:
            Initial state dictionary
        """
        # Create initial state
        state = {
            "messages": [],
            "travel_state": {},
            "current_stage": WorkflowStage.GREETING,
            "parameters": {},
            "search_results": {},
            "next_stage": WorkflowStage.GREETING,
            "error_count": 0
        }
        
        # Generate greeting directly without running through graph yet
        state["messages"].append({
            "role": "assistant", 
            "content": "Hello! I'm your AI travel assistant. How can I help you plan your next trip?"
        })
        
        return state
    
    def process_message(self, state: Dict[str, Any], user_message: str) -> Dict[str, Any]:
        """
        Process a user message through the agent workflow.
        
        Args:
            state: Current state dictionary
            user_message: Message from the user
            
        Returns:
            Updated state after processing
        """
        # Add user message to state
        state["messages"].append({"role": "user", "content": user_message})
        
        # Reset the next stage to intent recognition to start processing
        state["next_stage"] = WorkflowStage.INTENT_RECOGNITION
        
        try:
            # Process the message through the graph
            return self.graph.invoke(state)
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            # Handle error gracefully
            state["messages"].append({
                "role": "assistant", 
                "content": "I apologize, but I encountered an issue processing your request. Let's start over."
            })
            return state
    
    def get_latest_assistant_response(self, state: Dict[str, Any]) -> str:
        """Get the latest assistant response from the state."""
        for message in reversed(state["messages"]):
            if message["role"] == "assistant":
                return message["content"]
        return ""
