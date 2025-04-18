"""
Simplified LangGraph-based Travel Agent Workflow

This module implements a basic but functional LangGraph workflow for the travel agent,
following current LangGraph best practices.
"""
import os
import logging
from typing import Dict, Any, List, TypedDict, Annotated, Tuple
from enum import Enum

from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define workflow state
class WorkflowState(TypedDict):
    """State that is passed between nodes in the graph."""
    messages: List[Dict[str, str]]
    parameters: Dict[str, Any]
    search_results: Dict[str, Any]
    current_node: str

# Define the agent functions
def intent_recognition(state: WorkflowState) -> Tuple[WorkflowState, str]:
    """
    Analyze the user's message to determine intent.
    Returns the updated state and the next node to call.
    """
    logger.info("Processing intent recognition")
    
    # Get the latest user message
    last_message = next((m for m in reversed(state["messages"]) if m["role"] == "user"), None)
    
    # Simple intent recognition logic
    if last_message:
        message_text = last_message["content"].lower()
        
        # Check for keywords
        if any(word in message_text for word in ["paris", "france", "travel", "trip"]):
            response = "I see you're interested in traveling to Paris! It's a beautiful city. When are you planning to visit?"
            next_node = "parameter_extraction"
        elif any(word in message_text for word in ["hotel", "stay", "accommodation"]):
            response = "I'd be happy to help you find hotels. Could you tell me your preferred location and budget?"
            next_node = "search" 
        elif any(word in message_text for word in ["thank", "thanks"]):
            response = "You're welcome! It was my pleasure to help with your travel plans. Is there anything else you'd like to know?"
            next_node = "end"
        else:
            response = "I'm your AI travel assistant. How can I help you plan your trip today?"
            next_node = "parameter_extraction"
    else:
        response = "Hello! I'm your AI travel assistant. How can I help you plan your next trip?"
        next_node = "end"
    
    # Add response to messages
    state["messages"].append({"role": "assistant", "content": response})
    state["current_node"] = next_node
    
    return state, next_node

def parameter_extraction(state: WorkflowState) -> Tuple[WorkflowState, str]:
    """
    Extract travel parameters from the conversation.
    Returns the updated state and the next node to call.
    """
    logger.info("Processing parameter extraction")
    
    # Get the latest user message
    last_message = next((m for m in reversed(state["messages"]) if m["role"] == "user"), None)
    
    if not last_message:
        return state, "end"
    
    message_text = last_message["content"].lower()
    
    # Simple parameter extraction
    if "paris" in message_text:
        state["parameters"]["destination"] = "Paris, France"
    
    if any(num in message_text for num in ["5", "five"]) and "day" in message_text:
        state["parameters"]["duration"] = "5 days"
    
    if "next month" in message_text:
        state["parameters"]["dates"] = "next month"
    
    # Check if we have enough parameters to proceed to search
    if "destination" in state["parameters"]:
        response = f"Great! I'll help you plan your trip to {state['parameters']['destination']}. "
        if "duration" in state["parameters"]:
            response += f"I see you want to stay for {state['parameters']['duration']}. "
        if "dates" in state["parameters"]:
            response += f"You're planning to travel {state['parameters']['dates']}. "
        
        response += "Would you like me to find hotels or suggest activities?"
        next_node = "search"
    else:
        response = "To help you better, could you please tell me where you'd like to travel?"
        next_node = "parameter_extraction"
    
    # Add response to messages
    state["messages"].append({"role": "assistant", "content": response})
    state["current_node"] = next_node
    
    return state, next_node

