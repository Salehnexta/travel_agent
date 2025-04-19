"""
Debug Flask application for Travel Agent testing
Provides a simple interface to test 10 different travel queries
"""

import os
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Load environment variables 
load_dotenv()

# Import search tools and parsers
from travel_agent.search_tools import SearchToolManager
from travel_agent.search_result_parser import SearchResultParser
from travel_agent.agents.parameter_extraction import ParameterExtractionAgent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize components
search_tool = SearchToolManager()
parameter_agent = ParameterExtractionAgent()

# Create Flask app
app = Flask(__name__)

# Mock TravelState class for parameter extraction
class MockTravelState:
    def __init__(self, user_query):
        self.query = user_query
        self.conversation_history = [{"role": "user", "content": user_query}]
    
    def get_conversation_context(self, num_messages=5):
        return self.conversation_history
    
    def get_latest_user_query(self):
        return self.query

# Test queries
test_examples = [
    {"id": 1, "query": "Find me a flight from DMM to RUH tomorrow", "type": "flight", "description": "Basic next-day flight"},
    {"id": 2, "query": "I need a hotel in Riyadh for this weekend", "type": "hotel", "description": "Weekend hotel stay"},
    {"id": 3, "query": "Book a flight from Jeddah to Cairo next Monday", "type": "flight", "description": "International flight with day reference"},
    {"id": 4, "query": "Find cheap flights from DMM to DXB", "type": "flight", "description": "Flight without date specification"},
    {"id": 5, "query": "Need hotel in bkk for 3 nights starting tmrw", "type": "hotel", "description": "Hotel with abbreviations"},
    {"id": 6, "query": "One way flight from RUH to JED next week", "type": "flight", "description": "Domestic one-way flight"},
    {"id": 7, "query": "Flight from Riyadh to Dammam on Friday morning", "type": "flight", "description": "Flight with city names and time preference"},
    {"id": 8, "query": "Book luxury hotel in Jeddah for April 25", "type": "hotel", "description": "Hotel with category and specific date"},
    {"id": 9, "query": "Cheapest flight DMM to Bahrain nextweek", "type": "flight", "description": "Flight with run-together words"},
    {"id": 10, "query": "Find me flight + hotel in Dubai for next month", "type": "package", "description": "Package vacation query"}
]

@app.route('/')
def index():
    """Render the main debug page"""
    return render_template('debug.html', examples=test_examples)

