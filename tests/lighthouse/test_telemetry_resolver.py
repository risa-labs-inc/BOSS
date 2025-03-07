"""Tests for the TelemetryResolver."""

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
from boss.lighthouse.telemetry_resolver import TelemetryResolver


class TestTelemetryResolver(unittest.IsolatedAsyncioTestCase):
    """Test suite for the TelemetryResolver."""

    def setUp(self) -> None:
        """Set up the test environment."""
        # Create temp directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.boss_home_dir = os.path.join(self.temp_dir, "boss_home")
        self.telemetry_dir = os.path.join(self.boss_home_dir, "data", "telemetry")
        self.config_dir = os.path.join(self.boss_home_dir, "config")
        
        # Create required directories
        os.makedirs(self.boss_home_dir, exist_ok=True)
        os.makedirs(self.telemetry_dir, exist_ok=True)
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Mock environment variables
        self.env_patcher = patch.dict("os.environ", {"BOSS_HOME": self.boss_home_dir})
        self.env_patcher.start()
        
        # Create test resolver metadata
        self.metadata = TaskResolverMetadata(
            name="TelemetryResolver",
            description="Test Resolver",
            version="1.0.0"
        )
        
        # Initialize the resolver
        self.resolver = TelemetryResolver(self.metadata)
    
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
    
    async def test_collect_telemetry_data(self) -> None:
        """Test collecting telemetry data."""
        task = self._create_task({
            "operation": "collect_telemetry_data",
            "components": ["cpu", "memory", "disk"]
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("message", result.output_data)
        self.assertIn("Telemetry data collected", result.output_data.get("message", ""))
    
    async def test_analyze_telemetry_data(self) -> None:
        """Test analyzing telemetry data."""
        task = self._create_task({
            "operation": "analyze_telemetry_data",
            "time_range": {
                "start": (datetime.now().timestamp() - 3600),  # 1 hour ago
                "end": datetime.now().timestamp()
            },
            "components": ["cpu", "memory"]
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("message", result.output_data)
        self.assertIn("Telemetry data analyzed", result.output_data.get("message", ""))
    
    async def test_get_telemetry_report(self) -> None:
        """Test generating a telemetry report."""
        task = self._create_task({
            "operation": "get_telemetry_report",
            "report_type": "summary",
            "time_range": {
                "start": (datetime.now().timestamp() - 86400),  # 24 hours ago
                "end": datetime.now().timestamp()
            }
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("report", result.output_data)
        self.assertIn("Telemetry report", result.output_data.get("report", ""))
    
    async def test_health_check(self) -> None:
        """Test the health check operation."""
        task = self._create_task({
            "operation": "health_check"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("status", result.output_data)
        self.assertIn("healthy", result.output_data.get("status", ""))


if __name__ == "__main__":
    unittest.main() 