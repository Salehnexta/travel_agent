"""
Main application entry point for the enhanced travel agent.
Integrates all enhanced features with a Flask API.
"""

import os
import logging
import json
from uuid import uuid4
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS

from travel_agent.state_definitions import TravelState
from travel_agent.graph_builder_enhanced import create_enhanced_travel_agent_graph
from travel_agent.config.env_manager import get_env_manager
from travel_agent.config.redis_client import RedisManager
from travel_agent.error_tracking import error_tracker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("travel_agent_app")

# Initialize app
app = Flask(__name__)
CORS(app)

# Get environment manager
env_manager = get_env_manager()

# Initialize Redis client
redis_manager = RedisManager()

# Initialize travel agent graph with Redis persistence if available
use_redis = bool(env_manager.get("REDIS_URL"))
travel_agent = create_enhanced_travel_agent_graph(use_redis=use_redis)


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    # Check if required API keys are configured
    api_statuses = {
        "deepseek": bool(env_manager.get_api_key("deepseek")),
        "groq": bool(env_manager.get_api_key("groq")),
        "serper": bool(env_manager.get_api_key("serper")),
    }
    
    # Check Redis connection
    redis_status = "ok"
    try:
        redis_manager.ping()
    except Exception as e:
        redis_status = str(e)
    
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "environment": env_manager.environment,
        "api_statuses": api_statuses,
        "redis_status": redis_status
    })


@app.route("/api/chat/start", methods=["POST"])
def start_chat():
    """Start a new chat session."""
    try:
        # Generate a session ID or use provided one
        data = request.json or {}
        session_id = data.get("session_id") or str(uuid4())
        
        # Create a new session
        state = travel_agent.create_session(session_id)
        
        # Prepare response
        initial_message = state.conversation_history[-1]["content"] if state.conversation_history else ""
        
        return jsonify({
            "session_id": session_id,
            "message": initial_message
        })
    except Exception as e:
        error_id = error_tracker.track_error(e, {"endpoint": "start_chat"})
        logger.error(f"Error starting chat: {str(e)} (Error ID: {error_id})")
        return jsonify({
            "error": "Failed to start chat session",
            "error_id": error_id
        }), 500


@app.route("/api/chat/<session_id>/message", methods=["POST"])
def send_message(session_id):
    """Send a message to the travel agent."""
    try:
        # Get message from request
        data = request.json or {}
        user_message = data.get("message", "")
        
        if not user_message:
            return jsonify({"error": "Message is required"}), 400
        
        # Try to get existing state from Redis or create new
        state = None
        try:
            state_data = redis_manager.get_json(f"travel_agent:state:{session_id}")
            if state_data:
                state = TravelState.model_validate(state_data)
                logger.info(f"Retrieved existing session {session_id}")
        except Exception as e:
            logger.warning(f"Error retrieving session {session_id}: {str(e)}")
        
        # If state not found, create new session
        if not state:
            state = travel_agent.create_session(session_id)
            logger.info(f"Created new session {session_id}")
        
        # Process the message
        updated_state = travel_agent.process_message(state, user_message)
        
        # Extract last assistant message
        assistant_message = ""
        if updated_state.conversation_history:
            for message in reversed(updated_state.conversation_history):
                if message.get("role") == "assistant":
                    assistant_message = message.get("content", "")
                    break
        
        # Prepare response data
        response_data = {
            "session_id": session_id,
            "message": assistant_message,
            "stage": updated_state.conversation_stage
        }
        
        # Add search results if available
        if updated_state.search_results:
            response_data["search_results"] = {
                category: [r.model_dump() for r in results][:3]  # Limit to 3 results per category
                for category, results in updated_state.search_results.items()
            }
        
        # Add debug info in development
        if env_manager.is_development():
            response_data["debug"] = {
                "extracted_parameters": list(updated_state.extracted_parameters),
                "missing_parameters": list(updated_state.missing_parameters),
                "destinations": [d.model_dump() for d in updated_state.destinations],
                "origins": [o.model_dump() for o in updated_state.origins],
                "dates": [d.model_dump() for d in updated_state.dates]
            }
        
        return jsonify(response_data)
    
    except Exception as e:
        error_id = error_tracker.track_error(e, {"endpoint": "send_message", "session_id": session_id})
        logger.error(f"Error processing message: {str(e)} (Error ID: {error_id})")
        return jsonify({
            "error": "Failed to process message",
            "error_id": error_id,
            "message": "I'm sorry, but I encountered an error processing your request. Please try again later."
        }), 500


if __name__ == "__main__":
    # Determine port (default to 5001 to avoid conflicts with AirPlay on macOS)
    port = int(env_manager.get("PORT", 5001))
    
    # Log startup information
    logger.info(f"Starting Travel Agent API on port {port}")
    logger.info(f"Environment: {env_manager.environment}")
    logger.info(f"Redis available: {use_redis}")
    
    # Run the app
    app.run(host="0.0.0.0", port=port, debug=env_manager.is_development())
