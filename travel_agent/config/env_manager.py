"""
Environment management module for travel agent.
Implements best practices for multi-environment configuration and secret management.
"""

import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EnvironmentManager:
    """
    Manager for environment-specific configuration and secrets.
    Supports development, testing, and production environments.
    """
    
    def __init__(self, environment: Optional[str] = None):
        """
        Initialize the environment manager.
        
        Args:
            environment: The environment to use (development, testing, production)
                         If None, tries to determine from ENVIRONMENT env var, defaulting to development
        """
        # Determine environment
        self.environment = environment or os.getenv("ENVIRONMENT", "development")
        self.valid_environments = ["development", "testing", "production"]
        
        if self.environment not in self.valid_environments:
            logger.warning(
                f"Unknown environment: {self.environment}. "
                f"Using development. Valid environments: {', '.join(self.valid_environments)}"
            )
            self.environment = "development"
        
        # Load appropriate .env file
        self.load_environment()
        
        logger.info(f"Environment Manager initialized for {self.environment} environment")
    
    def load_environment(self) -> None:
        """Load the appropriate environment file based on current environment."""
        # Try environment-specific file first
        env_file = f".env.{self.environment}"
        if os.path.isfile(env_file):
            load_dotenv(env_file)
            logger.info(f"Loaded environment from {env_file}")
        else:
            # Fall back to default .env
            load_dotenv()
            logger.info("Loaded environment from default .env file")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get an environment variable.
        
        Args:
            key: The name of the environment variable
            default: The value to return if the variable is not set
            
        Returns:
            The value of the environment variable, or the default
        """
        return os.getenv(key, default)
    
    def get_required(self, key: str) -> str:
        """
        Get a required environment variable. Raises ValueError if not set.
        
        Args:
            key: The name of the environment variable
            
        Returns:
            The value of the environment variable
            
        Raises:
            ValueError: If the environment variable is not set
        """
        value = os.getenv(key)
        if value is None:
            raise ValueError(f"Required environment variable {key} is not set")
        return value
    
    def get_api_key(self, service: str) -> Optional[str]:
        """
        Get an API key for a specific service.
        
        Args:
            service: The name of the service (e.g., 'deepseek', 'groq', 'serper')
            
        Returns:
            The API key for the service, or None if not set
        """
        key_name = f"{service.upper()}_API_KEY"
        return os.getenv(key_name)
    
    def get_required_api_key(self, service: str) -> str:
        """
        Get a required API key for a specific service. Raises ValueError if not set.
        
        Args:
            service: The name of the service (e.g., 'deepseek', 'groq', 'serper')
            
        Returns:
            The API key for the service
            
        Raises:
            ValueError: If the API key is not set
        """
        key_name = f"{service.upper()}_API_KEY"
        key = os.getenv(key_name)
        if not key:
            raise ValueError(f"Required API key for {service} (environment variable {key_name}) is not set")
        return key
    
    def is_production(self) -> bool:
        """Check if the current environment is production."""
        return self.environment == "production"
    
    def is_development(self) -> bool:
        """Check if the current environment is development."""
        return self.environment == "development"
    
    def is_testing(self) -> bool:
        """Check if the current environment is testing."""
        return self.environment == "testing"
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get a dictionary of common configuration values for the current environment.
        
        Returns:
            Dictionary of configuration values
        """
        return {
            "environment": self.environment,
            "debug": not self.is_production(),
            "redis_url": self.get("REDIS_URL", "redis://localhost:6379"),
            "api_keys": {
                "deepseek": self.get_api_key("deepseek"),
                "groq": self.get_api_key("groq"),
                "openai": self.get_api_key("openai"),
                "serper": self.get_api_key("serper"),
            }
        }


# Singleton instance
env_manager = EnvironmentManager()


def get_env_manager() -> EnvironmentManager:
    """Get the singleton environment manager instance."""
    return env_manager
