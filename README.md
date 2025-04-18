# AI-Powered Travel Assistant

An intelligent conversational travel agent that helps users plan trips through natural language interaction, leveraging LLMs and real-time search.

## 🌟 Features

- **Advanced Parameter Extraction** - Intelligently identifies travel details including airport codes and temporal references
- **Multi-pattern Recognition** - Enhanced detection of hotel preferences, dates, and locations
- **Real-time Travel Data** - Uses Google Search API with efficient caching for up-to-date information
- **Multiple LLM Support** - Primary: DeepSeek with Groq fallback, optimized client initialization
- **Stateful Conversation** - Maintains context throughout the planning process with LangGraph
- **Error Recovery** - Robust error tracking and fallback mechanisms

## 🛠️ Technologies

### AI & Machine Learning
- **Primary LLM**: DeepSeek Coder v2 (via OpenAI SDK compatibility layer)
- **Fallback LLM**: Groq (llama3-70b-8192) (via OpenAI SDK compatibility layer)
- **LLM Integration**: OpenAI SDK v1.5.0 with optimized client initialization
- **Agent Orchestration**: LangGraph v0.0.38 with state persistence

### Backend
- **Language**: Python 3.11+
- **Web Framework**: Flask with CORS support
- **State Management**: Redis with enhanced JSON serialization
- **APIs**: Google Serper API with tiered caching and retry logic
- **Error Tracking**: Centralized error tracking system with unique IDs

### Frontend
- **Core**: Vanilla JavaScript
- **Styling**: Custom responsive CSS
- **UI Components**: Card-based displays for travel options

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Redis
- API keys for DeepSeek, Groq (optional), and Google Serper
- DeepSeek and Groq accounts (both use OpenAI-compatible API endpoints)

### Installation

```bash
# Clone repository
git clone https://github.com/your-org/travel-agent.git
cd travel-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# For development, install test dependencies
pip install -r requirements.txt[test]

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Running Locally

```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start Flask app
source venv/bin/activate
FLASK_ENV=development python app.py

# Access in browser at http://localhost:5000
```

## 🧪 Development Plan

### Phase 1: Core Backend Components
- Implement state definitions
- Set up LLM providers (DeepSeek/Groq via OpenAI SDK)
- Create search tools

### Phase 2: Agent Implementation
- Build individual agents
- Integrate with LangGraph
- Test agent communication

### Phase 3: API and Redis Integration
- Set up Flask endpoints
- Integrate Redis for state management
- Test API functionality

### Phase 4: Frontend Development
- Create HTML/CSS interface
- Implement JavaScript interactivity
- Connect to backend API

## 🧩 System Architecture

```
                                  ┌───────────────────┐
                                  │                   │
                                  │  User Interface   │
                                  │                   │
                                  └─────────┬─────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│                           Flask Application                             │
│                                                                         │
└───────────────┬─────────────────────────────────────┬──────────────────┘
                │                                     │
                ▼                                     ▼
┌───────────────────────────────┐      ┌──────────────────────────────────┐
│                               │      │                                  │
│       LangGraph Flow          │      │           Redis Cache            │
│                               │      │                                  │
└─┬─────┬─────┬─────┬─────┬─────┘      └──────────────────────────────────┘
  │     │     │     │     │
  │     │     │     │     │
  ▼     ▼     ▼     ▼     ▼
┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐
│CM  │ │IR  │ │DE  │ │SM  │ │RG  │
└────┘ └────┘ └────┘ └────┘ └────┘

CM: Conversation Manager   IR: Intent Recognition   DE: Data Extraction
SM: Search Manager         RG: Response Generator
```

## 📝 Testing

| Component | Verification Method | Success Criteria |
|-----------|---------------------|------------------|
| State Definitions | Unit tests | Models can be instantiated with valid data |
| Parameter Extraction | Parameterized tests | Correctly extracts airport codes, dates, and preferences |
| LLM Integration | Mock API tests | Client handles responses and errors with proper recovery |
| Search Tools | Cached integration tests | Search queries return expected structure with efficient caching |
| Agent Logic | Unit & integration tests | Agents produce expected outputs and handle edge cases |
| API Endpoints | API tests | Endpoints return expected status codes and data |

The project includes specific test scripts for validating flight and hotel searches, with particular attention to the DMM to BKK route and tomorrow date extraction.

### Testing Procedures After Deployment

#### 1. API Endpoints Testing

```bash
# Health check endpoint
curl http://localhost:5001/health
# Expected: {"status": "healthy"}

# Chat API
curl -X POST -H "Content-Type: application/json" -d '{"message":"I want to travel to Paris next month"}' http://localhost:5001/api/chat
# Expected: Response with assistant message and session ID

# Reset session
curl -X POST http://localhost:5001/api/reset
# Expected: Success message with new session ID
```

#### 2. LLM Integration Testing

Testing the LLM integration requires valid API keys for DeepSeek and/or Groq. The application will fall back to available providers if some aren't configured.

```bash
# Verify LLM initialization in logs
grep "LLM client initialized" server.log

