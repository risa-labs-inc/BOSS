"""Tests for the PerformanceAnalyzerResolver."""

import json
import os
import shutil
import tempfile
from datetime import datetime
from typing import Any, Dict, Optional
import unittest
from unittest.mock import MagicMock, patch

from boss.core.task_models import Task, TaskMetadata, TaskResult
from boss.core.task_resolver import TaskResolverMetadata
from boss.core.task_status import TaskStatus
from boss.lighthouse.performance_analyzer_resolver import PerformanceAnalyzerResolver


class TestPerformanceAnalyzerResolver(unittest.IsolatedAsyncioTestCase):
    """Test suite for the PerformanceAnalyzerResolver."""

    def setUp(self) -> None:
        """Set up the test environment."""
        # Create temp directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.boss_home_dir = os.path.join(self.temp_dir, "boss_home")
        self.performance_data_dir = os.path.join(self.boss_home_dir, "data", "performance")
        self.config_dir = os.path.join(self.boss_home_dir, "config")
        
        # Create required directories
        os.makedirs(self.boss_home_dir, exist_ok=True)
        os.makedirs(self.performance_data_dir, exist_ok=True)
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Mock environment variables
        self.env_patcher = patch.dict("os.environ", {"BOSS_HOME": self.boss_home_dir})
        self.env_patcher.start()
        
        # Create test resolver metadata
        self.metadata = TaskResolverMetadata(
            name="PerformanceAnalyzerResolver",
            description="Test Resolver",
            version="1.0.0"
        )
        
        # Initialize the resolver
        self.resolver = PerformanceAnalyzerResolver(self.metadata)
    
    def tearDown(self) -> None:
        """Clean up the test environment."""
        self.env_patcher.stop()
        shutil.rmtree(self.temp_dir)
    
    def _create_task(self, input_data: Dict[str, Any]) -> Task:
        """Helper method to create a task with standard metadata."""
        return Task(
            id="test_task_id",
            name="Test Task",
            description="A test task",
            status=TaskStatus.PENDING,
            input_data=input_data,
            metadata=TaskMetadata(
                created_at=datetime.now(),
                updated_at=datetime.now(),
                owner="test_user"
            )
        )
    
    async def test_invalid_input(self) -> None:
        """Test with invalid input data (not a dict)."""
        task = self._create_task({})
        task.input_data = None  # type: ignore
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("must be a dictionary", result.output_data.get("error", ""))
    
    async def test_missing_operation(self) -> None:
        """Test with missing operation field."""
        task = self._create_task({})
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Missing 'operation' field", result.output_data.get("error", ""))
    
    async def test_invalid_operation(self) -> None:
        """Test with invalid operation."""
        task = self._create_task({"operation": "unknown_operation"})
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Unsupported operation", result.output_data.get("error", ""))
    
    async def test_collect_performance_metrics(self) -> None:
        """Test collecting performance metrics."""
        task = self._create_task({
            "operation": "collect_performance_metrics",
            "target_components": ["filesystem", "network", "memory"],
            "collection_period": 60  # seconds
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("message", result.output_data)
        self.assertIn("Performance metrics collected", result.output_data.get("message", ""))
    
    async def test_analyze_performance_data(self) -> None:
        """Test analyzing performance data."""
        task = self._create_task({
            "operation": "analyze_performance_data",
            "time_range": {
                "start": (datetime.now().timestamp() - 3600),  # 1 hour ago
                "end": datetime.now().timestamp()
            },
            "metrics": ["disk_io", "memory_usage", "cpu_utilization"],
            "analysis_type": "trend"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("message", result.output_data)
        self.assertIn("Performance data analyzed", result.output_data.get("message", ""))
    
    async def test_generate_performance_report(self) -> None:
        """Test generating a performance report."""
        task = self._create_task({
            "operation": "generate_performance_report",
            "report_type": "detailed",
            "time_range": {
                "start": (datetime.now().timestamp() - 86400),  # 24 hours ago
                "end": datetime.now().timestamp()
            },
            "components": ["cpu", "memory", "disk", "network"],
            "format": "html"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("report", result.output_data)
        self.assertIn("Performance report", result.output_data.get("report", ""))
    
    async def test_health_check(self) -> None:
        """Test the health check operation."""
        task = self._create_task({
            "operation": "health_check"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("status", result.output_data)
        self.assertIn("PerformanceAnalyzerResolver is healthy", result.output_data.get("status", ""))


if __name__ == "__main__":
    unittest.main() 