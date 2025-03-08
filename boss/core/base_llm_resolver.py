"""
Base LLM TaskResolver for the BOSS system.

This module defines the foundational class for all LLM-based TaskResolvers.
"""
import json
import time
import logging
from abc import abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union, TypeVar, Type

from pydantic import BaseModel, Field

from boss.core.task_base import Task
from boss.core.task_result import TaskResult
from boss.core.task_error import TaskError
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_status import TaskStatus


T = TypeVar('T')


class LLMResponse:
    """
    Represents a response from an LLM provider.
    
    This class normalizes responses from different LLM providers
    to a standard format for easier processing.
    """
    def __init__(
        self,
        content: str,
        raw_response: Any = None,
        model_name: str = "",
        tokens_used: Optional[Dict[str, int]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a new LLMResponse.
        
        Args:
            content: The text content returned by the LLM.
            raw_response: The raw response object from the LLM provider.
            model_name: The name of the model that generated the response.
            tokens_used: Information about token usage.
            metadata: Additional metadata about the response.
        """
        self.content = content.strip()
        self.raw_response = raw_response
        self.model_name = model_name
        self.tokens_used = tokens_used or {}
        self.metadata = metadata or {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the response to a dictionary representation.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the response.
        """
        return {
            "content": self.content,
            "model_name": self.model_name,
            "tokens_used": self.tokens_used,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }
    
    def try_parse_json(self) -> Optional[Dict[str, Any]]:
        """
        Attempt to parse the content as JSON.
        
        Returns:
            Optional[Dict[str, Any]]: Parsed JSON or None if parsing failed.
        """
        try:
            # Look for JSON within triple backticks or JSON code blocks
            content = self.content
            if "```json" in content:
                # Extract JSON from code block
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                # Try to extract any code block content
                content = content.split("```")[1].split("```")[0].strip()
            
            return json.loads(content)
        except (json.JSONDecodeError, IndexError):
            # Try to find just the JSON part
            try:
                # Look for first { and last }
                start = content.find('{')
                end = content.rfind('}') + 1
                if start >= 0 and end > start:
                    return json.loads(content[start:end])
            except json.JSONDecodeError:
                return None
        
        return None


class BaseLLMTaskResolver(TaskResolver):
    """
    Base class for all LLM-based TaskResolvers.
    
    This class handles common functionality for interacting with LLM providers,
    such as prompt construction, response parsing, and error handling.
    """
    
    def __init__(
        self,
        model_name: str,
        metadata: Optional[TaskResolverMetadata] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout_seconds: int = 60,
        retry_attempts: int = 2,
        system_prompt: Optional[str] = None
    ):
        """
        Initialize a new BaseLLMTaskResolver.
        
        Args:
            model_name: The name of the LLM model to use.
            metadata: Metadata about the TaskResolver.
            temperature: The temperature for LLM sampling (0-1).
            max_tokens: Maximum tokens to generate in the response.
            timeout_seconds: Timeout for LLM API calls in seconds.
            retry_attempts: Number of times to retry on API errors.
            system_prompt: Default system prompt to use with all requests.
        """
        if metadata is None:
            metadata = TaskResolverMetadata(
                name=self.__class__.__name__,
                description=f"LLM TaskResolver using {model_name}"
            )
        
        super().__init__(metadata)
        
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts
        self.system_prompt = system_prompt
        
        self.logger = logging.getLogger(f"boss.llm_resolver.{self.metadata.name}")
    
    @abstractmethod
    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Generate a completion from the LLM provider.
        
        This method must be implemented by subclasses to handle
        the specific API of each LLM provider.
        
        Args:
            prompt: The prompt to send to the LLM.
            system_prompt: Optional system prompt to use (overrides default).
            temperature: Optional temperature to use (overrides default).
            max_tokens: Optional max tokens to use (overrides default).
            
        Returns:
            LLMResponse: The response from the LLM.
            
        Raises:
            TaskError: If an error occurs when calling the LLM provider.
        """
        pass
    
    def build_prompt(self, task: Task) -> str:
        """
        Build a prompt from the task input data.
        
        This method can be overridden by subclasses to implement
        custom prompt construction logic.
        
        Args:
            task: The task to build a prompt for.
            
        Returns:
            str: The constructed prompt.
        """
        # Default implementation uses the 'prompt' field from input_data
        # or falls back to the task description
        if 'prompt' in task.input_data:
            return str(task.input_data['prompt'])
        
        # Fall back to task description
        return task.description or f"Perform task: {task.name}"
    
    def get_system_prompt(self, task: Task) -> Optional[str]:
        """
        Get the system prompt to use for this task.
        
        Args:
            task: The task being processed.
            
        Returns:
            Optional[str]: The system prompt to use, or None to use the default.
        """
        # Check if the task has a system prompt in its input data
        if 'system_prompt' in task.input_data:
            return str(task.input_data['system_prompt'])
        
        # Fall back to the default system prompt
        return self.system_prompt
    
    def process_response(self, response: LLMResponse, task: Task) -> Dict[str, Any]:
        """
        Process the LLM response and extract useful information.
        
        This method can be overridden by subclasses to implement
        custom response processing logic.
        
        Args:
            response: The response from the LLM.
            task: The task being processed.
            
        Returns:
            Dict[str, Any]: The processed response data.
        """
        # Default implementation returns the content and metadata
        result = {
            "content": response.content,
            "model": response.model_name,
            "tokens": response.tokens_used,
            "timestamp": response.timestamp.isoformat()
        }
        
        # Try to parse JSON if requested
        if task.input_data.get('parse_json', False):
            json_data = response.try_parse_json()
            if json_data:
                result['json'] = json_data
        
        return result
    
    async def resolve(self, task: Task) -> TaskResult:
        """
        Resolve a task using the LLM provider.
        
        This implementation handles the full lifecycle of an LLM task:
        1. Build the prompt
        2. Call the LLM provider
        3. Process the response
        4. Return the result
        
        Args:
            task: The task to resolve.
            
        Returns:
            TaskResult: The result of resolving the task.
            
        Raises:
            TaskError: If an error occurs during task resolution.
        """
        # Build the prompt
        prompt = self.build_prompt(task)
        system_prompt = self.get_system_prompt(task)
        
        # Get temperature and max_tokens from task if provided
        temperature = task.input_data.get('temperature', self.temperature)
        max_tokens = task.input_data.get('max_tokens', self.max_tokens)
        
        self.logger.info(f"Processing LLM task {task.id} with model {self.model_name}")
        
        try:
            # Measure execution time
            start_time = time.time()
            
            # Generate completion from LLM
            response = await self.generate_completion(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Calculate execution time
            execution_time_ms = (time.time() - start_time) * 1000
            
            # Process the response
            result_data = self.process_response(response, task)
            
            # Return the result
            return TaskResult.success(
                task=task,
                output_data=result_data,
                message=f"Generated completion with model {self.model_name}",
                execution_time_ms=execution_time_ms
            )
            
        except Exception as e:
            # Handle all exceptions
            error_message = f"Error generating LLM completion: {str(e)}"
            self.logger.error(error_message, exc_info=True)
            
            # Create a TaskError
            raise TaskError(
                task=task,
                error_type="llm_generation_error",
                message=error_message,
                details={
                    "model": self.model_name,
                    "exception": str(e)
                }
            )
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the LLM integration.
        
        This method sends a simple prompt to the LLM provider
        to verify that the integration is working correctly.
        
        Returns:
            Dict[str, Any]: Health check results.
        """
        health_prompt = "Respond with 'healthy' if you can process this request."
        
        try:
            # Try to generate a simple completion
            response = await self.generate_completion(
                prompt=health_prompt,
                temperature=0.1,
                max_tokens=10
            )
            
            # Check if the response contains "healthy"
            is_healthy = "healthy" in response.content.lower()
            
            result = {
                "status": "healthy" if is_healthy else "degraded",
                "model": self.model_name,
                "response": response.content,
                "tokens_used": response.tokens_used,
                "metadata": self.metadata.to_dict(),
                "timestamp": datetime.now().isoformat()
            }
            
            if not is_healthy:
                result["warning"] = "LLM response did not contain 'healthy'"
            
            return result
            
        except Exception as e:
            # If an error occurs, the LLM integration is not healthy
            return {
                "status": "unhealthy",
                "model": self.model_name,
                "error": str(e),
                "metadata": self.metadata.to_dict(),
                "timestamp": datetime.now().isoformat()
            } 