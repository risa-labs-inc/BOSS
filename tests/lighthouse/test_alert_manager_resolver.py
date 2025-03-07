"""Tests for the AlertManagerResolver."""

import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, cast
import unittest
from unittest.mock import MagicMock, patch

from boss.core.task_models import Task, TaskMetadata, TaskResult
from boss.core.task_resolver import TaskResolverMetadata
from boss.core.task_status import TaskStatus
from boss.lighthouse.alert_manager_resolver import AlertManagerResolver


class TestAlertManagerResolver(unittest.IsolatedAsyncioTestCase):
    """Test suite for the AlertManagerResolver."""

    def setUp(self) -> None:
        """Set up the test environment."""
        # Create temp directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.boss_home_dir = os.path.join(self.temp_dir, "boss_home")
        self.alerts_dir = os.path.join(self.boss_home_dir, "data", "alerts")
        self.config_dir = os.path.join(self.boss_home_dir, "config")
        
        # Create required directories
        os.makedirs(self.boss_home_dir, exist_ok=True)
        os.makedirs(self.alerts_dir, exist_ok=True)
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Mock environment variables
        self.env_patcher = patch.dict("os.environ", {"BOSS_HOME": self.boss_home_dir})
        self.env_patcher.start()
        
        # Create test resolver metadata
        self.metadata = TaskResolverMetadata(
            name="AlertManagerResolver",
            description="Test Resolver",
            version="1.0.0"
        )
        
        # Initialize the resolver
        self.resolver = AlertManagerResolver(self.metadata)
    
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
    
    async def test_process_alert_missing_data(self) -> None:
        """Test processing an alert with missing data."""
        task = self._create_task({
            "operation": "process_alert",
            "alert": {}
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("missing required fields", result.output_data.get("error", ""))
    
    async def test_process_alert_success(self) -> None:
        """Test successfully processing an alert."""
        alert_data = {
            "id": "test-alert-001",
            "severity": "warning",
            "title": "Test Alert",
            "message": "This is a test alert",
            "source": "test_suite"
        }
        
        task = self._create_task({
            "operation": "process_alert",
            "alert": alert_data
        })
        
        # Mock the send methods to avoid actual sending
        with patch.object(self.resolver, '_send_to_channel', return_value={"success": True, "message": "Sent"}):
            result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data.get("alert_id"), "test-alert-001")
        self.assertEqual(result.output_data.get("status"), "processed")
        
        # Check that the alert was stored
        alerts_file = os.path.join(self.alerts_dir, "alerts.json")
        self.assertTrue(os.path.exists(alerts_file))
        
        with open(alerts_file, 'r') as f:
            stored_alerts = json.load(f)
        
        self.assertEqual(len(stored_alerts), 1)
        self.assertEqual(stored_alerts[0]["id"], "test-alert-001")
        self.assertEqual(stored_alerts[0]["status"], "active")
    
    async def test_configure_channel_missing_data(self) -> None:
        """Test configuring a channel with missing data."""
        task = self._create_task({
            "operation": "configure_channel"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Channel type or configuration is missing", result.output_data.get("error", ""))
    
    async def test_configure_channel_invalid_channel(self) -> None:
        """Test configuring an invalid channel type."""
        task = self._create_task({
            "operation": "configure_channel",
            "channel_type": "invalid_channel",
            "config": {"enabled": True}
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Unsupported channel type", result.output_data.get("error", ""))
    
    async def test_configure_channel_success(self) -> None:
        """Test successfully configuring a channel."""
        channel_config = {
            "enabled": True,
            "smtp_server": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "testuser",
            "smtp_password": "testpass",
            "from_address": "test@example.com",
            "recipients": ["recipient@example.com"]
        }
        
        task = self._create_task({
            "operation": "configure_channel",
            "channel_type": "email",
            "config": channel_config
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data.get("channel_type"), "email")
        self.assertEqual(result.output_data.get("status"), "configured")
        
        # Check that the configuration was saved
        config_file = os.path.join(self.config_dir, "alert_manager.json")
        self.assertTrue(os.path.exists(config_file))
        
        with open(config_file, 'r') as f:
            saved_config = json.load(f)
        
        self.assertEqual(saved_config["notification_channels"]["email"]["enabled"], True)
        self.assertEqual(saved_config["notification_channels"]["email"]["smtp_server"], "smtp.example.com")
    
    async def test_update_routing_rules_success(self) -> None:
        """Test successfully updating routing rules."""
        routing_rules = {
            "critical": ["email", "webhook", "console"],
            "error": ["email", "console"],
            "warning": ["console"]
        }
        
        task = self._create_task({
            "operation": "update_routing_rules",
            "routing_rules": routing_rules
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data.get("status"), "updated")
        
        # Check that the configuration was saved
        config_file = os.path.join(self.config_dir, "alert_manager.json")
        self.assertTrue(os.path.exists(config_file))
        
        with open(config_file, 'r') as f:
            saved_config = json.load(f)
        
        self.assertEqual(saved_config["routing_rules"]["critical"], ["email", "webhook", "console"])
        self.assertEqual(saved_config["routing_rules"]["error"], ["email", "console"])
    
    async def test_update_routing_rules_invalid_channel(self) -> None:
        """Test updating routing rules with an invalid channel."""
        routing_rules = {
            "critical": ["email", "invalid_channel", "console"]
        }
        
        task = self._create_task({
            "operation": "update_routing_rules",
            "routing_rules": routing_rules
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Invalid channels", result.output_data.get("error", ""))
    
    async def test_acknowledge_alert_missing_id(self) -> None:
        """Test acknowledging an alert with missing ID."""
        task = self._create_task({
            "operation": "acknowledge_alert"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Alert ID is missing", result.output_data.get("error", ""))
    
    async def test_acknowledge_alert_not_found(self) -> None:
        """Test acknowledging a non-existent alert."""
        task = self._create_task({
            "operation": "acknowledge_alert",
            "alert_id": "nonexistent-alert"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("not found", result.output_data.get("error", ""))
    
    async def test_acknowledge_alert_success(self) -> None:
        """Test successfully acknowledging an alert."""
        # First create an alert
        alert_data = {
            "id": "test-alert-002",
            "severity": "warning",
            "title": "Test Alert",
            "message": "This is a test alert",
            "source": "test_suite",
            "status": "active",
            "timestamp": datetime.now().isoformat()
        }
        
        await self.resolver._store_alert(alert_data)
        
        task = self._create_task({
            "operation": "acknowledge_alert",
            "alert_id": "test-alert-002",
            "acknowledged_by": "test_user"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data.get("alert_id"), "test-alert-002")
        self.assertEqual(result.output_data.get("status"), "acknowledged")
        
        # Check that the alert status was updated
        alerts = await self.resolver._load_alerts()
        alert = next((a for a in alerts if a["id"] == "test-alert-002"), None)
        
        self.assertIsNotNone(alert)
        if alert is not None:
            self.assertEqual(alert["status"], "acknowledged")
            self.assertEqual(alert["acknowledged_by"], "test_user")
    
    async def test_resolve_alert_success(self) -> None:
        """Test successfully resolving an alert."""
        # First create an alert
        alert_data = {
            "id": "test-alert-003",
            "severity": "warning",
            "title": "Test Alert",
            "message": "This is a test alert",
            "source": "test_suite",
            "status": "active",
            "timestamp": datetime.now().isoformat()
        }
        
        await self.resolver._store_alert(alert_data)
        
        task = self._create_task({
            "operation": "resolve_alert",
            "alert_id": "test-alert-003",
            "resolved_by": "test_user",
            "resolution_note": "Test resolution"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data.get("alert_id"), "test-alert-003")
        self.assertEqual(result.output_data.get("status"), "resolved")
        
        # Check that the alert status was updated
        alerts = await self.resolver._load_alerts()
        alert = next((a for a in alerts if a["id"] == "test-alert-003"), None)
        
        self.assertIsNotNone(alert)
        if alert is not None:
            self.assertEqual(alert["status"], "resolved")
            self.assertEqual(alert["resolved_by"], "test_user")
            self.assertEqual(alert["resolution_note"], "Test resolution")
    
    async def test_get_active_alerts(self) -> None:
        """Test retrieving active alerts."""
        # Create several alerts with different statuses
        alert_data = [
            {
                "id": "test-alert-004",
                "severity": "warning",
                "title": "Test Alert 1",
                "message": "This is a test alert",
                "source": "test_suite",
                "status": "active",
                "timestamp": datetime.now().isoformat()
            },
            {
                "id": "test-alert-005",
                "severity": "error",
                "title": "Test Alert 2",
                "message": "This is a test alert",
                "source": "test_suite",
                "status": "acknowledged",
                "timestamp": datetime.now().isoformat()
            },
            {
                "id": "test-alert-006",
                "severity": "critical",
                "title": "Test Alert 3",
                "message": "This is a test alert",
                "source": "test_suite",
                "status": "active",
                "timestamp": datetime.now().isoformat()
            }
        ]
        
        for alert in alert_data:
            await self.resolver._store_alert(alert)
        
        task = self._create_task({
            "operation": "get_active_alerts"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data.get("count"), 2)  # Only active alerts
        
        # Test with filters
        task = self._create_task({
            "operation": "get_active_alerts",
            "filters": {
                "severity": "critical"
            }
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data.get("count"), 1)
        
        # Check that the alert in the result has the expected severity
        alerts = result.output_data.get("alerts")
        self.assertIsNotNone(alerts)
        self.assertTrue(isinstance(alerts, list))
        
        # Type annotation to help the linter
        alerts_list: List[Dict[str, Any]] = alerts if alerts is not None else []
        self.assertGreater(len(alerts_list), 0)
        if len(alerts_list) > 0:
            self.assertEqual(alerts_list[0]["severity"], "critical")
    
    async def test_get_alert_history(self) -> None:
        """Test retrieving alert history."""
        # Create alerts with different timestamps
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        alert_data = [
            {
                "id": "test-alert-007",
                "severity": "warning",
                "title": "Recent Alert",
                "message": "This is a test alert",
                "source": "test_suite",
                "status": "resolved",
                "timestamp": now.isoformat()
            },
            {
                "id": "test-alert-008",
                "severity": "error",
                "title": "Yesterday Alert",
                "message": "This is a test alert",
                "source": "test_suite",
                "status": "resolved",
                "timestamp": yesterday.isoformat()
            },
            {
                "id": "test-alert-009",
                "severity": "critical",
                "title": "Week Old Alert",
                "message": "This is a test alert",
                "source": "test_suite",
                "status": "resolved",
                "timestamp": week_ago.isoformat()
            },
            {
                "id": "test-alert-010",
                "severity": "info",
                "title": "Month Old Alert",
                "message": "This is a test alert",
                "source": "test_suite",
                "status": "resolved",
                "timestamp": month_ago.isoformat()
            }
        ]
        
        for alert in alert_data:
            await self.resolver._store_alert(alert)
        
        # Test default history (7 days)
        task = self._create_task({
            "operation": "get_alert_history"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data.get("count"), 3)  # Excludes month-old alert
        
        # Test with custom time range
        task = self._create_task({
            "operation": "get_alert_history",
            "days": 2
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data.get("count"), 2)  # Only includes recent and yesterday alerts
        
        # Test with severity filter
        task = self._create_task({
            "operation": "get_alert_history",
            "filters": {
                "severity": "critical"
            }
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data.get("count"), 1)
        
        # Check that the alert in the result has the expected severity
        alerts = result.output_data.get("alerts")
        self.assertIsNotNone(alerts)
        self.assertTrue(isinstance(alerts, list))
        
        # Type annotation to help the linter
        alerts_list: List[Dict[str, Any]] = alerts if alerts is not None else []
        self.assertGreater(len(alerts_list), 0)
        if len(alerts_list) > 0:
            self.assertEqual(alerts_list[0]["severity"], "critical")
    
    async def test_clear_old_alerts(self) -> None:
        """Test clearing old alerts."""
        # Create alerts with different timestamps
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        month_ago = now - timedelta(days=30)
        
        alert_data = [
            {
                "id": "test-alert-011",
                "severity": "warning",
                "title": "Recent Alert",
                "message": "This is a test alert",
                "source": "test_suite",
                "status": "resolved",
                "timestamp": now.isoformat()
            },
            {
                "id": "test-alert-012",
                "severity": "error",
                "title": "Yesterday Alert",
                "message": "This is a test alert",
                "source": "test_suite",
                "status": "resolved",
                "timestamp": yesterday.isoformat()
            },
            {
                "id": "test-alert-013",
                "severity": "info",
                "title": "Month Old Alert",
                "message": "This is a test alert",
                "source": "test_suite",
                "status": "resolved",
                "timestamp": month_ago.isoformat()
            }
        ]
        
        for alert in alert_data:
            await self.resolver._store_alert(alert)
        
        # Clear alerts older than 7 days
        task = self._create_task({
            "operation": "clear_old_alerts",
            "days": 7
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data.get("removed_alerts"), 1)  # One alert removed
        self.assertEqual(result.output_data.get("remaining_alerts"), 2)
        
        # Check that the old alert was removed
        alerts = await self.resolver._load_alerts()
        alert_ids = [a["id"] for a in alerts]
        
        self.assertIn("test-alert-011", alert_ids)
        self.assertIn("test-alert-012", alert_ids)
        self.assertNotIn("test-alert-013", alert_ids)
    
    async def test_health_check(self) -> None:
        """Test the health check operation."""
        task = self._create_task({
            "operation": "health_check"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data.get("status"), "healthy")
        self.assertTrue(result.output_data.get("checks", {}).get("alerts_directory"))


if __name__ == "__main__":
    unittest.main() 