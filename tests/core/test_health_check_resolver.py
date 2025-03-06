"""
Tests for the HealthCheckResolver component.

This module contains unit tests for the health check functionality,
including monitoring of other resolvers, health history tracking,
and health status reporting.
"""

import unittest
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from boss.core.task_models import Task, TaskResult, TaskStatus, TaskError
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.registry import TaskResolverRegistry
from boss.core.health_check_resolver import HealthCheckResolver, HealthCheckResult


class TestHealthCheckResult(unittest.TestCase):
    """Tests for the HealthCheckResult class."""
    
    def test_initialization(self) -> None:
        """Test initialization of HealthCheckResult."""
        # Test with minimal parameters
        result = HealthCheckResult(
            resolver_name="test_resolver",
            resolver_version="1.0.0",
            is_healthy=True,
            check_time=0.5
        )
        
        self.assertEqual(result.resolver_name, "test_resolver")
        self.assertEqual(result.resolver_version, "1.0.0")
        self.assertTrue(result.is_healthy)
        self.assertEqual(result.check_time, 0.5)
        self.assertIsNone(result.error_message)
        self.assertEqual(result.details, {})
        
        # Test with all parameters
        details = {"cpu_usage": 0.5, "memory_usage": 0.25}
        result = HealthCheckResult(
            resolver_name="test_resolver",
            resolver_version="1.0.0",
            is_healthy=False,
            check_time=0.5,
            error_message="Test error",
            details=details
        )
        
        self.assertEqual(result.resolver_name, "test_resolver")
        self.assertEqual(result.resolver_version, "1.0.0")
        self.assertFalse(result.is_healthy)
        self.assertEqual(result.check_time, 0.5)
        self.assertEqual(result.error_message, "Test error")
        self.assertEqual(result.details, details)
    
    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        details = {"cpu_usage": 0.5, "memory_usage": 0.25}
        result = HealthCheckResult(
            resolver_name="test_resolver",
            resolver_version="1.0.0",
            is_healthy=True,
            check_time=0.5,
            error_message="Test error",
            details=details
        )
        
        # Convert to dictionary
        result_dict = result.to_dict()
        
        # Verify dictionary contents
        self.assertEqual(result_dict["resolver_name"], "test_resolver")
        self.assertEqual(result_dict["resolver_version"], "1.0.0")
        self.assertTrue(result_dict["is_healthy"])
        self.assertEqual(result_dict["check_time"], 0.5)
        self.assertEqual(result_dict["error_message"], "Test error")
        self.assertEqual(result_dict["details"], details)
        self.assertIn("timestamp", result_dict)


class MockResolver(TaskResolver):
    """Mock TaskResolver for testing."""
    
    def __init__(
        self,
        metadata: TaskResolverMetadata,
        health_status: bool = True,
        health_exception: bool = False
    ) -> None:
        """
        Initialize the MockResolver.
        
        Args:
            metadata: Metadata for this resolver
            health_status: Health status to return from health_check
            health_exception: Whether to raise an exception in health_check
        """
        super().__init__(metadata)
        self.health_status = health_status
        self.health_exception = health_exception
    
    async def health_check(self) -> bool:
        """
        Perform a health check on this resolver.
        
        Returns:
            Health status
            
        Raises:
            Exception: If health_exception is True
        """
        if self.health_exception:
            raise Exception("Mock health check exception")
        return self.health_status
    
    def can_handle(self, task: Task) -> bool:
        """
        Determine if this resolver can handle the given task.
        
        Args:
            task: The task to check
            
        Returns:
            Always returns False for the mock resolver
        """
        return False


