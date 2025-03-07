"""Tests for the RetryResolver."""

import asyncio
import time
import unittest
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from boss.core.task_models import Task, TaskMetadata, TaskResult
from boss.core.task_resolver import TaskResolverMetadata
from boss.core.task_status import TaskStatus
from boss.utility.retry_resolver import RetryResolver, BackoffStrategy, RetryCondition


class TestRetryResolver(unittest.IsolatedAsyncioTestCase):
    """Test suite for the RetryResolver."""

    def setUp(self) -> None:
        """Set up the test environment."""
        # Create metadata with required parameters
        self.metadata = TaskResolverMetadata(
            name="RetryResolver",
            description="Test Resolver",
            version="1.0.0"
        )
        
        # Initialize the resolver
        self.resolver = RetryResolver(
            metadata=self.metadata,
            default_max_retries=3,
            default_backoff_strategy=BackoffStrategy.CONSTANT.value,
            default_base_delay=0.01,  # Very short for tests
            default_max_delay=0.1,
            default_retry_condition=RetryCondition.ALWAYS.value
        )
    
    def _create_task(self, input_data: Dict[str, Any]) -> Task:
        """Create a task with the given input data.
        
        Args:
            input_data: The input data for the task
            
        Returns:
            A task for testing
        """
        return Task(
            id="test_task",
            name="Test Retry Task",
            description="A test task for retry operations",
            input_data=input_data,
            metadata=TaskMetadata(
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        )
    
    async def test_invalid_input(self) -> None:
        """Test handling of invalid input data."""
        # Create task with valid input first
        task = self._create_task({})
        
        # Manually modify input_data to a string after creation to bypass validation
        task.input_data = "not a dictionary"  # type: ignore
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("must be a dictionary", result.message or "")
    
    async def test_missing_operation(self) -> None:
        """Test handling of missing operation."""
        task = self._create_task({})
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Unknown operation", result.message or "")
    
    async def test_invalid_operation(self) -> None:
        """Test handling of invalid operation."""
        task = self._create_task({"operation": "invalid_operation"})
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Unknown operation", result.message or "")
    
    async def test_retry_success_after_failure(self) -> None:
        """Test successful retry after initial failures."""
        # Create a function that fails twice then succeeds
        counter = [0]
        
        def test_func():
            counter[0] += 1
            if counter[0] < 3:
                raise ValueError(f"Test error {counter[0]}")
            return f"Success on attempt {counter[0]}"
        
        task = self._create_task({
            "operation": "retry",
            "target_operation": "test_func",
            "func": test_func,
            "max_retries": 3
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertTrue(result.output_data.get("success", False))
        self.assertEqual(result.output_data.get("attempts"), 3)
        self.assertEqual(result.output_data.get("result"), "Success on attempt 3")
    
    async def test_retry_all_failure(self) -> None:
        """Test when all retry attempts fail."""
        # Create a function that always fails
        def test_func():
            raise ValueError("Test error - always fails")
        
        task = self._create_task({
            "operation": "retry",
            "target_operation": "test_func",
            "func": test_func,
            "max_retries": 2
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertFalse(result.output_data.get("success", True))
        self.assertEqual(result.output_data.get("attempts"), 3)  # Initial + 2 retries
        self.assertIn("Test error - always fails", result.output_data.get("error", ""))
    
    async def test_retry_async_function(self) -> None:
        """Test retrying an async function."""
        # Create an async function that fails twice then succeeds
        counter = [0]
        
        async def test_async_func():
            counter[0] += 1
            if counter[0] < 3:
                raise ValueError(f"Test async error {counter[0]}")
            return f"Async success on attempt {counter[0]}"
        
        task = self._create_task({
            "operation": "retry",
            "target_operation": "test_async_func",
            "func": test_async_func,
            "max_retries": 3
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertTrue(result.output_data.get("success", False))
        self.assertEqual(result.output_data.get("attempts"), 3)
        self.assertEqual(result.output_data.get("result"), "Async success on attempt 3")
    
    async def test_retry_with_args_kwargs(self) -> None:
        """Test retry with args and kwargs."""
        # Create a function that returns args and kwargs after a few failures
        counter = [0]
        
        def test_func_with_args(arg1, arg2, kwarg1=None, kwarg2=None):
            counter[0] += 1
            if counter[0] < 2:
                raise ValueError(f"Test error {counter[0]}")
            return {
                "args": [arg1, arg2],
                "kwargs": {"kwarg1": kwarg1, "kwarg2": kwarg2},
                "attempt": counter[0]
            }
        
        task = self._create_task({
            "operation": "retry",
            "target_operation": "test_func_with_args",
            "func": test_func_with_args,
            "args": ["value1", "value2"],
            "kwargs": {"kwarg1": "kwvalue1", "kwarg2": "kwvalue2"},
            "max_retries": 3
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertTrue(result.output_data.get("success", False))
        self.assertEqual(result.output_data.get("attempts"), 2)
        
        # Check that args and kwargs were passed correctly
        result_data = result.output_data.get("result", {})
        self.assertEqual(result_data.get("args"), ["value1", "value2"])
        self.assertEqual(result_data.get("kwargs"), {"kwarg1": "kwvalue1", "kwarg2": "kwvalue2"})
    
    async def test_calculate_delay(self) -> None:
        """Test delay calculation for different strategies."""
        # Test constant strategy
        task = self._create_task({
            "operation": "calculate_delay",
            "attempt": 3,
            "strategy": BackoffStrategy.CONSTANT.value,
            "base_delay": 2.0,
            "max_delay": 10.0
        })
        
        result = await self.resolver.resolve(task)
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data.get("delay"), 2.0)  # Should always be base_delay
        
        # Test linear strategy
        task = self._create_task({
            "operation": "calculate_delay",
            "attempt": 3,
            "strategy": BackoffStrategy.LINEAR.value,
            "base_delay": 2.0,
            "max_delay": 10.0
        })
        
        result = await self.resolver.resolve(task)
        self.assertEqual(result.output_data.get("delay"), 6.0)  # 2.0 * 3
        
        # Test exponential strategy
        task = self._create_task({
            "operation": "calculate_delay",
            "attempt": 3,
            "strategy": BackoffStrategy.EXPONENTIAL.value,
            "base_delay": 1.0,
            "max_delay": 10.0
        })
        
        result = await self.resolver.resolve(task)
        self.assertEqual(result.output_data.get("delay"), 4.0)  # 1.0 * 2^(3-1) = 4.0
        
        # Test max delay cap
        task = self._create_task({
            "operation": "calculate_delay",
            "attempt": 10,
            "strategy": BackoffStrategy.EXPONENTIAL.value,
            "base_delay": 1.0,
            "max_delay": 10.0
        })
        
        result = await self.resolver.resolve(task)
        self.assertEqual(result.output_data.get("delay"), 10.0)  # Capped at max_delay
    
    async def test_is_retriable(self) -> None:
        """Test error retriability check."""
        # Test always condition
        task = self._create_task({
            "operation": "is_retriable",
            "error": "Any error message",
            "condition": RetryCondition.ALWAYS.value
        })
        
        result = await self.resolver.resolve(task)
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertTrue(result.output_data.get("retriable"))
        
        # Test timeout condition - match
        task = self._create_task({
            "operation": "is_retriable",
            "error": "Operation timed out after 30 seconds",
            "condition": RetryCondition.TIMEOUT.value
        })
        
        result = await self.resolver.resolve(task)
        self.assertTrue(result.output_data.get("retriable"))
        
        # Test timeout condition - no match
        task = self._create_task({
            "operation": "is_retriable",
            "error": "Invalid input parameter",
            "condition": RetryCondition.TIMEOUT.value
        })
        
        result = await self.resolver.resolve(task)
        self.assertFalse(result.output_data.get("retriable"))
        
        # Test server condition - match
        task = self._create_task({
            "operation": "is_retriable",
            "error": "Server returned 503 Service Unavailable",
            "condition": RetryCondition.SERVER.value
        })
        
        result = await self.resolver.resolve(task)
        self.assertTrue(result.output_data.get("retriable"))
    
    async def test_get_stats(self) -> None:
        """Test retrieving retry statistics."""
        # First generate some stats by running some retries
        counter = [0]
        
        def test_func():
            counter[0] += 1
            if counter[0] < 3:
                raise ValueError(f"Test error {counter[0]}")
            return "Success"
        
        # Run a successful retry
        task = self._create_task({
            "operation": "retry",
            "target_operation": "test_func",
            "func": test_func,
            "max_retries": 3
        })
        
        await self.resolver.resolve(task)
        
        # Now create a function that always fails
        def failing_func():
            raise ValueError("Always fails")
        
        # Run a failed retry
        task = self._create_task({
            "operation": "retry",
            "target_operation": "failing_func",
            "func": failing_func,
            "max_retries": 2
        })
        
        await self.resolver.resolve(task)
        
        # Now get stats
        task = self._create_task({
            "operation": "get_stats"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        stats = result.output_data.get("stats", {})
        
        # Verify stats were recorded
        self.assertEqual(stats.get("successful_retries"), 1)  # One successful retry
        self.assertEqual(stats.get("failed_retries"), 1)  # One failed retry
        self.assertGreaterEqual(stats.get("total_attempts", 0), 5)  # 2 + 3 = 5 attempts
    
    async def test_clear_stats(self) -> None:
        """Test clearing retry statistics."""
        # First generate some stats
        def test_func():
            raise ValueError("Test error")
        
        # Run a retry that will fail
        task = self._create_task({
            "operation": "retry",
            "target_operation": "test_func",
            "func": test_func,
            "max_retries": 1
        })
        
        await self.resolver.resolve(task)
        
        # Clear stats
        task = self._create_task({
            "operation": "clear_stats"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertTrue(result.output_data.get("success", False))
        
        # Verify stats were cleared
        task = self._create_task({
            "operation": "get_stats"
        })
        
        result = await self.resolver.resolve(task)
        stats = result.output_data.get("stats", {})
        
        self.assertEqual(stats.get("total_attempts"), 0)
        self.assertEqual(stats.get("successful_retries"), 0)
        self.assertEqual(stats.get("failed_retries"), 0)
    
    async def test_configure(self) -> None:
        """Test configuring the retry resolver."""
        # Configure new settings
        task = self._create_task({
            "operation": "configure",
            "config": {
                "max_retries": 5,
                "backoff_strategy": BackoffStrategy.EXPONENTIAL.value,
                "base_delay": 2.0,
                "max_delay": 30.0,
                "retry_condition": RetryCondition.NETWORK.value
            }
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertTrue(result.output_data.get("success", False))
        
        # Verify settings were updated
        self.assertEqual(self.resolver.default_max_retries, 5)
        self.assertEqual(self.resolver.default_backoff_strategy, BackoffStrategy.EXPONENTIAL.value)
        self.assertEqual(self.resolver.default_base_delay, 2.0)
        self.assertEqual(self.resolver.default_max_delay, 30.0)
        self.assertEqual(self.resolver.default_retry_condition, RetryCondition.NETWORK.value)
    
    async def test_health_check(self) -> None:
        """Test health check functionality."""
        # Health check should pass
        is_healthy = await self.resolver.health_check()
        self.assertTrue(is_healthy)


if __name__ == "__main__":
    unittest.main() 