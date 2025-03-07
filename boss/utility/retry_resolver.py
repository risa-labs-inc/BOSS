"""
RetryResolver for implementing advanced retry strategies.

This resolver provides advanced retry capabilities with different backoff
strategies, conditional retries based on error types, and comprehensive
retry statistics tracking.
"""

import asyncio
import logging
import random
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Callable, Type, cast

from boss.core.task_models import Task, TaskResult, TaskError
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_status import TaskStatus


class BackoffStrategy(str, Enum):
    """Supported backoff strategies for retries."""
    
    CONSTANT = "constant"  # Wait the same time between each retry
    LINEAR = "linear"      # Wait time increases linearly (base * attempt)
    EXPONENTIAL = "exponential"  # Wait time increases exponentially (base * 2^attempt)
    FIBONACCI = "fibonacci"  # Wait time follows Fibonacci sequence
    JITTER = "jitter"      # Random wait time within a range


class RetryCondition(str, Enum):
    """Conditions under which to retry."""
    
    ALWAYS = "always"     # Always retry regardless of error
    TIMEOUT = "timeout"   # Retry only on timeout errors
    NETWORK = "network"   # Retry only on network-related errors
    SERVER = "server"     # Retry only on server-side errors
    CUSTOM = "custom"     # Retry based on custom logic


