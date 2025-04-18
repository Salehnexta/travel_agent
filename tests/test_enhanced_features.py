"""
Comprehensive test suite for enhanced travel agent features.
Tests tiered caching, parallel search, and LangGraph integration.
"""

import pytest
import asyncio
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from travel_agent.state_definitions import TravelState, ConversationStage
from travel_agent.config.cache_manager import TieredCache
from travel_agent.agents.parallel_search_manager import ParallelSearchManager


class TestTieredCache:
    """Test suite for the tiered caching system."""
    
    def test_memory_cache_get_set(self):
        """Test basic memory cache get/set operations."""
        from travel_agent.config.cache_manager import MemoryCache
        
        cache = MemoryCache()
        cache.set("test_key", "test_value")
        assert cache.get("test_key") == "test_value"
        assert cache.get("nonexistent_key") is None
    
    def test_memory_cache_ttl(self, monkeypatch):
        """Test TTL-based expiration in memory cache."""
        from travel_agent.config.cache_manager import MemoryCache
        import time
        
        # Mock time.time() to control "current time"
        current_time = 1000.0
        monkeypatch.setattr(time, "time", lambda: current_time)
        
        cache = MemoryCache()
        
        # Set item with 10 second TTL
        cache.set("expiring_key", "will_expire", ttl=10)
        
        # Should still be available before expiry
        assert cache.get("expiring_key") == "will_expire"
        
        # Advance time past TTL
        current_time += 11
        
        # Should now be expired
        assert cache.get("expiring_key") is None
    
    def test_tiered_cache_layers(self, mock_redis):
        """Test that tiered cache uses memory first, then Redis."""
        with patch("travel_agent.config.redis_client.RedisManager", return_value=mock_redis):
            cache = TieredCache()
            
            # Set a value (should go to both memory and Redis)
            cache.set("test_key", "test_value")
            
            # Get the value (should come from memory without hitting Redis)
            mock_redis.get_json.reset_mock()
            result = cache.get("test_key")
            
            assert result == "test_value"
            # Verify Redis was not called since it was in memory
            mock_redis.get_json.assert_not_called()
    
    def test_tiered_cache_redis_fallback(self, mock_redis):
        """Test Redis fallback when item is not in memory."""
        with patch("travel_agent.config.redis_client.RedisManager", return_value=mock_redis):
            cache = TieredCache()
            
            # Configure Redis mock to return a value
            mock_redis.get_json.return_value = "redis_value"
            
            # Get a value not in memory (should fall back to Redis)
            result = cache.get("redis_key")
            
            assert result == "redis_value"
            # Verify Redis was called
            mock_redis.get_json.assert_called_once()


class TestParallelSearchManager:
    """Test suite for parallel search execution."""
    
    @pytest.mark.asyncio
    async def test_parallel_destination_search(self):
        """Test asynchronous destination search."""
        # Mock search_destination_info to return predefined results
        mock_result = {"info": "Sample destination info"}
        
        with patch("travel_agent.search_tools.search_destination_info", return_value=mock_result):
            manager = ParallelSearchManager()
            result = await manager._search_destination_async("DMM")
            
            assert result == mock_result
    
    @pytest.mark.asyncio
    async def test_parallel_flight_search(self):
        """Test asynchronous flight search."""
        # Mock search_flights to return predefined results
        mock_result = {"flights": [{"airline": "Test Airline"}]}
        
        with patch("travel_agent.search_tools.search_flights", return_value=mock_result):
            manager = ParallelSearchManager()
            result = await manager._search_flights_async("DMM", "BKK", "2025-04-19")
            
            assert result == mock_result
    
    def test_process_executes_searches(self, sample_travel_state, mock_serper_flight_response):
        """Test that process method executes all relevant searches."""
        # Create mocks for each search type
        with patch("travel_agent.search_tools.search_destination_info", return_value={"info": "destination info"}), \
             patch("travel_agent.search_tools.search_flights", return_value=mock_serper_flight_response), \
             patch("travel_agent.search_tools.search_hotels", return_value={"hotels": []}):
            
            manager = ParallelSearchManager()
            result_state = manager.process(sample_travel_state)
            
            # Verify results were added to state
            assert "destination" in result_state.search_results
            assert "flight" in result_state.search_results


class TestEnhancedTravelAgentGraph:
    """Test suite for enhanced travel agent graph with LangGraph integration."""
    
    def test_create_session(self, travel_agent_graph):
        """Test session creation."""
        state = travel_agent_graph.create_session("test-session")
        
        assert state.session_id == "test-session"
        assert state.conversation_stage == ConversationStage.INITIAL_GREETING
        assert len(state.conversation_history) > 0
    
    def test_graph_workflow(self, travel_agent_graph, sample_travel_state):
        """Test the graph processing workflow."""
        # Patch node methods to return predictable results
        with patch.object(travel_agent_graph, "_recognize_intent", return_value=sample_travel_state), \
             patch.object(travel_agent_graph, "_extract_parameters", return_value=sample_travel_state), \
             patch.object(travel_agent_graph, "_validate_parameters", return_value=sample_travel_state), \
             patch.object(travel_agent_graph, "_execute_search", return_value=sample_travel_state), \
             patch.object(travel_agent_graph, "_generate_response", return_value=sample_travel_state):
            
            result = travel_agent_graph.process_message(
                sample_travel_state, 
                "Show me flights from DMM to BKK tomorrow"
            )
            
            # Verify state contains user message
            last_message = result.conversation_history[-1]
            assert "Show me flights" in last_message.get("content", "")
    
    def test_error_handling(self, travel_agent_graph, sample_travel_state):
        """Test error handling in graph workflow."""
        # Patch a method to raise an exception
        with patch.object(travel_agent_graph, "_extract_parameters", side_effect=Exception("Test error")), \
             patch.object(travel_agent_graph.conversation_manager, "handle_error", return_value="Error occurred"):
            
            result = travel_agent_graph.process_message(
                sample_travel_state, 
                "This will cause an error"
            )
            
            # Verify error was handled
            assert result.conversation_stage == ConversationStage.ERROR_HANDLING
            assert len(result.errors) > 0
            
            # Check for error response
            last_message = result.conversation_history[-1]
            assert last_message.get("role") == "assistant"


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
