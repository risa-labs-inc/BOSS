"""
TaskRetryManager for the BOSS system.

This module provides functionality for handling task retries with different backoff strategies.
"""
import asyncio
import math
import random
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, Optional, TypeVar, Union, List

from boss.core.task_base import Task
from boss.core.task_result import TaskResult
from boss.core.task_status import TaskStatus


class BackoffStrategy(Enum):
    """
    Enum representing different backoff strategies for retrying tasks.
    """
    CONSTANT = auto()      # Always wait the same amount of time
    LINEAR = auto()        # Wait time increases linearly with retry count
    EXPONENTIAL = auto()   # Wait time increases exponentially with retry count
    FIBONACCI = auto()     # Wait time follows Fibonacci sequence
    RANDOM = auto()        # Wait a random time between min and max
    JITTERED = auto()      # Exponential backoff with jitter


# Type variable for the resolver function
T = TypeVar('T')


class TaskRetryManager:
    """
    Manages retries for tasks with configurable backoff strategies.
    """
    def __init__(
        self,
        max_retries: int = 3,
        strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
        base_delay_seconds: float = 1.0,
        max_delay_seconds: float = 60.0,
        jitter_factor: float = 0.1
    ):
        """
        Initialize a new TaskRetryManager.
        
        Args:
            max_retries: Maximum number of retry attempts.
            strategy: The backoff strategy to use.
            base_delay_seconds: Base delay between retries in seconds.
            max_delay_seconds: Maximum delay between retries in seconds.
            jitter_factor: Random jitter factor (0-1) to add to calculated delay.
        """
        self.max_retries = max_retries
        self.strategy = strategy
        self.base_delay = base_delay_seconds
        self.max_delay = max_delay_seconds
        self.jitter_factor = jitter_factor
        
        # Fibonacci sequence cache
        self.fibonacci_cache = {0: 0, 1: 1}
    
    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate the delay for a given retry attempt based on the strategy.
        
        Args:
            attempt: The current retry attempt (0-indexed).
            
        Returns:
            float: The delay in seconds.
        """
        if attempt <= 0:
            return 0
        
        # Calculate base delay based on strategy
        if self.strategy == BackoffStrategy.CONSTANT:
            delay = self.base_delay
        
        elif self.strategy == BackoffStrategy.LINEAR:
            delay = self.base_delay * attempt
        
        elif self.strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.base_delay * (2 ** (attempt - 1))
        
        elif self.strategy == BackoffStrategy.FIBONACCI:
            delay = self.base_delay * self._fibonacci(attempt)
        
        elif self.strategy == BackoffStrategy.RANDOM:
            delay = random.uniform(self.base_delay, self.max_delay)
        
        elif self.strategy == BackoffStrategy.JITTERED:
            # Exponential backoff with jitter
            temp_delay = self.base_delay * (2 ** (attempt - 1))
            jitter = random.uniform(-self.jitter_factor, self.jitter_factor) * temp_delay
            delay = temp_delay + jitter
        
        else:
            # Default to exponential
            delay = self.base_delay * (2 ** (attempt - 1))
        
        # Apply max delay cap
        return min(delay, self.max_delay)
    
    def _fibonacci(self, n: int) -> int:
        """
        Calculate the nth Fibonacci number.
        
        Uses a cache to avoid recalculation.
        
        Args:
            n: The index in the Fibonacci sequence.
            
        Returns:
            int: The nth Fibonacci number.
        """
        if n in self.fibonacci_cache:
            return self.fibonacci_cache[n]
        
        # Calculate and cache
        self.fibonacci_cache[n] = self._fibonacci(n-1) + self._fibonacci(n-2)
        return self.fibonacci_cache[n]
    
    def should_retry(self, task: Task, result: Optional[TaskResult] = None) -> bool:
        """
        Determine if a task should be retried based on its current state.
        
        Args:
            task: The task to check.
            result: Optional task result from the last attempt.
            
        Returns:
            bool: True if the task should be retried, False otherwise.
        """
        # Don't retry if we've hit the maximum retries
        if task.metadata.retry_count >= self.max_retries:
            return False
        
        # Don't retry tasks in terminal states
        if task.status.is_terminal():
            return False
        
        # Don't retry if the task has expired
        if task.is_expired():
            return False
        
        # Check if the result indicates retry is needed
        if result:
            # Only retry on errors, not successful completions
            return result.status == TaskStatus.ERROR
        
        # If no result is provided, use the task status
        return task.status == TaskStatus.ERROR or task.status == TaskStatus.RETRYING
    
    async def execute_with_retry(
        self,
        task: Task,
        resolver_func: Callable[[Task], T],
        error_handler: Optional[Callable[[Task, Exception, int], None]] = None
    ) -> Union[T, TaskResult]:
        """
        Execute a resolver function with automatic retries.
        
        Args:
            task: The task to execute.
            resolver_func: The function to execute the task.
            error_handler: Optional function to call on each error.
            
        Returns:
            Union[T, TaskResult]: The result of the resolver function or a failure TaskResult.
        """
        attempt = 0
        last_exception = None
        
        while attempt <= self.max_retries:
            try:
                # If this isn't the first attempt, increment retry count
                if attempt > 0:
                    task.metadata.retry_count += 1
                    task.metadata.updated_at = datetime.now()
                    
                    # Update task status to RETRYING
                    if task.status != TaskStatus.RETRYING:
                        task.update_status(TaskStatus.RETRYING)
                
                # Execute the resolver function
                return await resolver_func(task)
                
            except Exception as e:
                last_exception = e
                
                # Call error handler if provided
                if error_handler:
                    error_handler(task, e, attempt)
                
                # If we've reached max retries, break
                if attempt >= self.max_retries:
                    break
                
                # Calculate delay for next retry
                delay = self._calculate_delay(attempt + 1)
                
                # Wait before retrying
                await asyncio.sleep(delay)
                
                attempt += 1
        
        # If we get here, all retries failed
        # Add the error to the task
        error_message = f"Failed after {attempt} attempts: {str(last_exception)}"
        task.add_error("max_retries_exceeded", error_message)
        task.update_status(TaskStatus.FAILED)
        
        # Return a failure TaskResult
        return TaskResult.failure(
            task=task,
            error_message=error_message,
            error_details={"max_retries": self.max_retries, "attempts": attempt}
        ) 