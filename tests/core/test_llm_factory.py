import pytest
from unittest.mock import patch, MagicMock
from typing import Any, Dict, Optional, Type

from boss.core.llm_factory import LLMTaskResolverFactory
from boss.core.base_llm_resolver import BaseLLMTaskResolver
from boss.core.openai_resolver import OpenAITaskResolver
from boss.core.task_models import Task
from boss.core.task_resolver import TaskResolverMetadata


class MockResolver(BaseLLMTaskResolver):
    """Mock resolver for testing."""
    
    def __init__(
        self, 
        metadata: TaskResolverMetadata,
        model_name: str,
        api_key: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        super().__init__(metadata, model_name, api_key, **kwargs)
    
    def generate_completion(self, prompt: str) -> tuple[str, int]:
        return f"Mock response for {prompt}", 10


class TestLLMTaskResolverFactory:
    """Tests for the LLMTaskResolverFactory class."""
    
    def setup_method(self) -> None:
        """Set up test fixtures."""
        # Create a factory with mocked resolvers
        self.factory = LLMTaskResolverFactory()
        
        # Register our mock resolver
        self.factory.register_provider(
            "mock", 
            MockResolver, 
            ["mock-model-1", "mock-model-2"]
        )
    
    @patch.dict("os.environ", {"OPENAI_API_KEY": "fake-key"})
    def test_init(self) -> None:
        """Test factory initialization."""
        factory = LLMTaskResolverFactory()
        assert "openai" in factory.resolver_classes
        assert OpenAITaskResolver == factory.resolver_classes["openai"]
    
    def test_register_provider(self) -> None:
        """Test provider registration."""
        # Check if our mock provider was registered correctly
        assert "mock" in self.factory.resolver_classes
        assert self.factory.resolver_classes["mock"] == MockResolver
        assert "mock-model-1" in self.factory.provider_models["mock"]
        assert "mock-model-2" in self.factory.provider_models["mock"]
    
    def test_get_available_providers(self) -> None:
        """Test getting available providers."""
        providers = self.factory.get_available_providers()
        assert "openai" in providers
        assert "mock" in providers
    
    def test_get_models_for_provider(self) -> None:
        """Test getting models for a provider."""
        models = self.factory.get_models_for_provider("mock")
        assert "mock-model-1" in models
        assert "mock-model-2" in models
        
        # Test with nonexistent provider
        with pytest.raises(ValueError):
            self.factory.get_models_for_provider("nonexistent")
    
    def test_infer_provider_from_model(self) -> None:
        """Test inferring provider from model name."""
        # Test OpenAI models
        assert self.factory._infer_provider_from_model("gpt-4") == "openai"
        assert self.factory._infer_provider_from_model("gpt-3.5-turbo") == "openai"
        
        # Test our mock models
        assert self.factory._infer_provider_from_model("mock-model-1") == "mock"
        
        # Test unknown model
        assert self.factory._infer_provider_from_model("unknown-model") == ""
    
    @patch.dict("os.environ", {"OPENAI_API_KEY": "fake-key"})
    def test_get_resolver_for_task_with_provider(self) -> None:
        """Test getting resolver with provider specified in task."""
        task = Task(
            input_data="Test task",
            metadata={"provider": "openai", "model": "gpt-4"}
        )
        
        resolver = self.factory.get_resolver_for_task(task)
        assert isinstance(resolver, OpenAITaskResolver)
        assert resolver.model_name == "gpt-4"
    
    def test_get_resolver_for_task_with_model_only(self) -> None:
        """Test getting resolver with only model specified."""
        task = Task(
            input_data="Test task",
            metadata={"model": "mock-model-1"}
        )
        
        resolver = self.factory.get_resolver_for_task(task)
        assert isinstance(resolver, MockResolver)
        assert resolver.model_name == "mock-model-1"
    
    @patch.dict("os.environ", {"OPENAI_API_KEY": "fake-key"})
    def test_get_resolver_for_task_default(self) -> None:
        """Test getting default resolver when no provider or model specified."""
        task = Task(
            input_data="Test task",
            metadata={}
        )
        
        resolver = self.factory.get_resolver_for_task(task)
        assert isinstance(resolver, OpenAITaskResolver)
        assert resolver.model_name == "gpt-3.5-turbo"  # Default model
    
    def test_get_resolver_for_task_unknown_provider(self) -> None:
        """Test handling unknown provider."""
        task = Task(
            input_data="Test task",
            metadata={"provider": "unknown"}
        )
        
        with pytest.raises(ValueError) as excinfo:
            self.factory.get_resolver_for_task(task)
        assert "Unknown provider" in str(excinfo.value)
    
    def test_get_resolver_for_task_unknown_model(self) -> None:
        """Test handling unknown model."""
        task = Task(
            input_data="Test task",
            metadata={"model": "unknown-model"}
        )
        
        with pytest.raises(ValueError) as excinfo:
            self.factory.get_resolver_for_task(task)
        assert "Could not determine provider" in str(excinfo.value)
    
    def test_invalid_task(self) -> None:
        """Test handling invalid task."""
        with pytest.raises(ValueError) as excinfo:
            self.factory.get_resolver_for_task(None)  # type: ignore
        assert "Task cannot be None" in str(excinfo.value) 