def search(state: WorkflowState) -> Tuple[WorkflowState, str]:
    """
    Perform search for travel information.
    Returns the updated state and the next node to call.
    """
    logger.info("Processing search")
    
    # Check if we have necessary parameters
    destination = state["parameters"].get("destination")
    if not destination:
        state["messages"].append({"role": "assistant", "content": "I need to know your destination before I can search for options."})
        return state, "parameter_extraction"
    
    # Mock search results
    state["search_results"] = {
        "hotels": [
            {"name": "Grand Hotel Paris", "rating": 4.7, "price": "$250/night", "location": "City Center"},
            {"name": "Luxury Suites", "rating": 4.5, "price": "$180/night", "location": "Near Eiffel Tower"},
        ],
        "attractions": [
            {"name": "Eiffel Tower", "rating": 4.8, "price": "€17.10", "type": "Landmark"},
            {"name": "Louvre Museum", "rating": 4.7, "price": "€17", "type": "Museum"},
        ]
    }
    
    # Format results
    response = f"Here are some options for your trip to {destination}:\n\n"
    
    # Add hotel information
    response += "Hotels:\n"
    for hotel in state["search_results"]["hotels"]:
        response += f"- {hotel['name']}: {hotel['rating']} stars, {hotel['price']}, {hotel['location']}\n"
    
    # Add attraction information
    response += "\nPopular Attractions:\n"
    for attraction in state["search_results"]["attractions"]:
        response += f"- {attraction['name']}: {attraction['rating']} stars, {attraction['price']}, {attraction['type']}\n"
    
    response += "\nWould you like more specific information about any of these options?"
    
    # Add response to messages
    state["messages"].append({"role": "assistant", "content": response})
    state["current_node"] = "end"
    
    return state, "end"

# Define edge routing function
def router(state: WorkflowState) -> str:
    """Route to the next node based on current_node field."""
    return state["current_node"]

# Define the LangGraph workflow
def create_workflow():
    """Create and compile the LangGraph workflow."""
    # Create the graph
    workflow = StateGraph(WorkflowState)
    
    # Add nodes
    workflow.add_node("intent_recognition", intent_recognition)
    workflow.add_node("parameter_extraction", parameter_extraction)
    workflow.add_node("search", search)
    
    # Set entry point
    workflow.set_entry_point("intent_recognition")
    
    # Add conditional edges using the router function
    workflow.add_conditional_edges(
        "intent_recognition",
        router,
        {
            "parameter_extraction": "parameter_extraction",
            "search": "search",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "parameter_extraction",
        router,
        {
            "parameter_extraction": "parameter_extraction",
            "search": "search",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "search",
        router,
        {
            "parameter_extraction": "parameter_extraction",
            "end": END
        }
    )
    
    # Compile the graph
    return workflow.compile()

class TravelAgentSimple:
    """Simple LangGraph-based Travel Agent."""
    
    def __init__(self):
        """Initialize the Travel Agent."""
        self.graph = create_workflow()
        logger.info("Simple Travel Agent LangGraph initialized")
    
    def create_session(self) -> Dict[str, Any]:
        """Create a new session with initial state."""
        # Initialize state
        state = {
            "messages": [],
            "parameters": {},
            "search_results": {},
            "current_node": "intent_recognition"
        }
        
        # Add initial greeting
        state["messages"].append({
            "role": "assistant", 
            "content": "Hello! I'm your AI travel assistant. How can I help you plan your next trip?"
        })
        
        return state
    
    def process_message(self, state: Dict[str, Any], user_message: str) -> Dict[str, Any]:
        """Process a user message and update the state."""
        # Add user message to state
        state["messages"].append({"role": "user", "content": user_message})
        
        try:
            # Process through the graph
            result = self.graph.invoke(state)
            return result
        except Exception as e:
            logger.error(f"Error in workflow: {str(e)}")
            # Add error message
            state["messages"].append({
                "role": "assistant", 
                "content": "I'm sorry, I encountered an issue. Let's try a different approach. How can I help with your travel plans?"
            })
            return state
    
    def get_latest_response(self, state: Dict[str, Any]) -> str:
        """Get the latest assistant response."""
        for message in reversed(state["messages"]):
            if message["role"] == "assistant":
                return message["content"]
        return ""
