"""
TogetherAI task resolver for the BOSS system.

This module provides an implementation of the BaseLLMTaskResolver for
various models hosted on Together AI's platform.
"""
import os
import json
import asyncio
import logging
from typing import Optional, Dict, Any, List, Union, cast

# Check if together package is installed
try:
    import together  # type: ignore
    from together import Together, AsyncTogether  # type: ignore
    HAS_TOGETHER = True
except ImportError:
    HAS_TOGETHER = False

from boss.core.task_models import Task, TaskResult, TaskError
from boss.core.task_status import TaskStatus
from boss.core.task_resolver import TaskResolverMetadata
from boss.core.base_llm_resolver import BaseLLMTaskResolver, LLMResponse


logger = logging.getLogger(__name__)


class TogetherAITaskResolver(BaseLLMTaskResolver):
    """
    TaskResolver implementation for models hosted on Together AI.
    
    This resolver uses the Together AI API to generate completions for tasks
    using a variety of open-source models like Mixtral, Llama, etc.
    """
    
    def __init__(
        self,
        model_name: str = "mistralai/Mixtral-8x7B-Instruct-v0.1",
        api_key: Optional[str] = None,
        metadata: Optional[TaskResolverMetadata] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 1024,
        timeout_seconds: int = 60,
        retry_attempts: int = 2,
        system_prompt: Optional[str] = None
    ):
        """
        Initialize a new TogetherAITaskResolver.
        
        Args:
            model_name: The name of the Together AI model to use.
                Default is "mistralai/Mixtral-8x7B-Instruct-v0.1".
            api_key: The Together AI API key to use. If not provided,
                looks for TOGETHER_API_KEY environment variable.
            metadata: Metadata about this resolver.
            temperature: Controls randomness in output generation.
                Lower values make output more deterministic.
            max_tokens: Maximum number of tokens to generate.
            timeout_seconds: Maximum time to wait for a response.
            retry_attempts: Number of retry attempts for API failures.
            system_prompt: Default system prompt to use for all tasks.
        
        Raises:
            ImportError: If the together package is not installed.
            ValueError: If no API key is provided and TOGETHER_API_KEY
                environment variable is not set.
        """
        # Check if together is installed
        if not HAS_TOGETHER:
            raise ImportError(
                "together package is not installed. Please install it with "
                "poetry add together"
            )
        
        # Get API key from environment if not provided
        self.api_key = api_key or os.environ.get("TOGETHER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "No API key provided. Either pass api_key parameter or "
                "set TOGETHER_API_KEY environment variable."
            )
        
        # Create default metadata if not provided
        if metadata is None:
            metadata = TaskResolverMetadata(
                name="TogetherAITaskResolver",
                version="0.3.0",  # Update version to reflect new API changes
                description=f"TaskResolver using Together AI's {model_name} model",
                tags=["llm", "together", model_name]
            )
        
        # Initialize the base class
        super().__init__(
            model_name=model_name,
            metadata=metadata,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            retry_attempts=retry_attempts,
            system_prompt=system_prompt
        )
        
        # Create the client using the v1.4.1 API
        self.client = AsyncTogether(api_key=self.api_key)
        
        # Determine if the model is a chat model based on the model name
        # This approach is more robust and accounts for all Together.AI supported models
        self.is_chat_model = self._is_chat_model(model_name)
        
    def _is_chat_model(self, model_name: str) -> bool:
        """
        Determine if a model is a chat model based on its name.
        
        Args:
            model_name: The name of the model.
            
        Returns:
            True if the model is a chat model, False otherwise.
        """
        # Most models on Together AI are now chat models
        # The few exceptions are specifically marked as "completion" models
        if "completion" in model_name.lower():
            return False
            
        # Known chat models include LLaMA, Mistral, Mixtral, Falcon, etc.
        chat_model_identifiers = [
            "llama", "mistral", "mixtral", "falcon", "gpt", 
            "claude", "phi", "stability", "qwen", "yi", "gemma"
        ]
        
        return any(identifier in model_name.lower() for identifier in chat_model_identifiers)
    
    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Generate a completion from Together AI for the given prompt.
        
        Args:
            prompt: The prompt to generate a completion for.
            system_prompt: The system prompt to use, if any.
            temperature: Controls randomness in output generation.
                If None, uses the instance's default.
            max_tokens: Maximum number of tokens to generate.
                If None, uses the instance's default.
            
        Returns:
            An LLMResponse object containing the response from Together AI.
            
        Raises:
            TaskError: If there's an error communicating with Together AI.
        """
        # Use default values if not provided
        actual_temperature = temperature if temperature is not None else self.temperature
        actual_max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        try:
            if self.is_chat_model:
                # Create messages list for chat models
                messages = []
                
                # Add system message if provided
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                
                # Add user's message
                messages.append({"role": "user", "content": prompt})
                
                self.logger.debug(f"Sending chat request to Together AI with model {self.model_name}")
                
                # Set up timeout
                async with asyncio.timeout(self.timeout_seconds):
                    # Make API call using the v1.4.1 API
                    response = await self.client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        temperature=actual_temperature,
                        max_tokens=actual_max_tokens
                    )
                
                # Extract content from chat completion
                content = response.choices[0].message.content
                
                # Calculate tokens used
                tokens_used = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
                
                # Return the response
                return LLMResponse(
                    content=content,
                    raw_response=response,
                    model_name=self.model_name,
                    tokens_used=tokens_used,
                    metadata={
                        "id": response.id,
                        "model": response.model,
                        "finish_reason": response.choices[0].finish_reason if response.choices else None,
                        "created": response.created if hasattr(response, "created") else None
                    }
                )
            else:
                # For non-chat models, use the completions API
                self.logger.debug(f"Sending completion request to Together AI with model {self.model_name}")
                
                # Set up timeout
                async with asyncio.timeout(self.timeout_seconds):
                    # Make API call using the v1.4.1 API
                    response = await self.client.completions.create(
                        model=self.model_name,
                        prompt=prompt,
                        temperature=actual_temperature,
                        max_tokens=actual_max_tokens
                    )
                
                # Extract content from completion
                content = response.choices[0].text
                
                # Calculate tokens used
                tokens_used = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
                
                # Return the response
                return LLMResponse(
                    content=content,
                    raw_response=response,
                    model_name=self.model_name,
                    tokens_used=tokens_used,
                    metadata={
                        "id": response.id,
                        "model": response.model,
                        "finish_reason": response.choices[0].finish_reason if response.choices else None,
                        "created": response.created if hasattr(response, "created") else None
                    }
                )
                
        except asyncio.TimeoutError:
            error_message = f"Timeout calling Together AI API after {self.timeout_seconds}s"
            self.logger.error(error_message)
            
            # Create a dummy task for the error
            dummy_task = Task(id="dummy", name="dummy")
            
            # Raise a TaskError for proper handling
            raise TaskError(
                task=dummy_task,
                error_type="TogetherAITimeoutError",
                message=error_message,
                details={"model": self.model_name, "timeout_seconds": self.timeout_seconds}
            )
        except Exception as e:
            error_message = f"Error generating completion from Together AI: {str(e)}"
            self.logger.error(error_message)
            
            # Create a dummy task for the error
            dummy_task = Task(id="dummy", name="dummy")
            
            # Raise a TaskError for proper handling
            raise TaskError(
                task=dummy_task,
                error_type="TogetherAIError",
                message=error_message,
                details={"model": self.model_name, "exception": str(e)}
            )
    
    def can_handle(self, task: Task) -> bool:
        """
        Determine if this resolver can handle the given task.
        
        Args:
            task: The task to check.
            
        Returns:
            True if this resolver can handle the task, False otherwise.
        """
        # Check if the task explicitly specifies this resolver
        resolver_name = task.input_data.get("resolver_name", "")
        if resolver_name and resolver_name == self.metadata.name:
            return True
        
        # Check if the task specifies Together AI provider
        llm_provider = task.input_data.get("llm_provider", "").lower()
        if llm_provider in ["together", "togetherai", "together_ai"]:
            return True
        
        # Check if the task specifies a model hosted on Together AI
        model = task.input_data.get("model", "").lower()
        if any(x in model for x in ["mixtral", "llama", "mistral", "yi", "phi", "falcon", "gemma"]):
            return True
        
        # If the task doesn't specify a resolver, provider, or model,
        # we don't handle it by default
        return False 