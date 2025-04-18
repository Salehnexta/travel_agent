import os
import logging
import time
import httpx
from typing import List, Dict, Optional, Any, Union
from enum import Enum
import json

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LLMProviderType(str, Enum):
    """Enum for supported LLM providers."""
    DEEPSEEK = "deepseek"
    GROQ = "groq"
    OPENAI = "openai"  # Optional fallback


class LLMConfigurationError(Exception):
    """Exception raised for LLM configuration errors."""
    pass


class LLMRequestError(Exception):
    """Exception raised for errors in LLM API requests."""
    pass


class LLMClient:
    """
    Client for interacting with Language Model providers.
    Supports DeepSeek (primary) and Groq (fallback).
    """
    
    def __init__(self):
        """Initialize LLM client with API configurations."""
        # Load API keys from environment variables
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")  # Optional fallback
        
        # Check if at least one provider is configured
        if not (self.deepseek_api_key or self.groq_api_key or self.openai_api_key):
            raise LLMConfigurationError("No LLM provider API keys found in environment variables.")
        
        # Configure client for each available provider
        self.clients = {}
        self.available_providers = []
        
        # Configure DeepSeek client (primary)
        if self.deepseek_api_key:
            try:
                # Get base URL from environment variables, with fallback
                deepseek_base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
                
                # According to DeepSeek documentation, we need to use a specific base URL format
                # and configure client with minimal parameters to ensure compatibility
                http_client = httpx.Client(timeout=None)
                self.clients[LLMProviderType.DEEPSEEK] = OpenAI(
                    api_key=self.deepseek_api_key,
                    base_url=f"{deepseek_base}/v1",
                    http_client=http_client
                )
                self.available_providers.append(LLMProviderType.DEEPSEEK)
                logger.info(f"DeepSeek LLM client initialized with base URL: {deepseek_base}/v1")
            except Exception as e:
                logger.error(f"Failed to initialize DeepSeek client: {str(e)}")
        
        # Configure Groq client (fallback)
        if self.groq_api_key:
            try:
                # Get base URL from environment variables, with fallback
                groq_base = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")
                
                # According to Groq documentation, it's designed to be compatible with OpenAI client
                # Using a custom http client to avoid proxies parameter issues
                http_client = httpx.Client(timeout=None)
                self.clients[LLMProviderType.GROQ] = OpenAI(
                    api_key=self.groq_api_key,
                    base_url=groq_base,
                    http_client=http_client
                )
                self.available_providers.append(LLMProviderType.GROQ)
                logger.info(f"Groq LLM client initialized with base URL: {groq_base}")
            except Exception as e:
                logger.error(f"Failed to initialize Groq client: {str(e)}")
        
        # Configure OpenAI client (additional fallback)
        if self.openai_api_key:
            try:
                # OpenAI with custom http client to maintain consistency
                http_client = httpx.Client(timeout=None)
                self.clients[LLMProviderType.OPENAI] = OpenAI(
                    api_key=self.openai_api_key,
                    http_client=http_client
                )
                self.available_providers.append(LLMProviderType.OPENAI)
                logger.info("OpenAI LLM client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {str(e)}")
        
        # Set default models for each provider
        self.default_models = {
            LLMProviderType.DEEPSEEK: "deepseek-chat",  # Updated to valid model name
            LLMProviderType.GROQ: "llama3-8b-8192",  # Updated to currently available model
            LLMProviderType.OPENAI: "gpt-4-turbo-preview"
        }

    def get_available_providers(self) -> List[LLMProviderType]:
        """Return list of available LLM providers."""
        return self.available_providers
    
    def is_provider_available(self, provider: LLMProviderType) -> bool:
        """Check if a specific provider is available."""
        return provider in self.available_providers
    
    @retry(
        retry=retry_if_exception_type(Exception),  # Using generic Exception since we handle specifics inside the method
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _generate_with_provider(
        self,
        provider: LLMProviderType,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate a response using a specific provider.
        
        Args:
            provider: The LLM provider to use
            messages: List of message dictionaries with role and content
            model: Model name to use (defaults to provider's default)
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Dictionary containing the response and metadata
        """
        if provider not in self.available_providers:
            raise LLMConfigurationError(f"Provider {provider} is not configured")
        
        client = self.clients[provider]
        model_name = model or self.default_models[provider]
        
        try:
            start_time = time.time()
            
            # Create the completion request parameters
            params = {
                "model": model_name,
                "messages": messages
            }
            
            # Add optional parameters if provided
            if temperature is not None:
                params["temperature"] = temperature
            if max_tokens is not None:
                params["max_tokens"] = max_tokens
            
            # Make the API call
            response = client.chat.completions.create(**params)
            
            end_time = time.time()
            response_text = response.choices[0].message.content
            
            # Build result dictionary with response and metadata
            result = {
                "provider": provider,
                "model": model_name,
                "response": response_text,
                "latency": end_time - start_time,
                "success": True
            }
            
            return result
            
        except Exception as e:
            # Handle errors based on type
            rate_limit_errors = ['rate_limit', 'timeout', 'connection']  
            if any(err in str(e).lower() for err in rate_limit_errors):
                # These errors will trigger retry
                logger.warning(f"Retryable error with {provider}: {str(e)}")
                raise
            else:
                # Other errors will be caught and returned with error information
                logger.error(f"Error with {provider}: {str(e)}")
                return {
                    "provider": provider,
                    "model": model_name,
                    "error": str(e),
                    "success": False
                }
    
    def generate_response(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate a response from the LLM, trying providers in order of priority.
        Returns the generated text or raises an exception if all providers fail.
        
        Args:
            messages: List of message dictionaries with role and content
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            The generated text response
            
        Raises:
            LLMRequestError: If all providers fail
        """
        errors = []
        
        # Try each available provider in order of priority
        for provider in self.available_providers:
            result = self._generate_with_provider(
                provider=provider,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            if result["success"]:
                logger.info(f"Successfully generated response with {provider}")
                return result["response"]
            else:
                errors.append(f"{provider}: {result.get('error', 'Unknown error')}")
        
        # If we get here, all providers failed
        error_msg = "; ".join(errors)
        logger.error(f"All LLM providers failed: {error_msg}")
        raise LLMRequestError(f"All LLM providers failed: {error_msg}")
    
    def generate_structured_output(
        self,
        messages: List[Dict[str, str]],
        output_schema: Dict[str, Any],
        temperature: Optional[float] = 0.2
    ) -> Dict[str, Any]:
        """
        Generate a structured JSON output based on the provided schema.
        
        Args:
            messages: List of message dictionaries with role and content
            output_schema: JSON schema describing the expected response structure
            temperature: Sampling temperature (default: lower for structured outputs)
            
        Returns:
            Parsed JSON object matching the schema
        """
        # Add instructions for structured output to the messages
        schema_message = {
            "role": "system",
            "content": f"Please respond with a valid JSON object following this schema: {json.dumps(output_schema)}"
        }
        
        adjusted_messages = messages.copy()
        adjusted_messages.insert(0, schema_message)
        
        # Generate the response with a lower temperature for more predictable output
        response_text = self.generate_response(
            messages=adjusted_messages,
            temperature=temperature
        )
        
        try:
            # Enhanced JSON extraction from response
            import re
            response_text = response_text.strip()
            json_str = None
            
            # Case 1: JSON in markdown code block (various formats)
            code_block_patterns = [
                r'```(?:json)?([\s\S]*?)```',  # Standard markdown code blocks
                r'`([\s\S]*?)`',               # Inline code blocks
            ]
            
            for pattern in code_block_patterns:
                matches = re.findall(pattern, response_text)
                if matches:
                    for potential_json in matches:
                        potential_json = potential_json.strip()
                        if potential_json.startswith('{') and potential_json.endswith('}'):
                            try:
                                # Test if it's valid JSON
                                json.loads(potential_json)
                                json_str = potential_json
                                break
                            except json.JSONDecodeError:
                                continue
                    if json_str:
                        break
            
            # Case 2: Direct JSON object
            if not json_str and response_text.startswith('{') and response_text.endswith('}'):
                json_str = response_text
            
            # Case 3: JSON object embedded in text
            if not json_str:
                # Look for the largest matching JSON object in the text
                possible_jsons = re.findall(r'(\{[\s\S]*?\})', response_text)
                if possible_jsons:
                    # Sort by length (descending) to prioritize larger objects
                    possible_jsons.sort(key=len, reverse=True)
                    for possible_json in possible_jsons:
                        try:
                            json.loads(possible_json)
                            json_str = possible_json
                            break
                        except json.JSONDecodeError:
                            continue
            
            # Case 4: Key-value pairs that need to be converted to JSON
            if not json_str and ':' in response_text:
                try:
                    # Try to parse a simplified format like "key1: value1\nkey2: value2"
                    lines = [line.strip() for line in response_text.split('\n') if ':' in line]
                    parsed_obj = {}
                    for line in lines:
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            key = parts[0].strip().strip('"').strip("'")
                            value = parts[1].strip().strip('"').strip("'")
                            parsed_obj[key] = value
                    if parsed_obj:
                        json_str = json.dumps(parsed_obj)
                except Exception:
                    pass
            
            # Case 5: Look for "parameters" or structured content
            if not json_str:
                param_match = re.search(r'(parameters|extracted parameters|result)[\s\S]*?\{[\s\S]*?\}', 
                                        response_text, re.IGNORECASE)
                if param_match:
                    param_text = param_match.group(0)
                    json_match = re.search(r'\{[\s\S]*?\}', param_text)
                    if json_match:
                        try:
                            json.loads(json_match.group(0))
                            json_str = json_match.group(0)
                        except json.JSONDecodeError:
                            pass
            
            if not json_str:
                # If we still don't have JSON, raise an error
                logger.error(f"Could not extract JSON from response: {response_text[:100]}...")
                raise ValueError("Could not extract JSON from response")
            
            # Parse the JSON response
            return json.loads(json_str)
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse structured output: {str(e)}")
            logger.debug(f"Raw response: {response_text}")
            raise LLMRequestError(f"Failed to parse structured output: {str(e)}")