@app.route('/test/<int:example_id>', methods=['GET'])
def test_example(example_id):
    """Run a test example and return the results"""
    # Find the example
    example = next((ex for ex in test_examples if ex["id"] == example_id), None)
    if not example:
        return jsonify({"error": "Example not found"}), 404
    
    # Step 1: Parameter Extraction
    mock_state = MockTravelState(example["query"])
    try:
        extracted_params = parameter_agent._extract_parameters(example["query"], mock_state)
        
        # Step 2: Search (using appropriate parameters based on query type)
        search_params = {}
        search_query = ""
        
        if example["type"] == "flight":
            # Extract origin, destination and date for flight search
            origin = None
            destination = None
            
            # Try to get from the extracted parameters
            if "origin" in extracted_params:
                origin = extracted_params["origin"]["code"]
            elif "origins" in extracted_params and extracted_params["origins"]:
                origin = extracted_params["origins"][0]["name"]
            
            if "destination" in extracted_params:
                destination = extracted_params["destination"]["code"]
            elif "destinations" in extracted_params and extracted_params["destinations"]:
                destination = extracted_params["destinations"][0]["name"]
            
            # Get date
            date = None
            if "dates" in extracted_params and extracted_params["dates"]:
                date_info = extracted_params["dates"][0]
                date_str = date_info.get("start_date")
                
                # Handle "tomorrow" and similar temporal references
                if date_str == "tomorrow":
                    date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                elif "next week" in date_str or date_str == "nextweek":
                    date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
                elif "weekend" in date_str:
                    # Find next Saturday
                    days_until_saturday = (5 - datetime.now().weekday()) % 7
                    date = (datetime.now() + timedelta(days=days_until_saturday)).strftime("%Y-%m-%d")
                elif "next month" in date_str:
                    date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
                elif "friday" in date_str.lower():
                    days_until_friday = (4 - datetime.now().weekday()) % 7
                    date = (datetime.now() + timedelta(days=days_until_friday)).strftime("%Y-%m-%d")
                elif "monday" in date_str.lower():
                    days_until_monday = (0 - datetime.now().weekday()) % 7
                    date = (datetime.now() + timedelta(days=days_until_monday)).strftime("%Y-%m-%d")
                else:
                    # Try to use the date directly
                    date = date_str
            
            # Default to tomorrow if no date found
            if not date:
                date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                
            search_params = {
                "origin": origin,
                "destination": destination,
                "date": date
            }
            search_query = f"flights from {origin} to {destination} on {date}"
            
        elif example["type"] == "hotel":
            # Extract location and dates for hotel search
            location = None
            if "destinations" in extracted_params and extracted_params["destinations"]:
                location = extracted_params["destinations"][0]["name"]
            
            # Set dates
            check_in = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")  # Default tomorrow
            check_out = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")  # Default 2 nights
            
            if "dates" in extracted_params and extracted_params["dates"]:
                date_info = extracted_params["dates"][0]
                if date_info.get("start_date"):
                    check_in_str = date_info.get("start_date")
                    
                    # Handle temporal references
                    if check_in_str == "tomorrow":
                        check_in = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                    elif "weekend" in check_in_str:
                        # Find next Saturday
                        days_until_saturday = (5 - datetime.now().weekday()) % 7
                        check_in = (datetime.now() + timedelta(days=days_until_saturday)).strftime("%Y-%m-%d")
                    elif "april 25" in check_in_str.lower():
                        check_in = "2025-04-25"
                    else:
                        # Try to use date directly
                        check_in = check_in_str
                    
                    # Set checkout based on nights if specified
                    nights = 2  # Default
                    if "3 nights" in example["query"].lower():
                        nights = 3
                    
                    # Parse check_in to datetime if it's a string
                    if isinstance(check_in, str) and "-" in check_in:
                        try:
                            check_in_date = datetime.strptime(check_in, "%Y-%m-%d")
                            check_out = (check_in_date + timedelta(days=nights)).strftime("%Y-%m-%d")
                        except ValueError:
                            check_out = (datetime.now() + timedelta(days=1+nights)).strftime("%Y-%m-%d")
            
            search_params = {
                "location": location,
                "check_in": check_in,
                "check_out": check_out
            }
            search_query = f"hotels in {location} check in {check_in} check out {check_out}"
        
        else:
            # Package or other type of search
            search_query = example["query"]
        
        # Execute search
        raw_results = search_tool.search(
            query=search_query,
            search_type="organic",
            location=search_params.get("location")
        )
        
        # Parse the results
        structured_results = SearchResultParser.process_search_results(
            raw_results, example["type"], search_params
        )
        
        # Return all the data
        return jsonify({
            "example": example,
            "parameters": extracted_params,
            "search_query": search_query,
            "search_params": search_params,
            "raw_results": raw_results.get("organic", [])[:3],  # Just the first 3 for brevity
            "structured_results": structured_results
        })
        
    except Exception as e:
        logger.error(f"Error processing example {example_id}: {str(e)}", exc_info=True)
        return jsonify({
            "example": example,
            "error": str(e),
            "error_type": type(e).__name__
        }), 500

