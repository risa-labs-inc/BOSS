"""Tests for the CacheResolver."""

import os
import shutil
import tempfile
import time
import unittest
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from boss.core.task_models import Task, TaskMetadata, TaskResult
from boss.core.task_resolver import TaskResolverMetadata
from boss.core.task_status import TaskStatus
from boss.utility.cache_resolver import CacheResolver, CacheBackend, CacheInvalidationStrategy


class TestCacheResolver(unittest.IsolatedAsyncioTestCase):
    """Test suite for the CacheResolver."""

    def setUp(self) -> None:
        """Set up the test environment."""
        # Create a temporary directory for file cache
        self.temp_dir = tempfile.mkdtemp()
        
        # Create metadata with required parameters
        self.metadata = TaskResolverMetadata(
            name="CacheResolver",
            description="Test Resolver",
            version="1.0.0"
        )
        
        # Initialize resolvers for different backends
        self.memory_resolver = CacheResolver(
            metadata=self.metadata,
            cache_backend=CacheBackend.MEMORY,
            default_ttl_seconds=10,
            max_cache_size=10
        )
        
        self.file_resolver = CacheResolver(
            metadata=self.metadata,
            cache_backend=CacheBackend.FILE,
            base_cache_dir=self.temp_dir,
            default_ttl_seconds=10
        )
    
    def tearDown(self) -> None:
        """Clean up after tests."""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)
    
    def _create_task(self, input_data: Dict[str, Any]) -> Task:
        """Create a task with the given input data.
        
        Args:
            input_data: The input data for the task
            
        Returns:
            A task for testing
        """
        return Task(
            id="test_task",
            name="Test Cache Task",
            description="A test task for cache operations",
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
        
        result = await self.memory_resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("must be a dictionary", result.message or "")
    
    async def test_missing_operation(self) -> None:
        """Test handling of missing operation."""
        task = self._create_task({})
        
        result = await self.memory_resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Unknown operation", result.message or "")
    
    async def test_invalid_operation(self) -> None:
        """Test handling of invalid operation."""
        task = self._create_task({"operation": "invalid_operation"})
        
        result = await self.memory_resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Unknown operation", result.message or "")
    
    async def test_set_get_memory(self) -> None:
        """Test setting and getting a value in memory cache."""
        # Set a value
        set_task = self._create_task({
            "operation": "set",
            "key": "test_key",
            "value": {"name": "test", "value": 123}
        })
        
        set_result = await self.memory_resolver.resolve(set_task)
        self.assertEqual(set_result.status, TaskStatus.COMPLETED)
        self.assertTrue(set_result.output_data.get("success", False))
        
        # Get the value back
        get_task = self._create_task({
            "operation": "get",
            "key": "test_key"
        })
        
        get_result = await self.memory_resolver.resolve(get_task)
        self.assertEqual(get_result.status, TaskStatus.COMPLETED)
        self.assertTrue(get_result.output_data.get("found", False))
        self.assertEqual(get_result.output_data.get("value"), {"name": "test", "value": 123})
    
    async def test_set_get_file(self) -> None:
        """Test setting and getting a value in file cache."""
        # Set a value
        set_task = self._create_task({
            "operation": "set",
            "key": "test_key",
            "value": {"name": "test", "value": 123}
        })
        
        set_result = await self.file_resolver.resolve(set_task)
        self.assertEqual(set_result.status, TaskStatus.COMPLETED)
        self.assertTrue(set_result.output_data.get("success", False))
        
        # Get the value back
        get_task = self._create_task({
            "operation": "get",
            "key": "test_key"
        })
        
        get_result = await self.file_resolver.resolve(get_task)
        self.assertEqual(get_result.status, TaskStatus.COMPLETED)
        self.assertTrue(get_result.output_data.get("found", False))
        self.assertEqual(get_result.output_data.get("value"), {"name": "test", "value": 123})
    
    async def test_ttl_expiration(self) -> None:
        """Test cache TTL expiration."""
        # Set a value with 1 second TTL
        set_task = self._create_task({
            "operation": "set",
            "key": "test_key",
            "value": {"name": "test", "value": 123},
            "ttl": 1  # 1 second TTL
        })
        
        set_result = await self.memory_resolver.resolve(set_task)
        self.assertEqual(set_result.status, TaskStatus.COMPLETED)
        
        # Get the value immediately (should succeed)
        get_task = self._create_task({
            "operation": "get",
            "key": "test_key"
        })
        
        get_result = await self.memory_resolver.resolve(get_task)
        self.assertEqual(get_result.status, TaskStatus.COMPLETED)
        self.assertTrue(get_result.output_data.get("found", False))
        
        # Wait for TTL to expire
        time.sleep(2)
        
        # Try to get the value again (should fail)
        get_result_expired = await self.memory_resolver.resolve(get_task)
        self.assertEqual(get_result_expired.status, TaskStatus.COMPLETED)
        self.assertFalse(get_result_expired.output_data.get("found", True))
    
    async def test_invalidate(self) -> None:
        """Test invalidating a cache entry."""
        # Set a value
        set_task = self._create_task({
            "operation": "set",
            "key": "test_key",
            "value": {"name": "test", "value": 123}
        })
        
        await self.memory_resolver.resolve(set_task)
        
        # Invalidate the value
        invalidate_task = self._create_task({
            "operation": "invalidate",
            "key": "test_key"
        })
        
        invalidate_result = await self.memory_resolver.resolve(invalidate_task)
        self.assertEqual(invalidate_result.status, TaskStatus.COMPLETED)
        self.assertTrue(invalidate_result.output_data.get("success", False))
        
        # Try to get the value (should fail)
        get_task = self._create_task({
            "operation": "get",
            "key": "test_key"
        })
        
        get_result = await self.memory_resolver.resolve(get_task)
        self.assertEqual(get_result.status, TaskStatus.COMPLETED)
        self.assertFalse(get_result.output_data.get("found", True))
    
    async def test_clear(self) -> None:
        """Test clearing the cache."""
        # Set multiple values
        for i in range(3):
            set_task = self._create_task({
                "operation": "set",
                "key": f"test_key_{i}",
                "value": {"index": i}
            })
            
            await self.memory_resolver.resolve(set_task)
        
        # Clear the cache
        clear_task = self._create_task({
            "operation": "clear"
        })
        
        clear_result = await self.memory_resolver.resolve(clear_task)
        self.assertEqual(clear_result.status, TaskStatus.COMPLETED)
        self.assertTrue(clear_result.output_data.get("success", False))
        
        # Try to get a value (should fail)
        get_task = self._create_task({
            "operation": "get",
            "key": "test_key_0"
        })
        
        get_result = await self.memory_resolver.resolve(get_task)
        self.assertEqual(get_result.status, TaskStatus.COMPLETED)
        self.assertFalse(get_result.output_data.get("found", True))
    
    async def test_get_stats(self) -> None:
        """Test getting cache statistics."""
        # Set a value and get it to generate some stats
        set_task = self._create_task({
            "operation": "set",
            "key": "test_key",
            "value": {"name": "test"}
        })
        
        await self.memory_resolver.resolve(set_task)
        
        get_task = self._create_task({
            "operation": "get",
            "key": "test_key"
        })
        
        await self.memory_resolver.resolve(get_task)
        
        # Get non-existent key to generate miss
        miss_task = self._create_task({
            "operation": "get",
            "key": "nonexistent_key"
        })
        
        await self.memory_resolver.resolve(miss_task)
        
        # Get stats
        stats_task = self._create_task({
            "operation": "get_stats"
        })
        
        stats_result = await self.memory_resolver.resolve(stats_task)
        self.assertEqual(stats_result.status, TaskStatus.COMPLETED)
        
        stats = stats_result.output_data
        self.assertEqual(stats.get("backend"), CacheBackend.MEMORY)
        self.assertEqual(stats.get("stats", {}).get("hits"), 1)
        self.assertEqual(stats.get("stats", {}).get("misses"), 1)
        self.assertEqual(stats.get("stats", {}).get("sets"), 1)
    
    async def test_clear_stats(self) -> None:
        """Test clearing cache statistics."""
        # Generate some stats
        set_task = self._create_task({
            "operation": "set",
            "key": "test_key",
            "value": {"name": "test"}
        })
        
        await self.memory_resolver.resolve(set_task)
        
        # Clear stats
        clear_stats_task = self._create_task({
            "operation": "clear_stats"
        })
        
        clear_result = await self.memory_resolver.resolve(clear_stats_task)
        self.assertEqual(clear_result.status, TaskStatus.COMPLETED)
        self.assertTrue(clear_result.output_data.get("success", False))
        
        # Get stats and confirm they're reset
        stats_task = self._create_task({
            "operation": "get_stats"
        })
        
        stats_result = await self.memory_resolver.resolve(stats_task)
        stats = stats_result.output_data
        
        self.assertEqual(stats.get("stats", {}).get("hits"), 0)
        self.assertEqual(stats.get("stats", {}).get("misses"), 0)
        self.assertEqual(stats.get("stats", {}).get("sets"), 0)
    
    async def test_configure(self) -> None:
        """Test configuring the cache resolver."""
        # Configure new settings
        configure_task = self._create_task({
            "operation": "configure",
            "config": {
                "ttl": 3600,
                "max_size": 500,
                "invalidation_strategy": CacheInvalidationStrategy.LRU.value
            }
        })
        
        configure_result = await self.memory_resolver.resolve(configure_task)
        self.assertEqual(configure_result.status, TaskStatus.COMPLETED)
        self.assertTrue(configure_result.output_data.get("success", False))
        
        # Verify settings were changed
        self.assertEqual(self.memory_resolver.default_ttl_seconds, 3600)
        self.assertEqual(self.memory_resolver.max_cache_size, 500)
        self.assertEqual(self.memory_resolver.invalidation_strategy, CacheInvalidationStrategy.LRU.value)
    
    async def test_health_check(self) -> None:
        """Test health check functionality."""
        # Health check should pass
        is_healthy = await self.memory_resolver.health_check()
        self.assertTrue(is_healthy)


if __name__ == "__main__":
    unittest.main() 