class RetryResolver(TaskResolver):
    """
    Resolver for implementing advanced retry strategies.
    
    This resolver supports:
    - Multiple backoff strategies (constant, linear, exponential, etc.)
    - Conditional retries based on error types
    - Retry statistics tracking
    - Dynamic adjustment of retry parameters
    
    Attributes:
        metadata: Resolver metadata
        default_max_retries: Default maximum number of retry attempts
        default_backoff_strategy: Default strategy for timing between retries
        default_base_delay: Default base delay between retries (seconds)
        default_max_delay: Default maximum delay between retries (seconds)
        default_retry_condition: Default condition for when to retry
        retry_stats: Statistics about retry attempts and outcomes
    """
    
    def __init__(
        self,
        metadata: TaskResolverMetadata,
        default_max_retries: int = 3,
        default_backoff_strategy: str = BackoffStrategy.EXPONENTIAL,
        default_base_delay: float = 1.0,
        default_max_delay: float = 60.0,
        default_retry_condition: str = RetryCondition.ALWAYS
    ) -> None:
        """
        Initialize the RetryResolver.
        
        Args:
            metadata: Metadata for this resolver
            default_max_retries: Default maximum number of retry attempts
            default_backoff_strategy: Default backoff strategy
            default_base_delay: Default base delay between retries (seconds)
            default_max_delay: Default maximum delay between retries (seconds)
            default_retry_condition: Default condition for when to retry
        """
        super().__init__(metadata)
        self.logger = logging.getLogger(__name__)
        
        self.default_max_retries = default_max_retries
        self.default_backoff_strategy = default_backoff_strategy
        self.default_base_delay = default_base_delay
        self.default_max_delay = default_max_delay
        self.default_retry_condition = default_retry_condition
        
        # List of error patterns that are considered retriable for different categories
        self.retriable_errors = {
            RetryCondition.TIMEOUT.value: [
                "timeout", "timed out", "deadline exceeded", "too slow"
            ],
            RetryCondition.NETWORK.value: [
                "connection", "network", "socket", "unreachable", "dns", "reset", "closed"
            ],
            RetryCondition.SERVER.value: [
                "500", "502", "503", "504", "internal server error", "bad gateway", 
                "service unavailable", "gateway timeout", "overloaded"
            ]
        }
        
        # Initialize retry statistics
        self.retry_stats = {
            "total_attempts": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "by_strategy": {s: 0 for s in BackoffStrategy},
            "by_condition": {c: 0 for c in RetryCondition},
            "avg_attempts_until_success": 0.0
        }
    
    def can_handle(self, task: Task) -> bool:
        """
        Determine if this resolver can handle the task.
        
        Args:
            task: The task to check
            
        Returns:
            True if this resolver can handle the task, False otherwise
        """
        # Check if task specifically requests this resolver
        resolver_name = task.metadata.owner if task.metadata else ""
        if resolver_name == self.metadata.name or resolver_name == "":
            # Check if the task has an operation field and if it's supported
            if isinstance(task.input_data, dict):
                operation = task.input_data.get("operation", "")
                supported_ops = [
                    "retry", "get_stats", "clear_stats", "configure", 
                    "is_retriable", "calculate_delay"
                ]
                return operation in supported_ops
        
        return False
    
    async def resolve(self, task: Task) -> TaskResult:
        """
        Resolve the retry operation task.
        
        Args:
            task: The retry operation task to resolve
            
        Returns:
            The result of the retry operation
        """
        # Validate task input
        if not isinstance(task.input_data, dict):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message="Input data must be a dictionary"
            )
        
        try:
            input_data = task.input_data
            operation = input_data.get("operation", "")
            
            if operation == "retry":
                result = await self._handle_retry(input_data)
                return TaskResult(
                    task_id=task.id,
                    status=result.get("status", TaskStatus.ERROR),
                    output_data=result,
                    message=result.get("message", "")
                )
            
            elif operation == "get_stats":
                result = self._handle_get_stats()
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data=result
                )
            
            elif operation == "clear_stats":
                result = self._handle_clear_stats()
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data=result
                )
            
            elif operation == "configure":
                config = input_data.get("config", {})
                result = self._handle_configure(config)
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data=result
                )
            
            elif operation == "is_retriable":
                error = input_data.get("error", "")
                condition = input_data.get("condition", self.default_retry_condition)
                result = {
                    "retriable": self._is_retriable_error(error, condition),
                    "error": error,
                    "condition": condition
                }
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data=result
                )
            
            elif operation == "calculate_delay":
                attempt = input_data.get("attempt", 1)
                strategy = input_data.get("strategy", self.default_backoff_strategy)
                base_delay = input_data.get("base_delay", self.default_base_delay)
                max_delay = input_data.get("max_delay", self.default_max_delay)
                
                delay = self._calculate_delay(attempt, strategy, base_delay, max_delay)
                result = {
                    "delay": delay,
                    "attempt": attempt,
                    "strategy": strategy
                }
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data=result
                )
            
            else:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    message=f"Unknown operation: {operation}"
                )
        
        except Exception as e:
            self.logger.error(f"Error resolving task: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message=f"Error resolving task: {str(e)}"
            )
    
    async def _handle_retry(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle retry operation.
        
        Args:
            input_data: The retry input data
            
        Returns:
            A dict with the retry result
        """
        # Extract retry parameters
        max_retries = input_data.get("max_retries", self.default_max_retries)
        backoff_strategy = input_data.get("strategy", self.default_backoff_strategy)
        base_delay = input_data.get("base_delay", self.default_base_delay)
        max_delay = input_data.get("max_delay", self.default_max_delay)
        retry_condition = input_data.get("condition", self.default_retry_condition)
        
        # Extract the operation to be retried
        operation = input_data.get("target_operation")
        if not operation:
            return {
                "status": TaskStatus.ERROR,
                "success": False,
                "message": "Missing 'target_operation' field",
                "attempts": 0
            }
        
        # Extract the function to be called
        func = input_data.get("func")
        if not callable(func):
            return {
                "status": TaskStatus.ERROR,
                "success": False,
                "message": "Missing or invalid 'func' field",
                "attempts": 0
            }
        
        args = input_data.get("args", [])
        kwargs = input_data.get("kwargs", {})
        
        # Initialize retry counter and result
        attempts = 0
        result = None
        last_error = None
        
        # Increment the total attempts counter
        self.retry_stats["by_strategy"][backoff_strategy] = self.retry_stats["by_strategy"].get(backoff_strategy, 0) + 1
        self.retry_stats["by_condition"][retry_condition] = self.retry_stats["by_condition"].get(retry_condition, 0) + 1
        
        # Start retry loop
        while attempts <= max_retries:
            try:
                # Call the function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Success! Return the result
                if attempts > 0:
                    self.retry_stats["successful_retries"] += 1
                    # Update average attempts until success
                    total_successful = self.retry_stats["successful_retries"]
                    current_avg = self.retry_stats["avg_attempts_until_success"]
                    new_avg = ((current_avg * (total_successful - 1)) + attempts) / total_successful
                    self.retry_stats["avg_attempts_until_success"] = new_avg
                
                return {
                    "status": TaskStatus.COMPLETED,
                    "success": True,
                    "result": result,
                    "attempts": attempts + 1,
                    "operation": operation
                }
            
            except Exception as e:
                attempts += 1
                self.retry_stats["total_attempts"] += 1
                last_error = str(e)
                
                # Check if we should retry
                if attempts > max_retries or not self._is_retriable_error(last_error, retry_condition):
                    self.retry_stats["failed_retries"] += 1
                    break
                
                # Calculate delay based on strategy
                delay = self._calculate_delay(attempts, backoff_strategy, base_delay, max_delay)
                
                # Log the retry attempt
                self.logger.info(f"Retry attempt {attempts}/{max_retries} for operation '{operation}'. "
                                 f"Error: {last_error}. Waiting {delay}s before next attempt.")
                
                # Wait before retrying
                await asyncio.sleep(delay)
        
        # If we get here, all retries failed
        return {
            "status": TaskStatus.ERROR,
            "success": False,
            "error": last_error,
            "attempts": attempts,
            "operation": operation,
            "message": f"Operation failed after {attempts} attempts: {last_error}"
        }
    
    def _calculate_delay(self, attempt: int, strategy: str, base_delay: float, max_delay: float) -> float:
        """
        Calculate the delay for the next retry attempt.
        
        Args:
            attempt: The current attempt number (1-based)
            strategy: The backoff strategy to use
            base_delay: The base delay time in seconds
            max_delay: The maximum delay time in seconds
            
        Returns:
            The delay time in seconds
        """
        if strategy == BackoffStrategy.CONSTANT:
            delay = base_delay
        
        elif strategy == BackoffStrategy.LINEAR:
            delay = base_delay * attempt
        
        elif strategy == BackoffStrategy.EXPONENTIAL:
            delay = base_delay * (2 ** (attempt - 1))
        
        elif strategy == BackoffStrategy.FIBONACCI:
            # Calculate Fibonacci number for the attempt
            a, b = 1, 1
            for _ in range(attempt - 1):
                a, b = b, a + b
            delay = base_delay * a
        
        elif strategy == BackoffStrategy.JITTER:
            # Add some randomness to avoid thundering herd
            max_jitter = base_delay * attempt
            delay = base_delay + random.uniform(0, max_jitter)
        
        else:
            # Default to exponential backoff
            delay = base_delay * (2 ** (attempt - 1))
        
        # Ensure delay is not more than max_delay
        return min(delay, max_delay)
    
    def _is_retriable_error(self, error: str, condition: str) -> bool:
        """
        Determine if an error is retriable based on the retry condition.
        
        Args:
            error: The error message or description
            condition: The retry condition
            
        Returns:
            True if the error is retriable, False otherwise
        """
        if condition == RetryCondition.ALWAYS:
            return True
        
        if condition in self.retriable_errors:
            # Check if any of the error patterns for this condition match
            error_patterns = self.retriable_errors[condition]
            error_lower = error.lower()
            return any(pattern in error_lower for pattern in error_patterns)
        
        if condition == RetryCondition.CUSTOM:
            # Custom logic should be implemented by the caller
            # and specified in the input_data.
            return True
        
        return False
    
    def _handle_get_stats(self) -> Dict[str, Any]:
        """
        Handle get_stats operation.
        
        Returns:
            A dict with retry statistics
        """
        success_rate = 0.0
        total_retries = self.retry_stats["successful_retries"] + self.retry_stats["failed_retries"]
        if total_retries > 0:
            success_rate = float(self.retry_stats["successful_retries"]) / float(total_retries)
        
        return {
            "stats": self.retry_stats,
            "success_rate": success_rate,
            "total_retries": total_retries,
            "config": {
                "max_retries": self.default_max_retries,
                "backoff_strategy": self.default_backoff_strategy,
                "base_delay": self.default_base_delay,
                "max_delay": self.default_max_delay,
                "retry_condition": self.default_retry_condition
            }
        }
    
    def _handle_clear_stats(self) -> Dict[str, Any]:
        """
        Handle clear_stats operation.
        
        Returns:
            A dict with the operation result
        """
        old_stats = self.retry_stats.copy()
        
        self.retry_stats = {
            "total_attempts": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "by_strategy": {s: 0 for s in BackoffStrategy},
            "by_condition": {c: 0 for c in RetryCondition},
            "avg_attempts_until_success": 0.0
        }
        
        return {
            "success": True,
            "previous_stats": old_stats
        }
    
    def _handle_configure(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle configure operation.
        
        Args:
            config: New configuration settings
            
        Returns:
            A dict with the operation result
        """
        changes = {}
        
        # Update max retries if provided
        if "max_retries" in config:
            self.default_max_retries = config["max_retries"]
            changes["max_retries"] = self.default_max_retries
        
        # Update backoff strategy if provided
        if "backoff_strategy" in config:
            strategy = config["backoff_strategy"]
            if strategy in [s.value for s in BackoffStrategy]:
                self.default_backoff_strategy = strategy
                changes["backoff_strategy"] = self.default_backoff_strategy
        
        # Update base delay if provided
        if "base_delay" in config:
            self.default_base_delay = config["base_delay"]
            changes["base_delay"] = self.default_base_delay
        
        # Update max delay if provided
        if "max_delay" in config:
            self.default_max_delay = config["max_delay"]
            changes["max_delay"] = self.default_max_delay
        
        # Update retry condition if provided
        if "retry_condition" in config:
            condition = config["retry_condition"]
            if condition in [c.value for c in RetryCondition]:
                self.default_retry_condition = condition
                changes["retry_condition"] = self.default_retry_condition
        
        # Update retriable errors if provided
        if "retriable_errors" in config:
            for condition, errors in config["retriable_errors"].items():
                if condition in self.retriable_errors:
                    self.retriable_errors[condition] = errors
                    changes.setdefault("retriable_errors", {})[condition] = errors
        
        return {
            "success": True,
            "changes": changes
        }
    
    async def health_check(self) -> bool:
        """
        Perform a health check for this resolver.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            # Define a test function that fails a few times then succeeds
            attempt_counter = [0]
            
            def test_func() -> str:
                attempt_counter[0] += 1
                if attempt_counter[0] < 3:
                    raise ValueError("Test error")
                return "Success"
            
            # Retry the function
            retry_input = {
                "operation": "retry",
                "target_operation": "test_func",
                "func": test_func,
                "max_retries": 3,
                "strategy": BackoffStrategy.CONSTANT.value,
                "base_delay": 0.01,  # Very short delay for testing
                "condition": RetryCondition.ALWAYS.value
            }
            
            result = await self._handle_retry(retry_input)
            
            # Check that it succeeded after retries
            if not result.get("success", False) or result.get("attempts", 0) != 3:
                self.logger.error("Health check failed: Retry mechanism not working correctly")
                return False
            
            # Also test the delay calculation
            delay = self._calculate_delay(2, BackoffStrategy.EXPONENTIAL.value, 1.0, 10.0)
            if delay != 2.0:  # 1.0 * 2^(2-1) = 2.0
                self.logger.error(f"Health check failed: Incorrect delay calculation ({delay} != 2.0)")
                return False
            
            # All tests passed
            return True
            
        except Exception as e:
            self.logger.error(f"Health check failed with exception: {str(e)}")
            return False 