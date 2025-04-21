import streamlit as st
import requests
from datetime import datetime
import json
import time
from api_service import TravelAgentAPI

# Initialize API service at the top
travel_api = TravelAgentAPI()

# Initialize all state variables upfront
if 'chat_history' not in st.session_state:
    st.session_state.update({
        'chat_history': [],
        'selected_flight': None,
        'selected_hotel': None,
        'filters': {
            'max_price': 2000,
            'min_rating': 3
        },
        'last_backend_check': None,
        'session_id': None
    })

# Set page config
@st.cache_data(ttl=60)  # Cache for 1 minute
def ping_backend():
    try:
        return requests.get('http://localhost:5001/health', timeout=3).ok
    except:
        return False

def display_system_status():
    with st.sidebar.expander(" System Status"):
        if st.button("Run Diagnostics"):
            with st.spinner("Checking components..."):
                backend_status = " Online" if ping_backend() else " Offline"
                st.session_state.last_backend_check = datetime.now().strftime('%H:%M:%S')
                
                st.write(f"**Backend Service:** {backend_status}")
                st.write(f"**Last Checked:** {st.session_state.last_backend_check}")
                
                if " Offline" in backend_status:
                    st.error("Flask backend not detected. Please run:\n\n`flask run`")
                    st.link_button("Open Backend", "http://localhost:5000")

