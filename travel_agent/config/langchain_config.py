"""
Optimized LangChain configuration for the travel agent application.
Implements best practices for LangChain integration with caching and monitoring.
"""

import os
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.language_models.llms import LLM
from langchain_community.cache import RedisCache
from langchain.chains.llm import LLMChain
from langchain_core.prompts import ChatPromptTemplate
import langchain

from travel_agent.config.redis_client import redis_manager
from travel_agent.error_tracking import track_errors, ErrorTracker, retry_with_tracking

# Configure logger
langchain_logger = logging.getLogger('travel_agent.langchain')
error_tracker = ErrorTracker('langchain')

# Configure LangChain tracing if enabled
LANGCHAIN_TRACING = os.getenv("LANGCHAIN_TRACING", "false").lower() in ("true", "1", "t")
if LANGCHAIN_TRACING:
    os.environ["LANGCHAIN_TRACING"] = "true"
    langchain_endpoint = os.getenv("LANGCHAIN_ENDPOINT")
    langchain_api_key = os.getenv("LANGCHAIN_API_KEY")
    
    if langchain_endpoint and langchain_api_key:
        os.environ["LANGCHAIN_ENDPOINT"] = langchain_endpoint
        os.environ["LANGCHAIN_API_KEY"] = langchain_api_key
        langchain_logger.info("LangChain tracing enabled with custom endpoint")
    else:
        langchain_logger.info("LangChain tracing enabled with default endpoint")

# Configure LangChain caching with Redis
LANGCHAIN_CACHING = os.getenv("LANGCHAIN_CACHING", "true").lower() in ("true", "1", "t")
if LANGCHAIN_CACHING:
    try:
        # Skip caching configuration if Redis isn't available or if there are import issues
        try:
            # Create a direct connection string for Redis
            langchain.llm_cache = RedisCache(url=redis_manager.redis_url)
            langchain_logger.info("LangChain caching enabled with Redis")
        except TypeError:
            # Fall back to simpler initialization if the API has changed
            langchain_logger.info("Attempting fallback Redis cache initialization")
            langchain.llm_cache = RedisCache()
            langchain_logger.info("LangChain caching enabled with default Redis")
    except Exception as e:
        error_id = error_tracker.track_error(e, {"feature": "langchain_caching"})
        langchain_logger.warning(f"Failed to enable LangChain caching: {str(e)} (Error ID: {error_id})")

class CustomLLM(LLM):
    """Custom LLM class to integrate with our LLM provider"""
    
    model_id: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 500
    
    @property
    def _llm_type(self) -> str:
        return "custom_llm"
    
    @track_errors('langchain')
    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        """Call the LLM with the prompt"""
        from travel_agent.config.llm_provider import llm_provider
        
        messages = [{"role": "user", "content": prompt}]
        
        response = llm_provider.get_completion(
            messages=messages,
            model_id=self.model_id,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        
        return response["content"]
    
    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Return identifying parameters"""
        return {
            "model_id": self.model_id,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

@track_errors('langchain')
def create_langchain_messages(messages: List[Dict[str, str]]) -> List[BaseMessage]:
    """Convert dictionary messages to LangChain message objects"""
    langchain_messages = []
    
    for message in messages:
        role = message["role"].lower()
        content = message["content"]
        
        if role == "system":
            langchain_messages.append(SystemMessage(content=content))
        elif role == "user":
            langchain_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            langchain_messages.append(AIMessage(content=content))
        # Ignore unknown roles
    
    return langchain_messages

@track_errors('langchain')
def create_prompt_template(template: str, input_variables: List[str]) -> ChatPromptTemplate:
    """Create a prompt template with optimization"""
    return ChatPromptTemplate.from_template(template)

@track_errors('langchain')
def create_llm_chain(prompt_template: ChatPromptTemplate, model_id: str = "deepseek-chat") -> LLMChain:
    """Create an LLM chain with our custom LLM"""
    llm = CustomLLM(model_id=model_id)
    return LLMChain(llm=llm, prompt=prompt_template)
