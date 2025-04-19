# Travel Agent Testing Framework

This directory contains a comprehensive testing framework for the Travel Agent system. The tests are organized into four categories:

## Test Structure

### 1. Unit Tests
Located in the `unit/` directory, these tests focus on testing individual components in isolation. They verify that each component functions correctly on its own.

- `test_input_validation.py` - Tests for the input validation component
- `test_rate_limiter.py` - Tests for the rate limiting functionality
- `test_error_handling.py` - Tests for error tracking, fallbacks, and monitoring

### 2. Integration Tests
Located in the `integration/` directory, these tests verify that different components work correctly together. They test the interactions between multiple units.

### 3. API Tests
Located in the `api/` directory, these tests focus on testing the Flask API endpoints. They verify that the API behaves correctly and returns appropriate responses.

- `test_flask_api.py` - Tests for API endpoints with security and error handling

### 4. End-to-End Tests
Located in the `end_to_end/` directory, these tests simulate real user interactions with the system. They test the complete flow from UI to backend and back.

- `test_web_interface.py` - Tests for the web UI using Selenium

## Running Tests

Use the `run_tests.py` script to run tests:

```bash
# Run all tests
python tests/run_tests.py

# Run only unit tests
python tests/run_tests.py --type unit

# Run only API tests
python tests/run_tests.py --type api

# Run only end-to-end tests
python tests/run_tests.py --type end_to_end

# Run with reduced verbosity
python tests/run_tests.py --verbosity 1
```

## Test Dependencies

Required packages for running the tests:

- `unittest` - Standard Python testing framework
- `flask_unittest` - Enhanced testing for Flask applications
- `selenium` - For web UI testing
- `webdriver_manager` - For managing Selenium WebDriver
- `requests` - For making HTTP requests in tests

Install all development dependencies with:

```bash
pip install -r requirements-dev.txt
```

## Test Coverage

The tests cover all major components of the Travel Agent system:

1. **Security Features**
   - Input validation and sanitization
   - Rate limiting
   - Session security

2. **Error Handling**
   - Error tracking with unique IDs
   - Fallback mechanisms
   - Error monitoring dashboard

3. **API Endpoints**
   - Health check
   - Chat start
   - Message sending
   - Error responses

4. **Web Interface**
   - UI elements and interactions
   - Message sending and responses
   - Search results display
   - Error handling in the UI

## Writing New Tests

When adding new features or modifying existing ones, ensure to:

1. Write unit tests for new components
2. Update integration tests if component interactions change
3. Update API tests if endpoints are modified
4. Update end-to-end tests if UI behavior changes

Always run the full test suite before submitting changes to ensure nothing breaks unexpectedly.
