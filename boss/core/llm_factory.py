"""
LLM TaskResolver Factory for the BOSS system.

This module provides a factory for creating and managing LLM TaskResolvers
based on configuration or task requirements.
"""
import os
import logging
from typing import Dict, List, Optional, Type, Union

from boss.core.task_resolver import TaskResolver
from boss.core.base_llm_resolver import BaseLLMTaskResolver
from boss.core.openai_resolver import OpenAITaskResolver
from boss.core.task_models import Task


class LLMTaskResolverFactory:
    """
    Factory for creating and managing LLM TaskResolvers.
    
    This class maintains a registry of available LLM providers and
    creates the appropriate TaskResolver based on configuration or task requirements.
    """
    
    def __init__(self):
        """
        Initialize a new LLMTaskResolverFactory.
        """
        self.logger = logging.getLogger("boss.llm_factory")
        
        # Registry of available LLM provider classes
        self._resolver_classes: Dict[str, Type[BaseLLMTaskResolver]] = {}
        
        # Registry of initialized resolver instances
        self._resolver_instances: Dict[str, BaseLLMTaskResolver] = {}
        
        # Register default providers
        self.register_provider("openai", OpenAITaskResolver)
        
        # Try to import and register other providers if available
        self._try_register_anthropic()
        self._try_register_together_ai()
        self._try_register_xai()
    
    def _try_register_anthropic(self) -> None:
        """
        Try to import and register the Anthropic provider if available.
        """
        try:
            from boss.core.anthropic_resolver import AnthropicTaskResolver
            self.register_provider("anthropic", AnthropicTaskResolver)
        except ImportError:
            self.logger.debug("Anthropic provider not available")
    
    def _try_register_together_ai(self) -> None:
        """
        Try to import and register the Together AI provider if available.
        """
        try:
            from boss.core.together_ai_resolver import TogetherAITaskResolver
            self.register_provider("together", TogetherAITaskResolver)
        except ImportError:
            self.logger.debug("Together AI provider not available")
    
    def _try_register_xai(self) -> None:
        """
        Try to import and register the xAI provider if available.
        """
        try:
            from boss.core.xai_resolver import XAITaskResolver
            self.register_provider("xai", XAITaskResolver)
        except ImportError:
            self.logger.debug("xAI provider not available")
    
    def register_provider(self, provider_name: str, resolver_class: Type[BaseLLMTaskResolver]) -> None:
        """
        Register a new LLM provider.
        
        Args:
            provider_name: The name of the provider.
            resolver_class: The TaskResolver class for the provider.
        """
        provider_name = provider_name.lower()
        self._resolver_classes[provider_name] = resolver_class
        self.logger.info(f"Registered LLM provider: {provider_name}")
    
    def get_resolver_for_task(self, task: Task) -> BaseLLMTaskResolver:
        """
        Get an appropriate resolver for the given task.
        
        This method examines the task's input data to determine which
        LLM provider and model to use.
        
        Args:
            task: The task to resolve.
            
        Returns:
            BaseLLMTaskResolver: An appropriate resolver for the task.
            
        Raises:
            ValueError: If no appropriate resolver can be found.
        """
        # Extract provider and model information from task
        provider = task.input_data.get("llm_provider", "").lower()
        model = task.input_data.get("model", "")
        
        # If provider is specified, use it
        if provider:
            return self.get_resolver(provider, model)
        
        # If model is specified, infer provider from model
        if model:
            provider = self._infer_provider_from_model(model)
            if provider:
                return self.get_resolver(provider, model)
        
        # Use default provider (OpenAI)
        return self.get_resolver("openai")
    
    def get_resolver(self, provider: str, model: Optional[str] = None) -> BaseLLMTaskResolver:
        """
        Get a resolver for the specified provider and model.
        
        Args:
            provider: The LLM provider to use.
            model: The specific model to use (optional).
            
        Returns:
            BaseLLMTaskResolver: A resolver for the specified provider and model.
            
        Raises:
            ValueError: If the provider is not registered.
        """
        provider = provider.lower()
        
        # Check if provider is registered
        if provider not in self._resolver_classes:
            raise ValueError(f"LLM provider '{provider}' is not registered")
        
        # Create a cache key for this provider/model combination
        cache_key = f"{provider}:{model}" if model else provider
        
        # Check if we already have an instance for this combination
        if cache_key in self._resolver_instances:
            return self._resolver_instances[cache_key]
        
        # Create a new instance
        resolver_class = self._resolver_classes[provider]
        
        # Initialize with model if provided
        if model:
            resolver = resolver_class(model_name=model)
        else:
            resolver = resolver_class()
        
        # Cache the instance
        self._resolver_instances[cache_key] = resolver
        
        return resolver
    
    def _infer_provider_from_model(self, model: str) -> Optional[str]:
        """
        Infer the LLM provider from a model name.
        
        Args:
            model: The model name.
            
        Returns:
            Optional[str]: The inferred provider, or None if unknown.
        """
        model = model.lower()
        
        if model.startswith(("gpt", "davinci", "curie", "babbage", "ada")):
            return "openai"
        elif model.startswith(("claude", "anthropic")):
            return "anthropic"
        elif model.startswith("grok"):
            return "xai"
        elif model.startswith("llama") or model.startswith("mistral"):
            return "together"
        
        return None
    
    def get_available_providers(self) -> List[str]:
        """
        Get a list of available LLM providers.
        
        Returns:
            List[str]: A list of registered provider names.
        """
        return list(self._resolver_classes.keys())
    
    def get_available_models(self, provider: Optional[str] = None) -> List[str]:
        """
        Get a list of available models for a provider.
        
        Args:
            provider: The provider to get models for (optional).
            
        Returns:
            List[str]: A list of available model names.
        """
        # If no provider specified, return models for all providers
        if not provider:
            all_models = []
            for provider in self._resolver_classes:
                all_models.extend(self._get_provider_models(provider))
            return all_models
        
        # Get models for specific provider
        provider = provider.lower()
        if provider not in self._resolver_classes:
            raise ValueError(f"LLM provider '{provider}' is not registered")
        
        return self._get_provider_models(provider)
    
    def _get_provider_models(self, provider: str) -> List[str]:
        """
        Get available models for a specific provider.
        
        Args:
            provider: The provider to get models for.
            
        Returns:
            List[str]: A list of available model names.
        """
        # Map provider to available models
        provider_models = {
            "openai": ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"],
            "anthropic": ["claude-2", "claude-instant"],
            "together": ["llama-2-7b", "llama-2-13b", "llama-2-70b", "mistral-7b"],
            "xai": ["grok-1"]
        }
        
        return provider_models.get(provider, []) 