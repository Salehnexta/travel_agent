"""
Minimal LangGraph-based Travel Agent Workflow

This module implements a simple but working LangGraph workflow for the travel agent,
following current LangGraph best practices.
"""
import logging
from typing import Dict, Any, List, TypedDict, Annotated, Literal
from enum import Enum

from langgraph.graph import StateGraph, END

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define the state type
class State(TypedDict):
    """The state of the agent."""
    messages: List[Dict[str, str]]
    next: str
    parameters: Dict[str, Any]
    search_results: Dict[str, Any]

# Define node names
GREETING = "greeting"
INTENT = "intent"
PARAMETER = "parameter"
SEARCH = "search"
RESPONSE = "response"

# Define the node functions that operate on the state
def greeting(state: State) -> State:
    """Generate a greeting message."""
    logger.info("Running greeting node")
    state["messages"].append({
        "role": "assistant",
        "content": "Hello! I'm your travel assistant. How can I help you plan your trip?"
    })
    state["next"] = INTENT
    return state

def intent_recognition(state: State) -> State:
    """Recognize user intent."""
    logger.info("Running intent recognition node")
    
    # Get the last message
    if not state["messages"] or len(state["messages"]) < 2:
        state["next"] = END
        return state
    
    last_message = state["messages"][-1]["content"].lower()
    
    # Simple intent recognition
    if any(word in last_message for word in ["paris", "france", "travel"]):
        state["parameters"]["destination"] = "Paris, France"
        state["next"] = PARAMETER
    elif any(word in last_message for word in ["hotel", "accommodation"]):
        state["next"] = SEARCH
    elif any(word in last_message for word in ["thank"]):
        state["messages"].append({
            "role": "assistant",
            "content": "You're welcome! Feel free to ask if you need more help planning your trip."
        })
        state["next"] = END
    else:
        state["next"] = PARAMETER
    
    return state

def parameter_extraction(state: State) -> State:
    """Extract travel parameters."""
    logger.info("Running parameter extraction node")
    
    last_message = state["messages"][-1]["content"].lower()
    
    # Simple parameter extraction
    if "paris" in last_message:
        state["parameters"]["destination"] = "Paris, France"
    
    if any(num in last_message for num in ["5", "five"]) and "day" in last_message:
        state["parameters"]["duration"] = "5 days"
    
    if "next month" in last_message:
        state["parameters"]["dates"] = "next month"
    
    # Respond based on extracted parameters
    response = "Thanks for the information. "
    if "destination" in state["parameters"]:
        response += f"I see you're planning to visit {state['parameters']['destination']}. "
    if "duration" in state["parameters"]:
        response += f"You're staying for {state['parameters']['duration']}. "
    if "dates" in state["parameters"]:
        response += f"You'll be traveling {state['parameters']['dates']}. "
    
    response += "Would you like me to suggest some hotels or attractions?"
    
    state["messages"].append({
        "role": "assistant",
        "content": response
    })
    
    state["next"] = SEARCH
    return state

def search_execution(state: State) -> State:
    """Search for travel options."""
    logger.info("Running search execution node")
    
    # Add mock search results
    state["search_results"] = {
        "hotels": [
            {"name": "Grand Hotel Paris", "rating": 4.7, "price": "$250/night"},
            {"name": "Eiffel View Suites", "rating": 4.5, "price": "$180/night"}
        ],
        "attractions": [
            {"name": "Eiffel Tower", "rating": 4.8, "price": "€17.10"},
            {"name": "Louvre Museum", "rating": 4.7, "price": "€17"}
        ]
    }
    
    # Format response with search results
    dest = state["parameters"].get("destination", "your destination")
    response = f"Here are some recommendations for {dest}:\n\n"
    
    response += "Hotels:\n"
    for hotel in state["search_results"]["hotels"]:
        response += f"- {hotel['name']}: {hotel['rating']} stars, {hotel['price']}\n"
    
    response += "\nAttractions:\n"
    for attraction in state["search_results"]["attractions"]:
        response += f"- {attraction['name']}: {attraction['rating']} stars, {attraction['price']}\n"
    
    response += "\nCan I help you with anything else regarding your trip?"
    
    state["messages"].append({
        "role": "assistant",
        "content": response
    })
    
    state["next"] = END
    return state

# Define the router function
def router(state: State) -> Literal["greeting", "intent", "parameter", "search", "end"]:
    """Route to the next node based on the state."""
    logger.info(f"Routing to: {state['next']}")
    return state["next"]

# Create the state graph
def create_workflow():
    """Create the workflow graph."""
    # Create the graph
    workflow = StateGraph(State)
    
    # Add nodes
    workflow.add_node(GREETING, greeting)
    workflow.add_node(INTENT, intent_recognition)
    workflow.add_node(PARAMETER, parameter_extraction)
    workflow.add_node(SEARCH, search_execution)
    
    # Set entry point
    workflow.set_entry_point(GREETING)
    
    # Add conditional edges
    workflow.add_conditional_edges(
        GREETING,
        router,
        {
            INTENT: INTENT,
            END: END
        }
    )
    
    workflow.add_conditional_edges(
        INTENT,
        router,
        {
            PARAMETER: PARAMETER,
            SEARCH: SEARCH,
            END: END
        }
    )
    
    workflow.add_conditional_edges(
        PARAMETER,
        router,
        {
            SEARCH: SEARCH,
            END: END
        }
    )
    
    workflow.add_conditional_edges(
        SEARCH,
        router,
        {
            END: END
        }
    )
    
    # Compile the graph
    return workflow.compile()

class TravelAgentMini:
    """
    Minimal LangGraph-based Travel Agent.
    """
    
    def __init__(self):
        """Initialize the Travel Agent."""
        self.graph = create_workflow()
        logger.info("Travel Agent Mini initialized")
    
    def create_session(self) -> Dict[str, Any]:
        """Create a new session and generate initial greeting."""
        state = {
            "messages": [],
            "next": GREETING,
            "parameters": {},
            "search_results": {}
        }
        return state
    
    def process_message(self, state: Dict[str, Any], message: str) -> Dict[str, Any]:
        """Process a user message."""
        # Add the user message to state
        state["messages"].append({"role": "user", "content": message})
        
        # Set the next node to intent recognition to process the message
        state["next"] = INTENT
        
        try:
            # Run the graph
            return self.graph.invoke(state)
        except Exception as e:
            logger.error(f"Error in workflow: {str(e)}")
            # Add error message
            state["messages"].append({
                "role": "assistant",
                "content": "I'm sorry, I encountered an issue processing your request."
            })
            return state
    
    def get_latest_response(self, state: Dict[str, Any]) -> str:
        """Get the latest assistant response."""
        for message in reversed(state["messages"]):
            if message["role"] == "assistant":
                return message["content"]
        return ""
