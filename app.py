import os
import json
import logging
import redis
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify, render_template, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv
from uuid import uuid4

from travel_agent.graph_builder import TravelAgentGraph
from travel_agent.state_definitions import TravelState
from travel_agent.config import init_limiter

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, template_folder="travel_agent/templates")
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')

# Enable CORS for all routes
CORS(app, resources={r"/*": {"origins": "*"}})

# Configure Redis with connection pooling and timeouts
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
redis_client = redis.from_url(
    redis_url,
    socket_timeout=30,
    socket_connect_timeout=30,
    retry_on_timeout=True,
    health_check_interval=30
)

# Initialize optimized rate limiter
limiter = init_limiter(app)

# Initialize the travel agent graph
agent_graph = TravelAgentGraph()


def get_or_create_session_id() -> str:
    """Get the current session ID or create a new one."""
    if 'session_id' not in session:
        session['session_id'] = str(uuid4())
    return session['session_id']


def save_state(state: TravelState) -> None:
    """Save the state to Redis."""
    try:
        # Convert state to JSON-serializable dict
        state_dict = state.dict()
        redis_client.set(f"travel_state:{state.session_id}", json.dumps(state_dict))
        redis_client.expire(f"travel_state:{state.session_id}", 60 * 60 * 24)  # Expire after 24 hours
        logger.info(f"Saved state for session {state.session_id}")
    except Exception as e:
        logger.error(f"Error saving state to Redis: {str(e)}")


def load_state(session_id: str) -> Optional[TravelState]:
    """Load the state from Redis."""
    try:
        state_json = redis_client.get(f"travel_state:{session_id}")
        if state_json:
            state_dict = json.loads(state_json)
            return TravelState.parse_obj(state_dict)
        return None
    except Exception as e:
        logger.error(f"Error loading state from Redis: {str(e)}")
        return None


@app.route('/')
def index():
    """Render the main page."""
    return render_template('frontpage.html')


@app.route('/frontpage')
def frontpage():
    """Render the new HTML native frontpage."""
    return render_template('frontpage.html')


@app.route('/api/chat', methods=['POST'])
@limiter.exempt
def chat():
    """Handle chat API endpoint."""
    try:
        data = request.json
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400
        
        user_message = data['message']
        session_id = get_or_create_session_id()
        
        # Load existing state or create new one
        state = load_state(session_id)
        if not state:
            state = agent_graph.create_session(session_id)
        
        # Process the message
        updated_state = agent_graph.process_message(state, user_message)
        
        # Save the updated state
        save_state(updated_state)
        
        # Extract the assistant's response (the last message)
        response = None
        for message in reversed(updated_state.conversation_history):
            if message['role'] == 'assistant':
                response = message['content']
                break
        
        if not response:
            return jsonify({'error': 'No response generated'}), 500
        
        # Attempt to extract flight results from the updated state
        structured_flights = []
        raw_flight_results = []
        if hasattr(updated_state, 'search_results') and 'flight' in updated_state.search_results:
            # Collect all structured and raw results from all flight search results
            for result in updated_state.search_results['flight']:
                if isinstance(result.data, dict):
                    if 'structured' in result.data:
                        structured_flights.extend(result.data['structured'])
                    if 'raw' in result.data:
                        raw_flight_results.extend(result.data['raw'])
        return jsonify({
            'response': response,
            'session_id': session_id,
            'structured_flights': structured_flights,
            'raw_flight_results': raw_flight_results
        })
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/reset', methods=['POST'])
@limiter.exempt
def reset_session():
    """Reset the user's session."""
    try:
        session_id = get_or_create_session_id()
        redis_client.delete(f"travel_state:{session_id}")
        session.pop('session_id', None)
        
        # Create a new session
        new_session_id = str(uuid4())
        session['session_id'] = new_session_id
        
        return jsonify({
            'status': 'success',
            'message': 'Session reset successfully',
            'new_session_id': new_session_id
        })
        
    except Exception as e:
        logger.error(f"Error resetting session: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/health')
@limiter.exempt
def health_check():
    """Health check endpoint for monitoring."""
    try:
        # Check Redis connection
        redis_client.ping()
        return jsonify({'status': 'healthy'}), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500


if __name__ == '__main__':
    # Check if required environment variables are set
    required_vars = ['DEEPSEEK_API_KEY', 'SERPER_API_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.warning(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.warning("Some functionality may be limited")
    
    # Run the Flask app
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    # Use port 5001 instead of 5000 to avoid conflicts with AirPlay on macOS
    port = int(os.getenv('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
