"""
Tests for the XAITaskResolver class.

This module contains unit tests for the XAITaskResolver, which integrates with 
xAI's Grok models through the official xai-grok-sdk.
"""
import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Any, Optional, Dict

from boss.core.task_models import Task
from boss.core.xai_resolver import XAITaskResolver, XAI_SDK_AVAILABLE
from boss.core.task_resolver import TaskResolverMetadata


class TestXAITaskResolver:
    """Test suite for the XAITaskResolver class."""

    def setup_method(self) -> None:
        """Set up the test environment before each test."""
        self.metadata = TaskResolverMetadata(
            name="xai",
            version="1.0.0",
            description="XAI Grok task resolver"
        )
        # Mock API key for testing
        os.environ["XAI_API_KEY"] = "test-key-xai-12345"
        
        # Create the resolver
        self.resolver = XAITaskResolver(
            metadata=self.metadata,
            model_name="grok-2-1212",
            temperature=0.7
        )
    
    def teardown_method(self) -> None:
        """Clean up the test environment after each test."""
        if "XAI_API_KEY" in os.environ:
            del os.environ["XAI_API_KEY"]
    
    @patch('xai_grok_sdk.XAI')
    def test_init_with_api_key_param(self, mock_xai: Any) -> None:
        """Test initializing the resolver with API key as a parameter."""
        resolver = XAITaskResolver(
            metadata=self.metadata,
            model_name="grok-2-1212",
            api_key="direct-api-key",
            temperature=0.7
        )
        assert resolver.api_key == "direct-api-key"
        assert resolver.model_name == "grok-2-1212"
        assert resolver.temperature == 0.7
    
    @patch('xai_grok_sdk.XAI')
    def test_init_with_env_api_key(self, mock_xai: Any) -> None:
        """Test initializing the resolver with API key from environment variable."""
        os.environ["XAI_API_KEY"] = "env-api-key"
        resolver = XAITaskResolver(
            metadata=self.metadata,
            model_name="grok-2-1212"
        )
        assert resolver.api_key == "env-api-key"
    
    @patch('xai_grok_sdk.XAI')
    def test_init_with_unsupported_model(self, mock_xai: Any) -> None:
        """Test initializing with a model name that's not explicitly supported."""
        resolver = XAITaskResolver(
            metadata=self.metadata,
            model_name="grok-3",
            api_key="test-key"
        )
        # Should still initialize but log a warning (which we can't check here)
        assert resolver.model_name == "grok-3"
    
    @patch('boss.core.xai_resolver.XAI')
    def test_initialize_client_success(self, mock_xai: Any) -> None:
        """Test successful client initialization."""
        # Setup
        mock_xai.return_value = MagicMock()
        resolver = XAITaskResolver(model_name="grok-2-1212", api_key="test-key")
        
        # Execute
        result = resolver._initialize_client()
        
        # Verify
        assert result is True
        mock_xai.assert_called_once_with(api_key="test-key", model="grok-2-1212")
        assert resolver.client is not None
    
    @patch('boss.core.xai_resolver.XAI')
    def test_initialize_client_error(self, mock_xai: Any) -> None:
        """Test client initialization with error."""
        # Setup
        mock_xai.side_effect = Exception("Client error")
        resolver = XAITaskResolver(model_name="grok-2-1212", api_key="test-key")
        
        # Execute
        result = resolver._initialize_client()
        
        # Verify
        assert result is False
        assert resolver.client is None
    
    @pytest.mark.asyncio
    @patch('boss.core.xai_resolver.XAI')
    async def test_generate_completion_success(self, mock_xai: Any) -> None:
        """Test successful completion generation."""
        # Setup mock client
        mock_client = MagicMock()
        mock_xai.return_value = mock_client
        
        # Mock response
        mock_message = MagicMock()
        mock_message.content = "This is a generated response"
        
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 15
        mock_response.usage.completion_tokens = 25
        mock_response.usage.total_tokens = 40
        
        # Mock the client.invoke method
        mock_client.invoke.return_value = mock_response
        
        # Create resolver
        resolver = XAITaskResolver(model_name="grok-2-1212", api_key="test-key")
        resolver.client = mock_client  # Set client directly
        
        # Test
        response = await resolver.generate_completion("Tell me about AI")
        
        # Verify
        mock_client.invoke.assert_called_once()
        call_args = mock_client.invoke.call_args[1]
        assert call_args["messages"][0]["content"] == "Tell me about AI"
        assert call_args["temperature"] == 0.7
        
        # Check response
        assert response.content == "This is a generated response"
        assert response.model_name == "grok-2-1212"
        assert response.tokens_used["total_tokens"] == 40
        assert response.metadata["finish_reason"] == "stop"
    
    @pytest.mark.asyncio
    @patch('boss.core.xai_resolver.XAI')
    async def test_generate_completion_with_system_prompt(self, mock_xai: Any) -> None:
        """Test completion generation with system prompt."""
        # Setup mock client
        mock_client = MagicMock()
        mock_xai.return_value = mock_client
        
        # Mock response
        mock_message = MagicMock()
        mock_message.content = "Response with system prompt"
        
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        
        # Mock the client.invoke method
        mock_client.invoke.return_value = mock_response
        
        # Create resolver
        resolver = XAITaskResolver(model_name="grok-2-1212", api_key="test-key")
        resolver.client = mock_client  # Set client directly
        
        # Test with system prompt
        system_prompt = "You are a helpful assistant"
        response = await resolver.generate_completion(
            "Tell me about AI",
            system_prompt=system_prompt
        )
        
        # Verify system prompt was included
        mock_client.invoke.assert_called_once()
        call_args = mock_client.invoke.call_args[1]
        assert len(call_args["messages"]) == 2
        assert call_args["messages"][0]["role"] == "system"
        assert call_args["messages"][0]["content"] == system_prompt
        assert call_args["messages"][1]["content"] == "Tell me about AI"
        
        # Check response
        assert response.content == "Response with system prompt"
    
    @pytest.mark.asyncio
    @patch('boss.core.xai_resolver.XAI_SDK_AVAILABLE', False)
    async def test_generate_completion_sdk_not_available(self) -> None:
        """Test completion generation when SDK is not available."""
        # Setup
        resolver = XAITaskResolver(model_name="grok-2-1212", api_key="test-key")
        
        # Test
        with pytest.raises(Exception) as exc_info:
            await resolver.generate_completion("Test prompt")
        
        # Verify
        assert "xAI Grok SDK is not available" in str(exc_info.value)
    
    @pytest.mark.asyncio
    @patch('boss.core.xai_resolver.XAITaskResolver._initialize_client')
    async def test_generate_completion_client_init_failure(self, mock_init_client: Any) -> None:
        """Test completion generation when client initialization fails."""
        # Setup
        mock_init_client.return_value = False
        resolver = XAITaskResolver(model_name="grok-2-1212", api_key="test-key")
        
        # Test
        with pytest.raises(Exception) as exc_info:
            await resolver.generate_completion("Test prompt")
        
        # Verify
        assert "Failed to initialize xAI client" in str(exc_info.value)
    
    @pytest.mark.asyncio
    @patch('boss.core.xai_resolver.XAI')
    async def test_generate_completion_api_error(self, mock_xai: Any) -> None:
        """Test completion generation when API call fails."""
        # Setup mock client
        mock_client = MagicMock()
        mock_xai.return_value = mock_client
        
        # Mock API error
        mock_client.invoke.side_effect = Exception("API error")
        
        # Create resolver
        resolver = XAITaskResolver(model_name="grok-2-1212", api_key="test-key")
        resolver.client = mock_client  # Set client directly
        
        # Test
        with pytest.raises(Exception) as exc_info:
            await resolver.generate_completion("Test prompt")
        
        # Verify
        assert "API error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    @patch('boss.core.xai_resolver.XAI')
    async def test_process_task_success(self, mock_xai: Any) -> None:
        """Test successful task processing."""
        # Setup mock client
        mock_client = MagicMock()
        mock_xai.return_value = mock_client
        
        # Mock response
        mock_message = MagicMock()
        mock_message.content = "Processed task response"
        
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.total_tokens = 30
        
        # Mock the client.invoke method
        mock_client.invoke.return_value = mock_response
        
        # Create resolver
        resolver = XAITaskResolver(model_name="grok-2-1212", api_key="test-key")
        resolver.client = mock_client  # Set client directly
        
        # Create a task
        task = Task(
            name="process_task_test",
            input_data={
                "prompt": "Task prompt",
                "resolver": "xai"
            }
        )
        
        # Process the task
        processed_task = await resolver.process_task(task)
        
        # Verify
        assert processed_task.result is not None
        assert "content" in processed_task.result
        assert processed_task.error is None
    
    @pytest.mark.asyncio
    @patch('boss.core.xai_resolver.XAITaskResolver.generate_completion')
    async def test_process_task_error(self, mock_generate: Any) -> None:
        """Test task processing with error."""
        # Setup
        mock_generate.side_effect = Exception("Task processing error")
        resolver = XAITaskResolver(model_name="grok-2-1212", api_key="test-key")
        
        # Create a task
        task = Task(
            name="process_task_error_test",
            input_data={
                "prompt": "Task prompt",
                "resolver": "xai"
            }
        )
        
        # Process the task
        processed_task = await resolver.process_task(task)
        
        # Verify
        assert processed_task.error is not None
        assert "Task processing error" in processed_task.error.get("message", "")
        assert processed_task.error.get("details", {}).get("model") == "grok-2-1212"
    
    def test_can_handle(self) -> None:
        """Test can_handle method with various task configurations."""
        # Task explicitly for this resolver
        task1 = Task(
            name="can_handle_test_1",
            input_data={
                "resolver": "xai",
                "prompt": "Test"
            }
        )
        assert self.resolver.can_handle(task1) is True
        
        # Task with "grok" as resolver
        task2 = Task(
            name="can_handle_test_2",
            input_data={
                "resolver": "grok",
                "prompt": "Test"
            }
        )
        assert self.resolver.can_handle(task2) is True
        
        # Task with grok model specified
        task3 = Task(
            name="can_handle_test_3",
            input_data={
                "model": "grok-2-1212",
                "prompt": "Test"
            }
        )
        assert self.resolver.can_handle(task3) is True
        
        # Task for a different resolver
        task4 = Task(
            name="can_handle_test_4",
            input_data={
                "resolver": "openai",
                "prompt": "Test"
            }
        )
        assert self.resolver.can_handle(task4) is False
    
    @pytest.mark.asyncio
    @patch('boss.core.xai_resolver.XAI')
    async def test_health_check_success(self, mock_xai: Any) -> None:
        """Test health check with success."""
        # Setup mock client
        mock_client = MagicMock()
        mock_xai.return_value = mock_client
        
        # Create resolver
        resolver = XAITaskResolver(model_name="grok-2-1212", api_key="test-key")
        resolver.client = mock_client  # Set client directly
        
        # Mock generate_completion
        mock_response = MagicMock()
        mock_response.content = "I am healthy and operational"
        
        with patch.object(
            resolver, 'generate_completion', 
            return_value=mock_response
        ):
            # Test
            result = await resolver.health_check()
            
            # Verify
            assert result is True
    
    @pytest.mark.asyncio
    @patch('boss.core.xai_resolver.XAI')
    async def test_health_check_degraded(self, mock_xai: Any) -> None:
        """Test health check with unhealthy response."""
        # Create resolver
        resolver = XAITaskResolver(model_name="grok-2-1212", api_key="test-key")
        
        # Mock generate_completion to return response without 'healthy'
        mock_response = MagicMock()
        mock_response.content = "I cannot process your request right now"
        
        with patch.object(
            resolver, 'generate_completion', 
            return_value=mock_response
        ):
            # Test
            result = await resolver.health_check()
            
            # Verify
            assert result is False
    
    @pytest.mark.asyncio
    @patch('boss.core.xai_resolver.XAI_SDK_AVAILABLE', False)
    async def test_health_check_sdk_not_available(self) -> None:
        """Test health check when SDK is not available."""
        # Create resolver
        resolver = XAITaskResolver(model_name="grok-2-1212", api_key="test-key")
        
        # Test
        result = await resolver.health_check()
        
        # Verify
        assert result is False
    
    @pytest.mark.asyncio
    async def test_health_check_no_api_key(self) -> None:
        """Test health check with no API key."""
        # Create resolver with no API key
        if "XAI_API_KEY" in os.environ:
            del os.environ["XAI_API_KEY"]
        resolver = XAITaskResolver(model_name="grok-2-1212", api_key=None)
        
        # Test
        result = await resolver.health_check()
        
        # Verify
        assert result is False
    
    @pytest.mark.asyncio
    @patch('boss.core.xai_resolver.XAITaskResolver.generate_completion')
    async def test_health_check_api_error(self, mock_generate: Any) -> None:
        """Test health check with API error."""
        # Mock generate_completion to raise exception
        mock_generate.side_effect = Exception("API error during health check")
        
        # Create resolver
        resolver = XAITaskResolver(model_name="grok-2-1212", api_key="test-key")
        
        # Test
        result = await resolver.health_check()
        
        # Verify
        assert result is False 