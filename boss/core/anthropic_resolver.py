"""
Anthropic task resolver for the BOSS system.

This module provides an implementation of the BaseLLMTaskResolver for
the Anthropic Claude models via the Anthropic API.
"""
import json
import os
import asyncio
import logging
from typing import Optional, Dict, Any, List, Union, cast

# Check if anthropic is installed
try:
    import anthropic
    from anthropic.types import ContentBlock, Message, MessageParam
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    # Define dummy types for type checking
    class ContentBlock:
        pass
    class Message:
        pass
    MessageParam = Dict[str, Any]

from boss.core.task_models import Task, TaskResult, TaskError
from boss.core.task_status import TaskStatus
from boss.core.task_resolver import TaskResolverMetadata
from boss.core.base_llm_resolver import BaseLLMTaskResolver, LLMResponse


logger = logging.getLogger(__name__)


class AnthropicTaskResolver(BaseLLMTaskResolver):
    """
    TaskResolver implementation for Anthropic Claude models.
    
    This resolver uses the Anthropic API to generate completions
    for tasks using Claude models.
    """
    
    def __init__(
        self,
        model_name: str = "claude-3-sonnet-20240229",
        api_key: Optional[str] = None,
        metadata: Optional[TaskResolverMetadata] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout_seconds: int = 60,
        retry_attempts: int = 2,
        system_prompt: Optional[str] = None
    ):
        """
        Initialize a new AnthropicTaskResolver.
        
        Args:
            model_name: The name of the Anthropic model to use.
                Default is "claude-3-sonnet-20240229".
            api_key: The Anthropic API key to use. If not provided,
                looks for ANTHROPIC_API_KEY environment variable.
            metadata: Metadata about this resolver.
            temperature: Controls randomness in output generation.
                Lower values make output more deterministic (e.g., 0.2),
                while higher values make output more random (e.g., 0.8).
            max_tokens: Maximum number of tokens to generate. If None,
                uses the model's default.
            timeout_seconds: Maximum time to wait for a response from Anthropic.
            retry_attempts: Number of retry attempts for API failures.
            system_prompt: Default system prompt to use for all tasks.
        
        Raises:
            ImportError: If the anthropic package is not installed.
            ValueError: If no API key is provided and ANTHROPIC_API_KEY
                environment variable is not set.
        """
        # Check if anthropic is installed
        if not HAS_ANTHROPIC:
            raise ImportError(
                "anthropic package is not installed. Please install it with "
                "`pip install anthropic`."
            )
        
        # Get API key from environment if not provided
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "No API key provided. Either pass api_key parameter or "
                "set ANTHROPIC_API_KEY environment variable."
            )
        
        # Create the client
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key)
        
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
    
    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Generate a completion from Anthropic for the given prompt.
        
        Args:
            prompt: The prompt to generate a completion for.
            system_prompt: The system prompt to use, if any.
            temperature: Controls randomness in output generation.
                If None, uses the instance's default.
            max_tokens: Maximum number of tokens to generate.
                If None, uses the instance's default.
                
        Returns:
            An LLMResponse object containing the response from Anthropic.
            
        Raises:
            TaskError: If there's an error communicating with Anthropic.
        """
        # Use default values if not provided
        actual_temperature = temperature if temperature is not None else self.temperature
        actual_max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        # Add user's message
        messages: List[MessageParam] = [
            {"role": "user", "content": prompt}
        ]
        
        # Prepare the request
        try:
            # Set up parameters
            params = {
                "model": self.model_name,
                "messages": messages,
                "temperature": actual_temperature,
                "max_tokens": actual_max_tokens or 1024,  # Default to 1024 if not specified
            }
            
            # Add system prompt if provided
            if system_prompt:
                params["system"] = system_prompt
            
            # Make the API call with timeout
            timeout_ctx = asyncio.timeout if hasattr(asyncio, 'timeout') else asyncio.TimeoutError
            async with timeout_ctx(self.timeout_seconds):
                response = await self.client.messages.create(**params)
            
            # Extract response content
            content = response.content[0].text if response.content else ""
            
            # Calculate tokens used
            tokens_used = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
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
                    "type": response.type,
                    "role": response.role
                }
            )
        
        except anthropic.APIError as e:
            error_message = f"Anthropic API error: {str(e)}"
            self.logger.error(error_message)
            raise TaskError(
                message=error_message,
                error_type="AnthropicAPIError",
                details={"status_code": getattr(e, "status_code", None)}
            )
        
        except anthropic.APITimeoutError as e:
            error_message = f"Anthropic API timeout: {str(e)}"
            self.logger.error(error_message)
            raise TaskError(
                message=error_message,
                error_type="AnthropicTimeoutError"
            )
        
        except anthropic.AuthenticationError as e:
            error_message = f"Anthropic authentication error: {str(e)}"
            self.logger.error(error_message)
            raise TaskError(
                message=error_message,
                error_type="AnthropicAuthenticationError"
            )
        
        except anthropic.BadRequestError as e:
            error_message = f"Anthropic bad request: {str(e)}"
            self.logger.error(error_message)
            raise TaskError(
                message=error_message,
                error_type="AnthropicBadRequestError",
                details={"params": params}
            )
        
        except (asyncio.TimeoutError, Exception) as e:
            error_message = f"Error generating completion from Anthropic: {str(e)}"
            self.logger.error(error_message)
            raise TaskError(
                message=error_message,
                error_type="AnthropicUnexpectedError"
            )
    
    def can_handle(self, task: Task) -> bool:
        """
        Determine if this resolver can handle the given task.
        
        A task can be handled if it either:
        1. Specifies this resolver by name
        2. Requests an Anthropic model
        3. Doesn't specify any resolver or model, but this resolver is the default
        
        Args:
            task: The task to check.
            
        Returns:
            True if this resolver can handle the task, False otherwise.
        """
        # Check if the task explicitly specifies this resolver
        resolver_name = task.input_data.get("resolver_name", "")
        if resolver_name and resolver_name == self.metadata.name:
            return True
        
        # Check if the task specifies an Anthropic model
        llm_provider = task.input_data.get("llm_provider", "").lower()
        if llm_provider == "anthropic":
            return True
        
        # Check if the task specifies a model that starts with "claude"
        model = task.input_data.get("model", "").lower()
        if model.startswith("claude"):
            return True
        
        # If the task doesn't specify a resolver, provider, or model,
        # and this is the default resolver, we can handle it
        if not resolver_name and not llm_provider and not model:
            # Default behavior is determined by the factory, but here we'll
            # assume we're not the default unless explicitly configured
            return False
        
        return False 