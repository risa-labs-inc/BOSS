"""Tests for the MonitoringResolver."""

import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, cast
import unittest
from unittest.mock import MagicMock, patch

import psutil

from boss.core.task_models import Task, TaskMetadata, TaskResult  # type: ignore[import]
from boss.core.task_resolver import TaskResolverMetadata  # type: ignore[import]
from boss.core.task_status import TaskStatus  # type: ignore[import]
from boss.lighthouse.monitoring_resolver import MonitoringResolver  # type: ignore[import]


class TestMonitoringResolver(unittest.IsolatedAsyncioTestCase):
    """Test suite for the MonitoringResolver."""

    def setUp(self) -> None:
        """Set up the test environment."""
        # Create temp directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.boss_home_dir = os.path.join(self.temp_dir, "boss_home")
        self.metrics_dir = os.path.join(self.boss_home_dir, "data", "metrics")
        self.alerts_dir = os.path.join(self.boss_home_dir, "data", "alerts")
        self.config_dir = os.path.join(self.boss_home_dir, "config")
        
        # Create required directories
        os.makedirs(self.boss_home_dir, exist_ok=True)
        os.makedirs(self.metrics_dir, exist_ok=True)
        os.makedirs(self.alerts_dir, exist_ok=True)
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Mock environment variables
        self.env_patcher = patch.dict("os.environ", {"BOSS_HOME": self.boss_home_dir})
        self.env_patcher.start()
        
        # Create test resolver metadata
        self.metadata = TaskResolverMetadata(
            name="MonitoringResolver",
            description="Test Resolver",
            version="1.0.0"
        )
        
        # Initialize the resolver
        self.resolver = MonitoringResolver(self.metadata)
        
        # Mock system metrics for testing
        self.mock_metrics = {
            "cpu_usage": 50.0,
            "cpu_count": 8,
            "memory_usage": 60.0,
            "memory_total_bytes": 16000000000,
            "memory_available_bytes": 8000000000,
            "disk_usage": 70.0,
            "disk_total_bytes": 500000000000,
            "disk_free_bytes": 200000000000,
            "network_bytes_sent": 1000000,
            "network_bytes_recv": 2000000,
            "boot_time": datetime.now().isoformat(),
            "uptime_seconds": 3600,
            "process_count": 100,
            "platform": "Test Platform",
            "python_version": "3.9.0",
            "hostname": "test-host"
        }
        
        # Set up mock for _get_system_metrics
        self.metrics_patcher = patch.object(
            MonitoringResolver, 
            '_get_system_metrics',
            return_value=self.mock_metrics
        )
        self.mock_get_metrics = self.metrics_patcher.start()
    
    def tearDown(self) -> None:
        """Clean up after tests."""
        # Stop patches
        self.env_patcher.stop()
        self.metrics_patcher.stop()
        
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
            name="Test Monitoring Task",
            description="A test task for monitoring operations",
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
        self.assertIn("must be a dictionary", result.output_data.get("error", ""))
    
    async def test_missing_operation(self) -> None:
        """Test handling of missing operation."""
        task = self._create_task({})
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Missing 'operation'", result.output_data.get("error", ""))
    
    async def test_invalid_operation(self) -> None:
        """Test handling of invalid operation."""
        task = self._create_task({"operation": "invalid_operation"})
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Unsupported operation", result.output_data.get("error", ""))
    
    async def test_collect_system_metrics(self) -> None:
        """Test collection of system metrics."""
        task = self._create_task({
            "operation": "collect_system_metrics",
            "store_metrics": True
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("metrics", result.output_data)
        self.assertIn("timestamp", result.output_data)
        
        # Verify metrics match our mock
        self.assertEqual(result.output_data["metrics"], self.mock_metrics)
        
        # Verify metrics are stored
        self.assertTrue(os.path.exists(self.metrics_dir))
        
        # Find the metrics file (should be in a date-based directory)
        now = datetime.now()
        year_dir = os.path.join(self.metrics_dir, str(now.year))
        month_dir = os.path.join(year_dir, f"{now.month:02d}")
        day_dir = os.path.join(month_dir, f"{now.day:02d}")
        
        self.assertTrue(os.path.exists(day_dir))
        
        # There should be at least one JSON file in the day directory
        files = [f for f in os.listdir(day_dir) if f.endswith(".json")]
        self.assertGreater(len(files), 0)
        
        # Verify the file contents
        with open(os.path.join(day_dir, files[0]), "r") as f:
            stored_metrics = json.load(f)
            
        self.assertEqual(stored_metrics, self.mock_metrics)
    
    async def test_collect_system_metrics_with_threshold_alerts(self) -> None:
        """Test collection of system metrics with threshold alerts."""
        # Set CPU usage above threshold
        high_cpu_metrics = self.mock_metrics.copy()
        high_cpu_metrics["cpu_usage"] = 95.0
        
        # Update mock to return high CPU usage
        self.mock_get_metrics.return_value = high_cpu_metrics
        
        task = self._create_task({
            "operation": "collect_system_metrics",
            "store_metrics": True,
            "generate_alerts": True
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("alerts", result.output_data)
        
        # Verify alerts were generated
        alerts = result.output_data.get("alerts", [])
        self.assertGreater(len(alerts), 0)
        
        # Verify alert contains CPU usage warning
        cpu_alerts = [a for a in alerts if a.get("type") == "cpu_usage"]
        self.assertGreater(len(cpu_alerts), 0)
        self.assertIn("CPU usage", cpu_alerts[0].get("message", ""))
        
        # Verify alerts are stored
        self.assertTrue(os.path.exists(self.alerts_dir))
        
        # There should be at least one JSON file in the alerts directory
        files = [f for f in os.listdir(self.alerts_dir) if f.endswith(".json")]
        self.assertGreater(len(files), 0)
    
    async def test_check_component_health(self) -> None:
        """Test checking component health."""
        task = self._create_task({
            "operation": "check_component_health",
            "component_id": "test_component",
            "store_result": True
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data.get("component_id"), "test_component")
        self.assertEqual(result.output_data.get("status"), "ok")
        
        # Verify health check is stored
        health_checks_dir = os.path.join(self.metrics_dir, "health_checks")
        self.assertTrue(os.path.exists(health_checks_dir))
        
        component_file = os.path.join(health_checks_dir, "test_component.json")
        self.assertTrue(os.path.exists(component_file))
        
        # Verify file contents
        with open(component_file, "r") as f:
            health_checks = json.load(f)
            
        self.assertIsInstance(health_checks, list)
        self.assertEqual(len(health_checks), 1)
        self.assertEqual(health_checks[0].get("component_id"), "test_component")
        self.assertEqual(health_checks[0].get("status"), "ok")
    
    async def test_check_component_health_missing_component_id(self) -> None:
        """Test checking component health with missing component ID."""
        task = self._create_task({
            "operation": "check_component_health"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Missing 'component_id'", result.output_data.get("error", ""))
    
    async def test_generate_alert(self) -> None:
        """Test generating an alert."""
        task = self._create_task({
            "operation": "generate_alert",
            "type": "test_alert",
            "message": "This is a test alert",
            "level": "warning",
            "component_id": "test_component"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data.get("alert", {}).get("type"), "test_alert")
        self.assertEqual(result.output_data.get("alert", {}).get("message"), "This is a test alert")
        self.assertEqual(result.output_data.get("alert", {}).get("level"), "warning")
        self.assertEqual(result.output_data.get("alert", {}).get("component_id"), "test_component")
        
        # Verify alert is stored
        files = [f for f in os.listdir(self.alerts_dir) if f.endswith(".json")]
        self.assertGreater(len(files), 0)
        
        # Verify file contents
        with open(os.path.join(self.alerts_dir, files[0]), "r") as f:
            alert = json.load(f)
            
        self.assertEqual(alert.get("type"), "test_alert")
        self.assertEqual(alert.get("message"), "This is a test alert")
        self.assertEqual(alert.get("level"), "warning")
        self.assertEqual(alert.get("component_id"), "test_component")
    
    async def test_generate_alert_missing_type(self) -> None:
        """Test generating an alert with missing type."""
        task = self._create_task({
            "operation": "generate_alert",
            "message": "This is a test alert"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Missing 'type'", result.output_data.get("error", ""))
    
    async def test_generate_alert_missing_message(self) -> None:
        """Test generating an alert with missing message."""
        task = self._create_task({
            "operation": "generate_alert",
            "type": "test_alert"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Missing 'message'", result.output_data.get("error", ""))
    
    async def test_list_alerts(self) -> None:
        """Test listing alerts."""
        # Create some test alerts
        for i in range(5):
            alert = {
                "type": f"test_alert_{i}",
                "message": f"Test alert {i}",
                "level": "info",
                "timestamp": datetime.now().isoformat()
            }
            alert_file = os.path.join(self.alerts_dir, f"alert_{i}.json")
            with open(alert_file, "w") as f:
                json.dump(alert, f, indent=2)
        
        task = self._create_task({
            "operation": "list_alerts",
            "limit": 10
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("alerts", result.output_data)
        self.assertEqual(result.output_data.get("count"), 5)
        
        # Verify all alerts are returned
        alerts = result.output_data.get("alerts", [])
        self.assertEqual(len(alerts), 5)
        
        # Test filtering by type
        task = self._create_task({
            "operation": "list_alerts",
            "type": "test_alert_1"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        alerts = result.output_data.get("alerts", [])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].get("type"), "test_alert_1")
    
    async def test_list_alerts_with_date_range(self) -> None:
        """Test listing alerts with date range."""
        # Create alerts with different dates
        dates = [
            datetime.now() - timedelta(days=3),
            datetime.now() - timedelta(days=2),
            datetime.now() - timedelta(days=1),
            datetime.now()
        ]
        
        for i, date in enumerate(dates):
            alert = {
                "type": f"test_alert_{i}",
                "message": f"Test alert {i}",
                "level": "info",
                "timestamp": date.isoformat()
            }
            alert_file = os.path.join(self.alerts_dir, f"alert_{i}.json")
            with open(alert_file, "w") as f:
                json.dump(alert, f, indent=2)
        
        # Test with start and end date
        start_date = (datetime.now() - timedelta(days=2)).isoformat()
        end_date = datetime.now().isoformat()
        
        task = self._create_task({
            "operation": "list_alerts",
            "start_date": start_date,
            "end_date": end_date
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        alerts = result.output_data.get("alerts", [])
        # Should include alerts from days 0-2 (today, yesterday, 2 days ago)
        self.assertGreaterEqual(len(alerts), 3)
    
    async def test_update_alert_thresholds(self) -> None:
        """Test updating alert thresholds."""
        new_thresholds = {
            "cpu_usage": 80.0,
            "memory_usage": 85.0,
            "disk_usage": 95.0
        }
        
        task = self._create_task({
            "operation": "update_alert_thresholds",
            "thresholds": new_thresholds
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        
        # Verify thresholds were updated
        self.assertEqual(self.resolver.alert_thresholds["cpu_usage"], 80.0)
        self.assertEqual(self.resolver.alert_thresholds["memory_usage"], 85.0)
        self.assertEqual(self.resolver.alert_thresholds["disk_usage"], 95.0)
        
        # Verify config file was updated
        config_file = os.path.join(self.config_dir, "monitoring.json")
        self.assertTrue(os.path.exists(config_file))
        
        with open(config_file, "r") as f:
            config = json.load(f)
            
        self.assertEqual(config["alert_thresholds"]["cpu_usage"], 80.0)
        self.assertEqual(config["alert_thresholds"]["memory_usage"], 85.0)
        self.assertEqual(config["alert_thresholds"]["disk_usage"], 95.0)
    
    async def test_update_alert_thresholds_missing_thresholds(self) -> None:
        """Test updating alert thresholds with missing thresholds."""
        task = self._create_task({
            "operation": "update_alert_thresholds"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Missing or invalid 'thresholds'", result.output_data.get("error", ""))
    
    async def test_get_system_status(self) -> None:
        """Test getting system status."""
        task = self._create_task({
            "operation": "get_system_status"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("system_status", result.output_data)
        
        system_status = result.output_data.get("system_status", {})
        self.assertEqual(system_status.get("overall"), "ok")
        self.assertEqual(system_status.get("checks", {}).get("cpu"), "ok")
        self.assertEqual(system_status.get("checks", {}).get("memory"), "ok")
        self.assertEqual(system_status.get("checks", {}).get("disk"), "ok")
        
        # Test with high CPU usage
        high_cpu_metrics = self.mock_metrics.copy()
        high_cpu_metrics["cpu_usage"] = 95.0
        self.mock_get_metrics.return_value = high_cpu_metrics
        
        result = await self.resolver.resolve(task)
        
        system_status = result.output_data.get("system_status", {})
        self.assertEqual(system_status.get("overall"), "warning")
        self.assertEqual(system_status.get("checks", {}).get("cpu"), "warning")
    
    async def test_clear_old_metrics(self) -> None:
        """Test clearing old metrics."""
        # Create directory structure for old metrics
        old_date = datetime.now() - timedelta(days=40)
        year_dir = os.path.join(self.metrics_dir, str(old_date.year))
        month_dir = os.path.join(year_dir, f"{old_date.month:02d}")
        day_dir = os.path.join(month_dir, f"{old_date.day:02d}")
        os.makedirs(day_dir, exist_ok=True)
        
        # Create a test metrics file
        metrics_file = os.path.join(day_dir, "test.json")
        with open(metrics_file, "w") as f:
            json.dump(self.mock_metrics, f, indent=2)
        
        # Create an old alert file
        alert_file = os.path.join(self.alerts_dir, "old_alert.json")
        with open(alert_file, "w") as f:
            json.dump({"type": "test", "message": "old alert"}, f, indent=2)
        
        # Set file modification time to old date
        os.utime(alert_file, (old_date.timestamp(), old_date.timestamp()))
        
        task = self._create_task({
            "operation": "clear_old_metrics",
            "days": 30,
            "include_alerts": True,
            "dry_run": False
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        
        # Verify old metrics were deleted
        self.assertFalse(os.path.exists(day_dir))
        
        # Verify old alerts were deleted
        self.assertFalse(os.path.exists(alert_file))
    
    async def test_health_check(self) -> None:
        """Test health check operation."""
        task = self._create_task({
            "operation": "health_check"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data.get("status"), "ok")
        self.assertEqual(result.output_data.get("metrics_check"), "ok")
        self.assertEqual(result.output_data.get("alerts_check"), "ok")
        self.assertEqual(result.output_data.get("config_check"), "ok")
        self.assertEqual(result.output_data.get("metrics_collection"), "ok") 