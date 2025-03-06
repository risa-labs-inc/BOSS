"""
OpenAI TaskResolver for the BOSS system.

This module implements a TaskResolver that uses OpenAI's API to generate completions.
"""
import os
import json
import asyncio
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import openai
    from openai.types.chat import ChatCompletion
    from openai.types.chat.chat_completion import Choice
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

from boss.core.base_llm_resolver import BaseLLMTaskResolver, LLMResponse
from boss.core.task_resolver import TaskResolverMetadata
from boss.core.task_models import Task, TaskResult, TaskError


class OpenAITaskResolver(BaseLLMTaskResolver):
    """
    TaskResolver that uses OpenAI's API to generate completions.
    
    This resolver supports GPT-3.5 and GPT-4 models.
    """
    
    def __init__(
        self,
        model_name: str = "gpt-3.5-turbo",
        api_key: Optional[str] = None,
        metadata: Optional[TaskResolverMetadata] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout_seconds: int = 60,
        retry_attempts: int = 2,
        system_prompt: Optional[str] = None
    ):
        """
        Initialize a new OpenAITaskResolver.
        
        Args:
            model_name: The name of the OpenAI model to use.
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var).
            metadata: Metadata about the TaskResolver.
            temperature: The temperature for sampling (0-1).
            max_tokens: Maximum tokens to generate in the response.
            timeout_seconds: Timeout for API calls in seconds.
            retry_attempts: Number of times to retry on API errors.
            system_prompt: Default system prompt to use with all requests.
        """
        if not HAS_OPENAI:
            raise ImportError(
                "OpenAI package is not installed. "
                "Please install it with 'poetry add openai'."
            )
        
        # Create default metadata if not provided
        if metadata is None:
            metadata = TaskResolverMetadata(
                name="OpenAITaskResolver",
                description=f"TaskResolver using OpenAI's {model_name} model",
                version="0.1.0",
                tags=["llm", "openai", model_name]
            )
        
        super().__init__(
            model_name=model_name,
            metadata=metadata,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            retry_attempts=retry_attempts,
            system_prompt=system_prompt
        )
        
        # Initialize the OpenAI client
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key is required. Please provide it as api_key parameter "
                "or set the OPENAI_API_KEY environment variable."
            )
        
        self.client = openai.AsyncOpenAI(api_key=self.api_key)
    
    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Generate a completion from OpenAI.
        
        Args:
            prompt: The prompt to send to the LLM.
            system_prompt: Optional system prompt to use.
            temperature: Optional temperature to use.
            max_tokens: Optional max tokens to use.
            
        Returns:
            LLMResponse: The response from OpenAI.
            
        Raises:
            TaskError: If an error occurs when calling the OpenAI API.
        """
        # Use default values if not provided
        system_prompt = system_prompt or self.system_prompt
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        # Prepare messages for the API call
        messages = []
        
        # Add system prompt if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add user prompt
        messages.append({"role": "user", "content": prompt})
        
        self.logger.debug(f"Sending request to OpenAI API with model {self.model_name}")
        
        try:
            # Set up API parameters
            params = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
            }
            
            # Add max_tokens if provided
            if max_tokens:
                params["max_tokens"] = max_tokens
            
            # Make API call with timeout
            async_call = self.client.chat.completions.create(**params)
            completion = await asyncio.wait_for(
                async_call, timeout=self.timeout_seconds
            )
            
            # Process the response
            content = completion.choices[0].message.content or ""
            
            # Extract token usage
            tokens_used = {}
            if hasattr(completion, "usage") and completion.usage:
                tokens_used = {
                    "prompt_tokens": completion.usage.prompt_tokens,
                    "completion_tokens": completion.usage.completion_tokens,
                    "total_tokens": completion.usage.total_tokens
                }
            
            # Create and return the response
            return LLMResponse(
                content=content,
                raw_response=completion,
                model_name=self.model_name,
                tokens_used=tokens_used,
                metadata={
                    "finish_reason": completion.choices[0].finish_reason,
                    "created": completion.created
                }
            )
            
        except asyncio.TimeoutError:
            raise TaskError(
                task=None,  # Will be set by caller
                error_type="openai_timeout",
                message=f"OpenAI API call timed out after {self.timeout_seconds} seconds",
                details={"model": self.model_name}
            )
        except Exception as e:
            raise TaskError(
                task=None,  # Will be set by caller
                error_type="openai_api_error",
                message=f"Error calling OpenAI API: {str(e)}",
                details={"model": self.model_name, "exception": str(e)}
            )
    
    def can_handle(self, task: Task) -> bool:
        """
        Determine if this resolver can handle the given task.
        
        Args:
            task: The task to check.
            
        Returns:
            bool: True if this resolver can handle the task.
        """
        # Check if the task explicitly specifies an LLM provider
        provider = task.input_data.get("llm_provider", "").lower()
        if provider and provider != "openai":
            return False
        
        # Check if the task explicitly specifies a model
        model = task.input_data.get("model", "").lower()
        if model and not model.startswith("gpt"):
            return False
        
        # Default to accepting tasks that don't specify a provider or model
        return True 