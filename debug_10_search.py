"""
Script to run all 10 debug search examples from debug_flask_app.py and print results (no frontend required).
"""
import os
import json
from travel_agent.search_tools import SearchToolManager
from travel_agent.search_result_parser import SearchResultParser
from travel_agent.agents.parameter_extraction import ParameterExtractionAgent

# Test queries from debug_flask_app.py
TEST_EXAMPLES = [
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

# Initialize components
search_tool = SearchToolManager()
parameter_agent = ParameterExtractionAgent()

class MockTravelState:
    def __init__(self, user_query):
        self.query = user_query
        self.conversation_history = [{"role": "user", "content": user_query}]
    def get_conversation_context(self, num_messages=5):
        return self.conversation_history
    def get_latest_user_query(self):
        return self.query

def run_debug_searches():
    results = []
    for example in TEST_EXAMPLES:
        print(f"\n=== Test {example['id']}: {example['description']} ===")
        print(f"Query: {example['query']}")
        mock_state = MockTravelState(example["query"])
        try:
            # Parameter extraction
            params = parameter_agent._extract_parameters(example["query"], mock_state)
            print("Extracted Parameters:")
            print(json.dumps(params, indent=2))
            # Search
            if example["type"] == "flight":
                origin = params.get("origin", {}).get("code") or (params.get("origins") or [{}])[0].get("name")
                destination = params.get("destination", {}).get("code") or (params.get("destinations") or [{}])[0].get("name")
                date = None
                if params.get("dates"):
                    date = params["dates"][0].get("start_date")
                search_results = search_tool.flight_search(origin, destination, date)
                structured = SearchResultParser.extract_flight_details(search_results, origin, destination, date)
            elif example["type"] == "hotel":
                location = params.get("destination", {}).get("name") or (params.get("destinations") or [{}])[0].get("name")
                check_in = None
                check_out = None
                if params.get("dates"):
                    check_in = params["dates"][0].get("start_date")
                    if len(params["dates"]) > 1:
                        check_out = params["dates"][1].get("start_date")
                search_results = search_tool.hotel_search(location, check_in, check_out)
                structured = SearchResultParser.extract_hotel_details(search_results, location, check_in, check_out)
            else:
                # For package or other types, just run a general search
                search_results = search_tool.general_search(example["query"])
                structured = search_results.get("organic", [])
            print("Search Results:")
            print(json.dumps(structured, indent=2))
            results.append({"id": example["id"], "description": example["description"], "params": params, "results": structured})
        except Exception as e:
            print(f"Error: {e}")
            results.append({"id": example["id"], "description": example["description"], "error": str(e)})
    return results

if __name__ == "__main__":
    all_results = run_debug_searches()
    print("\nSummary:")
    for res in all_results:
        print(f"Test {res['id']}: {res['description']}")
        if 'error' in res:
            print(f"  ERROR: {res['error']}")
        else:
            print(f"  Params: {json.dumps(res['params'], ensure_ascii=False)}")
            print(f"  Results: {json.dumps(res['results'], ensure_ascii=False)[:300]}...")