class TestHealthCheckResolver(unittest.TestCase):
    """Tests for the HealthCheckResolver class."""
    
    def setUp(self) -> None:
        """Set up test environment before each test."""
        # Create mock registry
        self.registry = MagicMock(spec=TaskResolverRegistry)
        
        # Create health check resolver
        self.metadata = TaskResolverMetadata(
            name="health_check",
            version="1.0.0",
            description="Health check resolver for testing"
        )
        
        self.resolver = HealthCheckResolver(
            metadata=self.metadata,
            registry=self.registry,
            timeout=1.0,
            max_workers=2
        )
        
        # Create mock resolvers
        self.healthy_resolver_metadata = TaskResolverMetadata(
            name="healthy_resolver",
            version="1.0.0",
            description="Healthy resolver for testing"
        )
        
        self.unhealthy_resolver_metadata = TaskResolverMetadata(
            name="unhealthy_resolver",
            version="1.0.0",
            description="Unhealthy resolver for testing"
        )
        
        self.error_resolver_metadata = TaskResolverMetadata(
            name="error_resolver",
            version="1.0.0",
            description="Error resolver for testing"
        )
        
        self.healthy_resolver = MockResolver(
            metadata=self.healthy_resolver_metadata,
            health_status=True
        )
        
        self.unhealthy_resolver = MockResolver(
            metadata=self.unhealthy_resolver_metadata,
            health_status=False
        )
        
        self.error_resolver = MockResolver(
            metadata=self.error_resolver_metadata,
            health_exception=True
        )
    
    def asyncSetUp(self) -> None:
        """Set up async test environment."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
    
    def asyncTearDown(self) -> None:
        """Tear down async test environment."""
        self.loop.close()
    
    async def test_health_check(self) -> None:
        """Test the health check method."""
        # Health check should return True if registry is available
        result = await self.resolver.health_check()
        self.assertTrue(result)
        
        # Set registry to None to simulate unavailable registry
        self.resolver.registry = None
        result = await self.resolver.health_check()
        self.assertFalse(result)
    
    def test_can_handle(self) -> None:
        """Test can_handle method."""
        # Valid task with resolver specified
        task1 = Task(
            input_data={"operation": "check_resolver", "resolver_name": "test_resolver"},
            metadata={"resolver": "health_check"}
        )
        self.assertTrue(self.resolver.can_handle(task1))
        
        # Valid task without resolver specified
        task2 = Task(
            input_data={"operation": "check_all"},
            metadata={}
        )
        self.assertTrue(self.resolver.can_handle(task2))
        
        # Invalid task with different resolver
        task3 = Task(
            input_data={"operation": "check_resolver", "resolver_name": "test_resolver"},
            metadata={"resolver": "other_resolver"}
        )
        self.assertFalse(self.resolver.can_handle(task3))
        
        # Invalid task with unsupported operation
        task4 = Task(
            input_data={"operation": "unsupported"},
            metadata={}
        )
        self.assertFalse(self.resolver.can_handle(task4))
        
        # Invalid task with non-dict input
        task5 = Task(
            input_data="not a dict",
            metadata={}
        )
        self.assertFalse(self.resolver.can_handle(task5))
    
    async def test_check_resolver_health(self) -> None:
        """Test checking a single resolver's health."""
        # Set up registry to return healthy resolver
        self.registry.get_resolver.return_value = self.healthy_resolver
        
        # Check health of healthy resolver
        result = await self.resolver._check_resolver_health("healthy_resolver")
        
        # Verify result
        self.assertEqual(result.resolver_name, "healthy_resolver")
        self.assertEqual(result.resolver_version, "1.0.0")
        self.assertTrue(result.is_healthy)
        self.assertIsNone(result.error_message)
        
        # Set up registry to return unhealthy resolver
        self.registry.get_resolver.return_value = self.unhealthy_resolver
        
        # Check health of unhealthy resolver
        result = await self.resolver._check_resolver_health("unhealthy_resolver")
        
        # Verify result
        self.assertEqual(result.resolver_name, "unhealthy_resolver")
        self.assertEqual(result.resolver_version, "1.0.0")
        self.assertFalse(result.is_healthy)
        self.assertIsNone(result.error_message)
        
        # Set up registry to return error resolver
        self.registry.get_resolver.return_value = self.error_resolver
        
        # Check health of error resolver
        result = await self.resolver._check_resolver_health("error_resolver")
        
        # Verify result
        self.assertEqual(result.resolver_name, "error_resolver")
        self.assertEqual(result.resolver_version, "1.0.0")
        self.assertFalse(result.is_healthy)
        self.assertEqual(result.error_message, "Mock health check exception")
        
        # Set up registry to return None (resolver not found)
        self.registry.get_resolver.return_value = None
        
        # Check health of non-existent resolver
        result = await self.resolver._check_resolver_health("non_existent_resolver", "1.0.0")
        
        # Verify result
        self.assertEqual(result.resolver_name, "non_existent_resolver")
        self.assertEqual(result.resolver_version, "1.0.0")
        self.assertFalse(result.is_healthy)
        self.assertEqual(result.error_message, "Resolver not found: non_existent_resolver v1.0.0")
    
    async def test_check_all_resolvers_health(self) -> None:
        """Test checking all resolvers' health."""
        # Set up registry to return all resolvers
        all_resolvers = [self.healthy_resolver, self.unhealthy_resolver, self.error_resolver]
        self.registry.get_all_resolvers.return_value = all_resolvers
        
        # Check health of all resolvers
        results = await self.resolver._check_all_resolvers_health()
        
        # Verify results
        self.assertEqual(len(results), 3)
        
        # Count healthy and unhealthy resolvers
        healthy_count = sum(1 for r in results if r.is_healthy)
        unhealthy_count = sum(1 for r in results if not r.is_healthy)
        
        self.assertEqual(healthy_count, 1)
        self.assertEqual(unhealthy_count, 2)
        
        # Verify results contain all resolver names
        resolver_names = [r.resolver_name for r in results]
        self.assertIn("healthy_resolver", resolver_names)
        self.assertIn("unhealthy_resolver", resolver_names)
        self.assertIn("error_resolver", resolver_names)
    
    async def test_check_all_resolvers_with_filter(self) -> None:
        """Test checking all resolvers with include/exclude patterns."""
        # Set up registry to return all resolvers
        all_resolvers = [self.healthy_resolver, self.unhealthy_resolver, self.error_resolver]
        self.registry.get_all_resolvers.return_value = all_resolvers
        
        # Check health with include pattern
        results = await self.resolver._check_all_resolvers_health(include_pattern="healthy.*")
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].resolver_name, "healthy_resolver")
        
        # Check health with exclude pattern
        results = await self.resolver._check_all_resolvers_health(exclude_pattern=".*error.*")
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].resolver_name, "healthy_resolver")
        
        # Check health with both include and exclude patterns
        results = await self.resolver._check_all_resolvers_health(
            include_pattern=".*resolver",
            exclude_pattern="healthy.*"
        )
        
        # Verify results
        self.assertEqual(len(results), 2)
        resolver_names = [r.resolver_name for r in results]
        self.assertIn("unhealthy_resolver", resolver_names)
        self.assertIn("error_resolver", resolver_names)
        self.assertNotIn("healthy_resolver", resolver_names)
    
    async def test_handle_check_resolver(self) -> None:
        """Test handling check_resolver task."""
        # Set up registry to return healthy resolver
        self.registry.get_resolver.return_value = self.healthy_resolver
        
        # Create check_resolver task
        task = Task(
            input_data={
                "operation": "check_resolver",
                "resolver_name": "healthy_resolver"
            }
        )
        
        # Resolve task
        result = await self.resolver._resolve_task(task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["resolver_name"], "healthy_resolver")
        self.assertEqual(result.output_data["resolver_version"], "1.0.0")
        self.assertTrue(result.output_data["is_healthy"])
        
        # Test with missing resolver_name
        task = Task(
            input_data={
                "operation": "check_resolver"
            }
        )
        
        # Resolve task
        result = await self.resolver._resolve_task(task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertEqual(result.error.error_type, "missing_parameter")
        self.assertEqual(result.error.message, "resolver_name is required")
    
    async def test_handle_check_all(self) -> None:
        """Test handling check_all task."""
        # Set up registry to return all resolvers
        all_resolvers = [self.healthy_resolver, self.unhealthy_resolver, self.error_resolver]
        self.registry.get_all_resolvers.return_value = all_resolvers
        
        # Create check_all task
        task = Task(
            input_data={
                "operation": "check_all"
            }
        )
        
        # Resolve task
        result = await self.resolver._resolve_task(task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(len(result.output_data["results"]), 3)
        self.assertEqual(result.output_data["total"], 3)
        self.assertEqual(result.output_data["healthy"], 1)
        self.assertEqual(result.output_data["unhealthy"], 2)
        
        # Test with include pattern
        task = Task(
            input_data={
                "operation": "check_all",
                "include_pattern": "healthy.*"
            }
        )
        
        # Resolve task
        result = await self.resolver._resolve_task(task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(len(result.output_data["results"]), 1)
        self.assertEqual(result.output_data["total"], 1)
        self.assertEqual(result.output_data["healthy"], 1)
        self.assertEqual(result.output_data["unhealthy"], 0)
    
    async def test_handle_get_health_status(self) -> None:
        """Test handling get_health_status task."""
        # Add some health history
        healthy_result = HealthCheckResult(
            resolver_name="healthy_resolver",
            resolver_version="1.0.0",
            is_healthy=True,
            check_time=0.5
        )
        
        unhealthy_result = HealthCheckResult(
            resolver_name="unhealthy_resolver",
            resolver_version="1.0.0",
            is_healthy=False,
            check_time=0.5,
            error_message="Test error"
        )
        
        self.resolver.health_history["healthy_resolver"] = [healthy_result]
        self.resolver.health_history["unhealthy_resolver"] = [unhealthy_result]
        
        # Create get_health_status task for all resolvers
        task = Task(
            input_data={
                "operation": "get_health_status"
            }
        )
        
        # Resolve task
        result = await self.resolver._resolve_task(task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(len(result.output_data), 2)
        self.assertTrue(result.output_data["healthy_resolver"]["is_healthy"])
        self.assertFalse(result.output_data["unhealthy_resolver"]["is_healthy"])
        
        # Create get_health_status task for specific resolver
        task = Task(
            input_data={
                "operation": "get_health_status",
                "resolver_name": "healthy_resolver"
            }
        )
        
        # Resolve task
        result = await self.resolver._resolve_task(task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["resolver_name"], "healthy_resolver")
        self.assertTrue(result.output_data["is_healthy"])
        
        # Test with non-existent resolver
        task = Task(
            input_data={
                "operation": "get_health_status",
                "resolver_name": "non_existent_resolver"
            }
        )
        
        # Resolve task
        result = await self.resolver._resolve_task(task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertEqual(result.error.error_type, "not_found")
    
    async def test_handle_get_health_history(self) -> None:
        """Test handling get_health_history task."""
        # Add some health history
        now = datetime.utcnow()
        
        # Create 5 health check results with different timestamps
        history = []
        for i in range(5):
            timestamp = now - timedelta(minutes=i)
            result = HealthCheckResult(
                resolver_name="test_resolver",
                resolver_version="1.0.0",
                is_healthy=i % 2 == 0,  # Alternate between healthy and unhealthy
                check_time=0.5,
                error_message=None if i % 2 == 0 else f"Error {i}"
            )
            # Manually set timestamp for testing
            result.timestamp = timestamp.isoformat()
            history.append(result)
        
        # Add history to resolver
        self.resolver.health_history["test_resolver"] = history
        
        # Create get_health_history task
        task = Task(
            input_data={
                "operation": "get_health_history",
                "resolver_name": "test_resolver",
                "limit": 3
            }
        )
        
        # Resolve task
        result = await self.resolver._resolve_task(task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(len(result.output_data), 3)  # Limit to 3 results
        
        # Test with missing resolver_name
        task = Task(
            input_data={
                "operation": "get_health_history"
            }
        )
        
        # Resolve task
        result = await self.resolver._resolve_task(task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertEqual(result.error.error_type, "missing_parameter")
        
        # Test with non-existent resolver
        task = Task(
            input_data={
                "operation": "get_health_history",
                "resolver_name": "non_existent_resolver"
            }
        )
        
        # Resolve task
        result = await self.resolver._resolve_task(task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertEqual(result.error.error_type, "not_found")
    
    async def test_handle_invalid_operation(self) -> None:
        """Test handling invalid operation."""
        # Create task with invalid operation
        task = Task(
            input_data={
                "operation": "invalid_operation"
            }
        )
        
        # Resolve task
        result = await self.resolver._resolve_task(task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertEqual(result.error.error_type, "invalid_operation")
    
    async def test_handle_non_dict_input(self) -> None:
        """Test handling non-dict input."""
        # Create task with non-dict input
        task = Task(
            input_data="not a dict"
        )
        
        # Resolve task
        result = await self.resolver._resolve_task(task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertEqual(result.error.error_type, "invalid_input")
    
    def test_get_resolver_key(self) -> None:
        """Test _get_resolver_key method."""
        # Test with resolver_name only
        key = self.resolver._get_resolver_key("test_resolver")
        self.assertEqual(key, "test_resolver")
        
        # Test with resolver_name and resolver_version
        key = self.resolver._get_resolver_key("test_resolver", "1.0.0")
        self.assertEqual(key, "test_resolver@1.0.0")


if __name__ == "__main__":
    unittest.main() 