# Main app
def main():
    st.set_page_config(
        page_title="AI Travel Agent", 
        page_icon="", 
        layout="wide"
    )
    
    import streamlit.components.v1 as components
    components.html(f"""
    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        // Patch Streamlit's wheel event listeners
        const originalAdd = EventTarget.prototype.addEventListener;
        EventTarget.prototype.addEventListener = function(type, fn, options) {{
            if (type === 'wheel' && typeof options !== 'object') {{
                options = {{ passive: true }};
            }}
            originalAdd.call(this, type, fn, options);
        }};
    }});
    </script>
    """, height=0)
    
    display_system_status()
    
    # Helper function to validate and format flight data
    def format_flight_data(flights):
        formatted_flights = []
        if not flights:
            return []
            
        for flight in flights:
            # Ensure all required fields exist
            formatted_flight = {
                'airline': flight.get('airline', 'Unknown Airline'),
                'price': flight.get('price', 'Price unavailable'),
                'departure': flight.get('departure', 'Departure info unavailable'),
                'arrival': flight.get('arrival', 'Arrival info unavailable'),
                'duration': flight.get('duration', 'Duration unknown'),
                'stops': flight.get('stops', 'Direct')
            }
            
            # Clean up price format
            if formatted_flight['price'] and not formatted_flight['price'].startswith('$') and formatted_flight['price'] != 'Price unavailable':
                try:
                    price_value = float(formatted_flight['price'])
                    formatted_flight['price'] = f"${price_value:.2f}"
                except:
                    pass
                    
            formatted_flights.append(formatted_flight)
        return formatted_flights
    
    # CSS for better styling
    st.markdown("""
    <style>
        .st-emotion-cache-1y4p8pa {
            padding: 2rem;
        }
        .flight-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        .flight-price {
            font-weight: bold;
            color: #2ecc71;
        }
        .hotel-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
            background-color: #f8f9fa;
        }
    </style>
    """, unsafe_allow_html=True)

    st.title(" AI Travel Assistant")

    # Sidebar for session management
    with st.sidebar:
        st.header("Session")
        if st.button("New Conversation"):
            st.session_state.chat_history = []
            st.session_state.session_id = None
            st.rerun()

        st.header("Travel Details")
        departure_date = st.date_input("Departure Date")
        return_date = st.date_input("Return Date (if round trip)")
        budget = st.number_input("Budget ($)", min_value=0, value=1000)

    # Chat display container
    chat_container = st.container()

    # Display chat history
    for msg in st.session_state.chat_history:
        with chat_container:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
                # Display flight cards if present
                if msg.get("flights"):
                    st.subheader("✈️ Flight Options")
                    # Format and validate flight data
                    formatted_flights = format_flight_data(msg["flights"])
                    
                    # Display flights with proper formatting
                    for flight in formatted_flights:
                        flight_title = f"{flight['airline']} - {flight['price']}"
                        with st.expander(flight_title):
                            st.markdown(f"""
                                <div class="flight-card">
                                    <div class="flight-price">{flight['price']}</div>
                                    <div><strong>🛫 Departure:</strong> {flight['departure']}</div>
                                    <div><strong>🛬 Arrival:</strong> {flight['arrival']}</div>
                                    <div><strong>⏱️ Duration:</strong> {flight['duration']}</div>
                                    <div><strong>✈️ Airline:</strong> {flight['airline']}</div>
                                    <div><strong>🔄 Stops:</strong> {flight['stops']}</div>
                                </div>
                            """, unsafe_allow_html=True)
                
                # Display hotels if present
                if msg.get("hotels"):
                    st.subheader(" Hotel Options")
                    for hotel in msg["hotels"]:
                        with st.expander(f"{hotel.get('name', 'Hotel')} - {hotel.get('price', 'Price N/A')}"):
                            st.markdown(f"""
                            <div class="hotel-card">
                                <div> Rating:</strong> {hotel.get('rating', 'N/A')}</div>
                                <div> Location:</strong> {hotel.get('location', 'N/A')}</div>
                                <div> Price:</strong> {hotel.get('price', 'N/A')}</div>
                                <div> <a href="{hotel.get('link', '#')}" target="_blank">View Deal</a></div>
                            </div>
                            """, unsafe_allow_html=True)

    try:
        if prompt := st.chat_input("Ask about flights, hotels, or itineraries"):
            # Add user message to history
            st.session_state.chat_history.append({
                "role": "user",
                "content": prompt,
                "timestamp": datetime.now().isoformat()
            })
            
            # Call API service with detailed loading states
            with st.status("Processing your travel request...", expanded=True) as status:
                st.write("🔍 Analyzing your query...")
                
                # Track start time for performance monitoring
                start_time = time.time()
                
                # Make API call with progress updates
                try:
                    status.update(label="🔍 Searching for travel options...", state="running")
                    
                    response_data = travel_api.send_chat(
                        prompt=prompt,
                        session_id=st.session_state.session_id,
                        params={
                            "departure_date": departure_date.isoformat(),
                            "return_date": return_date.isoformat() if return_date else None,
                            "budget": budget
                        }
                    )
                    
                    # Show processing time
                    elapsed = time.time() - start_time
                    st.write(f"⏱️ Processing time: {elapsed:.1f} seconds")
                    
                    if response_data:
                        status.update(label="✅ Found travel options!", state="complete")
                    else:
                        status.update(label="⚠️ Could not retrieve travel options", state="error")
                        
                except Exception as e:
                    status.update(label=f"❌ Error: {str(e)}", state="error")
                    st.error("The backend is taking too long to respond. This might be due to high demand or complex queries.")
                    st.info("Try a simpler query or try again later.")

                if response_data:
                    # Process successful response
                    if response_data.get("session_id"):
                        st.session_state.session_id = response_data["session_id"]
                    
                    # Add assistant response to history
                    assistant_msg = {
                        "role": "assistant",
                        "content": response_data.get("response", "I couldn't process that request."),
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Add flights if available
                    if response_data.get("structured_flights"):
                        assistant_msg["flights"] = response_data["structured_flights"]
                    
                    # Add hotels if available
                    if response_data.get("structured_hotels"):
                        assistant_msg["hotels"] = response_data["structured_hotels"]
                    
                    st.session_state.chat_history.append(assistant_msg)
                    st.rerun()
                    
    except Exception as e:
        st.error(f"Critical application error: {str(e)}")
        st.button("Reload App", on_click=st.rerun)
        st.stop()

if __name__ == "__main__":
    main()