# Test LLM generation with travel query
curl -X POST -H "Content-Type: application/json" -d '{"message":"What are the best hotels in Paris?"}' http://localhost:5001/api/chat
```

#### 3. Search Tools Testing

Testing search functionality requires a valid Serper API key.

```bash
# Test specific search-related query
curl -X POST -H "Content-Type: application/json" -d '{"message":"Find flights from New York to London"}' http://localhost:5001/api/chat
```

#### 4. End-to-End Testing via Web Interface

1. Open http://localhost:5001 in your web browser
2. Send a travel query (e.g., "I want to plan a trip to Tokyo next month")
3. Verify that the system asks appropriate follow-up questions
4. Provide travel details as requested
5. Verify that search results for hotels, flights, or destination information are displayed
6. Test the reset functionality by clicking the "Reset Conversation" button

## 🔒 Security

- Environment variables for API keys
- Input validation and sanitization
- Rate limiting implementation
- Session-based storage with Redis

## 🔧 Technical Notes

### Component Integration

#### LLM Providers

This application uses the OpenAI SDK v1.5.0 to connect to multiple LLM providers through their OpenAI-compatible APIs, with enhanced error handling and fallback mechanisms:

- **DeepSeek Coder v2**: Primary LLM used for language processing (via OpenAI compatibility layer)
  - Documentation: https://platform.deepseek.com/docs
  - Fixed initialization issues with OpenAI SDK v1.5.0
  - API Version: Compatible with OpenAI API v1
  - Base URL: https://api.deepseek.com/v1

- **Groq (llama3-70b-8192)**: Fallback LLM when DeepSeek is unavailable
  - Documentation: https://console.groq.com/docs
  - API Version: OpenAI-compatible API
  - Base URL: https://api.groq.com/openai/v1

##### Proper LLM Integration Configuration

To ensure proper integration with DeepSeek and Groq APIs using OpenAI SDK v1.5.0:

1. **Client Initialization**:
   ```python
   # Initialize with custom http client to avoid proxy issues
   from openai import OpenAI
   import httpx

   # For DeepSeek
   http_client = httpx.Client()
   deepseek_client = OpenAI(
       api_key=os.getenv("DEEPSEEK_API_KEY"),
       base_url=os.getenv("DEEPSEEK_API_BASE"),
       http_client=http_client,
       timeout=None  # Prevent timeouts for longer queries
   )

   # For Groq
   http_client = httpx.Client()
   groq_client = OpenAI(
       api_key=os.getenv("GROQ_API_KEY"),
       base_url=os.getenv("GROQ_API_BASE"),
       http_client=http_client,
       timeout=None  # Prevent timeouts for longer queries
   )
   ```

2. **Key Configuration Points**:
   - Use custom `httpx.Client()` to manage the connection
   - Set `timeout=None` to prevent connection timeouts (adjust as needed)
   - Avoid using the `proxies` parameter which causes compatibility issues
   - Ensure base URLs end with the appropriate version path
   - Create separate client instances for each LLM provider

#### Redis Integration

- Redis is used for session state management with a 24-hour expiration policy
- Redis connections are established using the redis-py client v5.0.1
- Session data is stored as JSON serialized objects under session-specific keys

#### Serper API (Google Search)

- The application uses Serper API to fetch real-time travel data
- Documentation: https://serper.dev/api-reference
- Requests are cached in-memory with a 1-hour TTL to minimize API usage

### Common Issues and Solutions

1. **OpenAI SDK Compatibility**: Fixed initialization issues with v1.5.0 for third-party compatible APIs like DeepSeek and Groq. The solution removes problematic parameters (like `proxies`) and implements more resilient client initialization with proper error handling.

2. **Parameter Extraction**: Enhanced date extraction to properly handle temporal references like "tomorrow" and "next week" with correct date formatting.

3. **Hotel Preference Detection**: Improved pattern matching to better identify hotel preferences with multiple recognition patterns (near locations, amenities, etc.).

4. **Port 5000 Conflict on macOS**: The default port 5000 may conflict with AirPlay on macOS. The application now defaults to port 5001 to avoid this issue.

### Performance Considerations

1. **LLM Latency**: Responses may take 2-5 seconds depending on the LLM provider's performance
2. **Rate Limiting**: The application implements rate limiting to prevent abuse and stay within API quotas
3. **Caching**: Search results are cached to improve performance and reduce API costs

## 🔀 LangGraph Integration

### Installation and Usage

This application uses LangGraph for agent workflow orchestration. Follow these guidelines to avoid common issues:

```bash
# Install the correct versions of LangGraph and related packages
pip install langgraph==0.0.51 langchain==0.1.20 langchain-core==0.1.53
```

### Best Practices

1. **State Structure**: Always define a clear state structure (using `TypedDict` or `Pydantic` models) that includes:
   - A conversation history or messages field
   - A field for tracking the next step (e.g., `next` or `current_node`)
   - Fields for any accumulated data (parameters, search results, etc.)

2. **Node Functions**: 
   - Node functions should accept and return the entire state object
   - Do not return tuples or multiple values from node functions
   - Update the state's routing field (e.g., `state["next"]`) within the function

3. **Graph Construction**:
   - Use `add_conditional_edges()` with a router function instead of direct edges
   - Always set a proper entry point with `set_entry_point()`
   - Include routes to `END` in your conditional edges

4. **Error Handling**:
   - Implement proper error tracking in your state
   - Set a recursion limit in your router function to avoid infinite loops

### Example Implementation

See `travel_agent/langgraph_mini.py` for a minimal but complete implementation following these best practices.

## 📚 Additional Resources

For more detailed information, see the [todo.md](todo.md) file which contains the comprehensive technical specification.

## 📄 License

[MIT License](LICENSE)
