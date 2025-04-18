"""
Optimized LLM provider configuration for the travel agent application.
Implements best practices for OpenAI API integration with DeepSeek and Groq.
"""

import os
import json
import logging
import time
from typing import Any, Dict, List, Optional, Union, Callable
import functools
import hashlib

from openai import OpenAI, APIError, APITimeoutError, RateLimitError

from travel_agent.error_tracking import (
    track_errors, retry_with_tracking, ErrorTracker, 
    LLMAPIError
)

# Create a dedicated logger for LLM operations
llm_logger = logging.getLogger('travel_agent.llm')
error_tracker = ErrorTracker('llm')

# Initialize Simple in-memory cache
_cache = {}

def _create_cache_key(model: str, messages: List[Dict], temperature: float, max_tokens: int) -> str:
    """Create a deterministic cache key for LLM requests"""
    cache_data = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    cache_json = json.dumps(cache_data, sort_keys=True)
    return hashlib.md5(cache_json.encode('utf-8')).hexdigest()

class LLMProvider:
    """Manages LLM API connections and operations with best practices"""
    
    def __init__(self):
        """Initialize LLM clients with proper configuration"""
        self.deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        
        # Default model configurations
        self.default_model = "deepseek-chat"
        self.fallback_model = "groq-chat"
        self.model_configs = {
            "deepseek-chat": {
                "api_key": self.deepseek_api_key,
                "base_url": "https://api.deepseek.com/v1",
                "model_name": "deepseek-chat-v1"
            },
            "groq-chat": {
                "api_key": self.groq_api_key,
                "base_url": "https://api.groq.com/v1",
                "model_name": "mixtral-8x7b-32768"
            }
        }
        
        # Initialize clients
        self.clients = {}
        self._initialize_clients()
        
        # Cache settings
        self.cache_enabled = True
        self.cache_ttl = 3600  # 1 hour cache TTL
    
    @track_errors('llm')
    def _initialize_clients(self):
        """Initialize OpenAI clients for each configured model using best practices."""
        llm_logger.info("Initializing LLM clients")
        
        # Initialize clients for each model
        for model_id, config in self.model_configs.items():
            if config["api_key"]:
                try:
                    # Use only the essential parameters to avoid compatibility issues
                    # across different OpenAI SDK implementations
                    self.clients[model_id] = OpenAI(
                        api_key=config["api_key"],
                        base_url=config["base_url"]
                    )
                    
                    # Set timeout separately after initialization if needed
                    if hasattr(self.clients[model_id], "timeout") and isinstance(self.clients[model_id].timeout, property):
                        try:
                            self.clients[model_id].timeout = 60.0
                        except Exception as e_timeout:
                            llm_logger.warning(f"Could not set timeout for {model_id}: {str(e_timeout)}")
                    
                    llm_logger.info(f"{model_id} LLM client initialized with base URL: {config['base_url']}")
                except Exception as e:
                    # Log the error and try a more minimal configuration
                    llm_logger.warning(f"{model_id} client initialization failed with standard params: {str(e)}")
                    
                    try:
                        # Try with absolutely minimal parameters (just API key)
                        self.clients[model_id] = OpenAI(
                            api_key=config["api_key"]
                        )
                        llm_logger.info(f"{model_id} LLM client initialized with default URL")
                    except Exception as e2:
                        error_id = error_tracker.track_error(
                            e2, {"model": model_id, "component": "llm_provider_init"}
                        )
                        llm_logger.error(f"Failed to initialize {model_id} client: {str(e2)} (Error ID: {error_id})")
    
    @retry_with_tracking(max_attempts=3, backoff_factor=2.0, component='llm')
    def get_completion(
        self,
        messages: List[Dict],
        model_id: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500,
        stream: bool = False,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Get completion from LLM with retry logic and caching
        
        Args:
            messages: List of message dictionaries (role, content)
            model_id: Model ID to use (deepseek-chat or groq-chat)
            temperature: Temperature for sampling
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            use_cache: Whether to use cache
            
        Returns:
            Dict containing the response
        """
        # Don't use cache for streaming
        if stream:
            use_cache = False
            
        # If caching is enabled and not streaming, check cache
        if self.cache_enabled and use_cache and not stream:
            cache_key = _create_cache_key(model_id or self.default_model, messages, temperature, max_tokens)
            cached_response = _cache.get(cache_key)
            if cached_response:
                cached_time, response = cached_response
                age = time.time() - cached_time
                if age < self.cache_ttl:
                    llm_logger.info(f"Cache hit for {model_id or self.default_model} (age: {age:.1f}s)")
                    return response
                else:
                    # Expired cache entry
                    del _cache[cache_key]
        
        # Select model
        model_id = model_id or self.default_model
        
        # Get model config
        config = self.model_configs.get(model_id)
        if not config:
            error_id = error_tracker.track_error(
                ValueError(f"Unknown model ID: {model_id}"),
                {"available_models": list(self.model_configs.keys())}
            )
            raise ValueError(f"Unknown model ID: {model_id} (Error ID: {error_id})")
        
        # Get client
        client = self.clients.get(model_id)
        if not client:
            # Try fallback if available
            if model_id == self.default_model and self.fallback_model in self.clients:
                llm_logger.warning(f"Primary model {model_id} unavailable, using fallback {self.fallback_model}")
                model_id = self.fallback_model
                client = self.clients.get(model_id)
                config = self.model_configs.get(model_id)
            
            if not client:
                error_id = error_tracker.track_error(
                    LLMAPIError(f"No client available for {model_id}"),
                    {"model": model_id}
                )
                raise LLMAPIError(f"No client available for {model_id} (Error ID: {error_id})")
        
        try:
            # Get response from the model
            llm_logger.info(f"Calling {model_id} with {len(messages)} messages")
            
            start_time = time.time()
            response = client.chat.completions.create(
                model=config["model_name"],
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )
            
            # Handle streaming response
            if stream:
                return response
            
            end_time = time.time()
            llm_logger.info(f"LLM call completed in {end_time - start_time:.2f}s")
            
            # Format response
            result = {
                "content": response.choices[0].message.content,
                "model": model_id,
                "latency": end_time - start_time,
                "finish_reason": response.choices[0].finish_reason
            }
            
            # Cache the response
            if self.cache_enabled and use_cache:
                cache_key = _create_cache_key(model_id, messages, temperature, max_tokens)
                _cache[cache_key] = (time.time(), result)
            
            return result
            
        except (APITimeoutError, APIError, RateLimitError) as e:
            error_details = {
                "model": model_id,
                "messages_count": len(messages),
                "error_type": type(e).__name__
            }
            
            # Attempt fallback for certain errors if this isn't already the fallback
            if model_id == self.default_model and self.fallback_model in self.clients:
                llm_logger.warning(f"Error with {model_id}, trying fallback {self.fallback_model}: {str(e)}")
                # Track error but don't raise
                error_tracker.track_error(e, error_details, level="warning")
                
                # Recursive call with fallback model
                return self.get_completion(
                    messages=messages,
                    model_id=self.fallback_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream,
                    use_cache=use_cache
                )
            else:
                # No fallback available or already using fallback
                error_id = error_tracker.track_error(e, error_details)
                raise LLMAPIError(f"LLM API error: {str(e)} (Error ID: {error_id})") from e

# Create a singleton instance for application-wide use
llm_provider = LLMProvider()