if __name__ == '__main__':
    # Create templates directory and debug template if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Create debug HTML template
    with open('templates/debug.html', 'w') as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Travel Agent Debug</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .result-container { margin-top: 20px; }
        pre { background-color: #f5f5f5; padding: 10px; border-radius: 5px; white-space: pre-wrap; }
        .loading { display: none; }
        .card { margin-bottom: 15px; }
    </style>
</head>
<body>
    <div class="container mt-5">
        <h1>Travel Agent Debug Interface</h1>
        <p class="lead">Test 10 example queries to debug the travel agent system</p>
        
        <div class="row">
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">Test Examples</div>
                    <div class="card-body">
                        <div class="list-group">
                            {% for example in examples %}
                            <button type="button" class="list-group-item list-group-item-action test-example" 
                                    data-id="{{ example.id }}">
                                <strong>{{ example.id }}. {{ example.type|capitalize }}</strong>: {{ example.query }}
                                <small class="d-block text-muted">{{ example.description }}</small>
                            </button>
                            {% endfor %}
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header">Results</div>
                    <div class="card-body">
                        <div class="loading text-center">
                            <div class="spinner-border text-primary" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                            <p>Processing request...</p>
                        </div>
                        
                        <div class="result-container">
                            <div id="result-placeholder" class="text-center text-muted">
                                <p>Select an example from the list to see results</p>
                            </div>
                            
                            <div id="result-content" style="display:none;">
                                <h4>Query Processed: <span id="query-text"></span></h4>
                                
                                <ul class="nav nav-tabs" id="resultTabs" role="tablist">
                                    <li class="nav-item" role="presentation">
                                        <button class="nav-link active" id="parameters-tab" data-bs-toggle="tab" 
                                                data-bs-target="#parameters-content" type="button">Parameters</button>
                                    </li>
                                    <li class="nav-item" role="presentation">
                                        <button class="nav-link" id="search-tab" data-bs-toggle="tab" 
                                                data-bs-target="#search-content" type="button">Search</button>
                                    </li>
                                    <li class="nav-item" role="presentation">
                                        <button class="nav-link" id="results-tab" data-bs-toggle="tab" 
                                                data-bs-target="#results-content" type="button">Results</button>
                                    </li>
                                </ul>
                                
                                <div class="tab-content mt-3">
                                    <div class="tab-pane fade show active" id="parameters-content" role="tabpanel">
                                        <h5>Extracted Parameters</h5>
                                        <pre id="parameters-json"></pre>
                                    </div>
                                    <div class="tab-pane fade" id="search-content" role="tabpanel">
                                        <h5>Search Query</h5>
                                        <pre id="search-query"></pre>
                                        <h5>Search Parameters</h5>
                                        <pre id="search-params"></pre>
                                    </div>
                                    <div class="tab-pane fade" id="results-content" role="tabpanel">
                                        <h5>Structured Results</h5>
                                        <pre id="structured-results"></pre>
                                        <h5>Raw Results (First 3)</h5>
                                        <pre id="raw-results"></pre>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const buttons = document.querySelectorAll('.test-example');
            const loading = document.querySelector('.loading');
            const placeholder = document.getElementById('result-placeholder');
            const content = document.getElementById('result-content');
            
            buttons.forEach(button => {
                button.addEventListener('click', function() {
                    const exampleId = this.getAttribute('data-id');
                    
                    // Show loading, hide other content
                    loading.style.display = 'block';
                    placeholder.style.display = 'none';
                    content.style.display = 'none';
                    
                    // Remove active class from all buttons
                    buttons.forEach(btn => btn.classList.remove('active'));
                    // Add active class to clicked button
                    this.classList.add('active');
                    
                    // Fetch the test results
                    fetch(`/test/${exampleId}`)
                        .then(response => response.json())
                        .then(data => {
                            // Hide loading
                            loading.style.display = 'none';
                            
                            // Update content
                            document.getElementById('query-text').textContent = data.example.query;
                            document.getElementById('parameters-json').textContent = JSON.stringify(data.parameters, null, 2);
                            document.getElementById('search-query').textContent = data.search_query;
                            document.getElementById('search-params').textContent = JSON.stringify(data.search_params, null, 2);
                            document.getElementById('raw-results').textContent = JSON.stringify(data.raw_results, null, 2);
                            document.getElementById('structured-results').textContent = JSON.stringify(data.structured_results, null, 2);
                            
                            // Show content
                            content.style.display = 'block';
                        })
                        .catch(error => {
                            loading.style.display = 'none';
                            content.style.display = 'block';
                            document.getElementById('query-text').textContent = 'Error: ' + error.message;
                        });
                });
            });
            
            // Initialize Bootstrap tabs
            const triggerTabList = [].slice.call(document.querySelectorAll('#resultTabs button'));
            triggerTabList.forEach(function (triggerEl) {
                new bootstrap.Tab(triggerEl);
            });
        });
    </script>
</body>
</html>""")
    
    # Run the app
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
