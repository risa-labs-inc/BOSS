"""
XAI Task Resolver for BOSS

This module supports integration with xAI's Grok models.
It uses the official xai-grok-sdk package for API access.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Callable, Awaitable

from boss.core.base_llm_resolver import BaseLLMTaskResolver, LLMResponse
from boss.core.task_models import Task, TaskError, TaskMetadata
from boss.core.task_resolver import TaskResolverMetadata
from boss.core.task_retry import TaskRetryManager, BackoffStrategy
from boss.core.task_status import TaskStatus

logger = logging.getLogger(__name__)

# Try importing the xAI Grok SDK
try:
    from xai_grok_sdk import XAI
    XAI_SDK_AVAILABLE = True
except ImportError:
    XAI_SDK_AVAILABLE = False
    logger.warning("xai-grok-sdk not available. Install with 'poetry add xai-grok-sdk'")

class XAITaskResolver(BaseLLMTaskResolver):
    """
    Task resolver for xAI's Grok models.
    
    This resolver supports available Grok models including:
    - grok-2-1212 (latest stable Grok 2 version)
    - grok-beta (latest beta model)
    
    For API access, you need to provide an API key from xAI.
    """

    def __init__(
        self,
        model_name: str = "grok-2-1212",  # Default to stable version
        api_key: Optional[str] = None,
        metadata: Optional[TaskResolverMetadata] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout_seconds: int = 60,
        retry_attempts: int = 2,
        system_prompt: Optional[str] = None,
    ):
        """
        Initialize the XAI Task Resolver.
        
        Args:
            model_name: Name of the Grok model to use (default: grok-2-1212)
                Available models: grok-2-1212, grok-beta
            api_key: xAI API key (if None, uses XAI_API_KEY environment variable)
            metadata: Task resolver metadata
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate (None for model default)
            timeout_seconds: Timeout for API calls
            retry_attempts: Number of retry attempts for API calls
            system_prompt: Default system prompt to use
        """
        # Initialize base class
        super().__init__(
            model_name=model_name, 
            metadata=metadata or TaskResolverMetadata(
                name="xai",
                description="XAI Grok task resolver",
                version="1.0.0"
            ),
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            retry_attempts=retry_attempts,
            system_prompt=system_prompt
        )
        
        # Get API key
        self.api_key = api_key or os.environ.get("XAI_API_KEY")
        if not self.api_key and XAI_SDK_AVAILABLE:
            logger.warning("No API key provided. Set the XAI_API_KEY environment variable.")
        
        # Initialize client to None (will be created on first use)
        self.client = None
        
        # Validate model name
        if model_name not in ["grok-2-1212", "grok-beta"]:
            logger.warning(f"Model {model_name} may not be supported. Supported models: grok-2-1212, grok-beta")
        
        # Initialize retry manager with correct parameters
        self.retry_manager = TaskRetryManager(
            max_retries=retry_attempts,
            strategy=BackoffStrategy.EXPONENTIAL,
            base_delay_seconds=1.0,
            max_delay_seconds=10.0
        )

    def _initialize_client(self) -> bool:
        """Initialize the xAI client if not already initialized."""
        if not self.client and XAI_SDK_AVAILABLE and self.api_key:
            try:
                self.client = XAI(
                    api_key=self.api_key,
                    model=self.model_name
                )
                logger.info(f"Initialized xAI client with model {self.model_name}")
                return True
            except Exception as e:
                logger.error(f"Failed to initialize xAI client: {str(e)}")
                return False
        return self.client is not None

    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Generate a completion using the Grok API.
        
        Args:
            prompt: The prompt to send to the model
            system_prompt: Optional system prompt
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            
        Returns:
            LLMResponse with the generated text and metadata
            
        Raises:
            TaskError: If the API call fails
        """
        # Use provided values or fall back to defaults
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        system_prompt = system_prompt if system_prompt is not None else self.system_prompt
        
        # Create a dummy task for error handling
        dummy_task = Task(
            name="grok_completion",
            input_data={"prompt": prompt},
            metadata=TaskMetadata(
                owner="xai_resolver",
                tags=["grok", "completion"]
            )
        )
        
        # Check if xAI SDK is available
        if not XAI_SDK_AVAILABLE:
            error_msg = "xAI Grok SDK is not available. Install with 'poetry add xai-grok-sdk'"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # Initialize client if needed
        if not self._initialize_client():
            error_msg = "Failed to initialize xAI client"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # Prepare messages
        messages = []
        
        # Add system prompt if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add user message
        messages.append({"role": "user", "content": prompt})

        # Make API call
        try:
            # Execute in a thread to avoid blocking the event loop
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.invoke,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                ),
                timeout=self.timeout_seconds
            )
            
            # Extract content from response
            message = response.choices[0].message
            generated_text = message.content
            
            # Get token usage if available
            tokens_used = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                "total_tokens": getattr(response.usage, "total_tokens", 0)
            }
            
            # Return structured response
            return LLMResponse(
                content=generated_text,
                model_name=self.model_name,
                tokens_used=tokens_used,
                raw_response=response,
                metadata={
                    "finish_reason": getattr(response.choices[0], "finish_reason", "stop")
                }
            )
            
        except asyncio.TimeoutError:
            error_msg = f"Request to Grok API timed out after {self.timeout_seconds} seconds"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Error calling Grok API: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

    async def process_task(self, task: Task) -> Task:
        """Process the task using the Grok API."""
        # Extract resolver-specific parameters from the task
        resolver_params = task.input_data.get("resolver_params", {})
        prompt = task.input_data.get("prompt", "")
        system_prompt = task.input_data.get("system_prompt", self.system_prompt)
        
        try:
            # Generate completion
            llm_response = await self.generate_completion(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=resolver_params.get("temperature", self.temperature),
                max_tokens=resolver_params.get("max_tokens", self.max_tokens)
            )
            
            # Process the response and update the task
            task.result = self.process_response(llm_response, task)
            
        except Exception as e:
            task.error = {
                "message": str(e),
                "details": {"model": self.model_name}
            }
        
        return task
    
    def can_handle(self, task: Task) -> bool:
        """
        Check if this resolver can handle the given task.
        
        Args:
            task: The task to check
            
        Returns:
            True if this resolver can handle the task, False otherwise
        """
        # Check if the task explicitly requests this resolver
        resolver_name = task.input_data.get("resolver", "")
        if resolver_name.lower() in ["xai", "grok"]:
            return True
        
        # Check if the task explicitly requests a Grok model
        model = task.input_data.get("model", "")
        if model.lower().startswith("grok"):
            return True
        
        return False
    
    async def health_check(self) -> bool:
        """
        Perform a health check on the resolver.
        
        Returns:
            True if the resolver is healthy, False otherwise
        """
        health_info = {
            "status": "unknown",
            "model": self.model_name,
            "api_available": XAI_SDK_AVAILABLE,
            "client_initialized": self.client is not None,
            "timestamp": datetime.now().isoformat()
        }
        
        if not XAI_SDK_AVAILABLE:
            logger.error("xAI Grok SDK not available")
            return False
            
        if not self.api_key:
            logger.error("API key not configured")
            return False
            
        try:
            # Simple health check prompt
            test_prompt = "Respond with 'healthy' if you can read this message."
            response = await self.generate_completion(test_prompt)
            
            if "healthy" in response.content.lower():
                return True
            else:
                logger.warning("Health check response did not contain expected value")
                return False
                
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False 