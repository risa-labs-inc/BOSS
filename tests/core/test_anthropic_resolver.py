import pytest
import os
from unittest.mock import patch, MagicMock
from typing import Any, Optional

from boss.core.task_models import Task, TaskStatus
from boss.core.anthropic_resolver import AnthropicTaskResolver
from boss.core.task_resolver import TaskResolverMetadata


class TestAnthropicTaskResolver:

    def setup_method(self) -> None:
        self.metadata = TaskResolverMetadata(
            name="anthropic",
            version="1.0.0",
            description="Anthropic Claude task resolver"
        )
        # Mock API key for testing
        os.environ["ANTHROPIC_API_KEY"] = "test-key-12345"
        
        self.resolver = AnthropicTaskResolver(
            metadata=self.metadata,
            model_name="claude-3-haiku-20240307",
            temperature=0.7
        )
    
    def teardown_method(self) -> None:
        if "ANTHROPIC_API_KEY" in os.environ:
            del os.environ["ANTHROPIC_API_KEY"]
    
    @patch('anthropic.Anthropic')
    def test_init_with_api_key_param(self, mock_anthropic: Any) -> None:
        resolver = AnthropicTaskResolver(
            metadata=self.metadata,
            model_name="claude-3-haiku-20240307",
            api_key="direct-api-key",
            temperature=0.7
        )
        assert resolver.api_key == "direct-api-key"
        assert resolver.model_name == "claude-3-haiku-20240307"
        assert resolver.temperature == 0.7
    
    @patch('anthropic.Anthropic')
    def test_init_with_env_api_key(self, mock_anthropic: Any) -> None:
        os.environ["ANTHROPIC_API_KEY"] = "env-api-key"
        resolver = AnthropicTaskResolver(
            metadata=self.metadata,
            model_name="claude-3-haiku-20240307"
        )
        assert resolver.api_key == "env-api-key"
    
    @patch('anthropic.Anthropic')
    def test_init_without_api_key(self, mock_anthropic: Any) -> None:
        if "ANTHROPIC_API_KEY" in os.environ:
            del os.environ["ANTHROPIC_API_KEY"]
        
        with pytest.raises(ValueError) as excinfo:
            resolver = AnthropicTaskResolver(
                metadata=self.metadata,
                model_name="claude-3-haiku-20240307"
            )
        assert "Anthropic API key not found" in str(excinfo.value)
    
    @patch('anthropic.Anthropic')
    def test_generate_completion_success(self, mock_anthropic: Any) -> None:
        # Mock the Anthropic client and its messages.create method
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This is a test response")]
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 20
        mock_client.messages.create.return_value = mock_response
        
        # Test the method
        prompt = "Tell me about AI"
        completion, tokens = self.resolver.generate_completion(prompt)
        
        # Verify the method called Anthropic API correctly
        mock_client.messages.create.assert_called_once()
        kwargs = mock_client.messages.create.call_args.kwargs
        assert kwargs["model"] == "claude-3-haiku-20240307"
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_tokens"] == 4096
        assert prompt in kwargs["messages"][0]["content"]
        
        # Verify the return values
        assert completion == "This is a test response"
        assert tokens == 30  # input + output tokens
    
    @patch('anthropic.Anthropic')
    def test_generate_completion_api_error(self, mock_anthropic: Any) -> None:
        # Mock the Anthropic client to raise an exception
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API Error")
        
        # Test the method
        with pytest.raises(Exception) as excinfo:
            self.resolver.generate_completion("Test prompt")
        
        assert "API Error" in str(excinfo.value)
    
    @patch.object(AnthropicTaskResolver, 'generate_completion')
    def test_call_success(self, mock_generate_completion: Any) -> None:
        # Mock the generate_completion method
        mock_generate_completion.return_value = ("This is a test response", 30)
        
        # Create a task
        task = Task(
            input_data="Tell me about AI",
            metadata={"resolver": "anthropic"}
        )
        
        # Call the resolver
        result = self.resolver(task)
        
        # Verify the result
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data == "This is a test response"
        assert result.metadata["tokens"] == 30
        assert not result.error
    
    @patch.object(AnthropicTaskResolver, 'generate_completion')
    def test_call_failure(self, mock_generate_completion: Any) -> None:
        # Mock the generate_completion method to raise an exception
        mock_generate_completion.side_effect = Exception("API Error")
        
        # Create a task
        task = Task(
            input_data="Tell me about AI",
            metadata={"resolver": "anthropic"}
        )
        
        # Call the resolver
        result = self.resolver(task)
        
        # Verify the result
        assert result.status == TaskStatus.ERROR
        assert result.error is not None
        assert "API Error" in str(result.error)
    
    def test_can_handle(self) -> None:
        # Task explicitly for this resolver
        task1 = Task(
            input_data="Test",
            metadata={"resolver": "anthropic"}
        )
        assert self.resolver.can_handle(task1)
        
        # Task with no specific resolver
        task2 = Task(
            input_data="Test",
            metadata={"resolver": ""}
        )
        assert self.resolver.can_handle(task2)
        
        # Task for a different resolver
        task3 = Task(
            input_data="Test",
            metadata={"resolver": "openai"}
        )
        assert not self.resolver.can_handle(task3)
        
        # Task with model specified
        task4 = Task(
            input_data="Test",
            metadata={"model": "claude-3-opus-20240229"}
        )
        assert self.resolver.can_handle(task4)
    
    @patch('anthropic.Anthropic')
    def test_health_check(self, mock_anthropic: Any) -> None:
        # Mock the Anthropic client and its messages.create method
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="I am operational and functioning normally.")]
        mock_response.usage.input_tokens = 5
        mock_response.usage.output_tokens = 10
        mock_client.messages.create.return_value = mock_response
        
        # Test the health check
        health_result = self.resolver.health_check()
        
        # Verify the health check called Anthropic API
        mock_client.messages.create.assert_called_once()
        
        # Verify the health check result
        assert health_result is True 