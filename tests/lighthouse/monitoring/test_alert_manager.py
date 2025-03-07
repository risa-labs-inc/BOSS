"""Tests for the AlertManager class."""

import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import json
from datetime import datetime, timedelta

from boss.core.task import Task, TaskResult, TaskStatus
from boss.core.resolvers import TaskResolverMetadata
from boss.lighthouse.monitoring.alert_manager import AlertManager


class TestAlertManager(unittest.TestCase):
    """Test cases for the AlertManager class."""

    def setUp(self):
        """Set up the test fixture."""
        self.metadata = TaskResolverMetadata(
            name="TestAlertManager",
            version="1.0.0",
            description="Test Alert Manager"
        )
        self.manager = AlertManager(self.metadata)
        
        # Create a sample task for testing alert generation
        self.task = Task(
            id="test_task_id",
            resolver_name="AlertManager",
            input_data={
                "operation": "generate_alert",
                "component_id": "test_component",
                "alert_type": "performance",
                "message": "High CPU usage detected",
                "severity": "high",
                "details": {
                    "metric": "cpu_usage",
                    "value": 95.5,
                    "threshold": 90.0
                }
            }
        )
        
    @patch.object(AlertManager, '_send_alert_notifications')
    async def test_handle_generate_alert(self, mock_send):
        """Test handling generate_alert operation."""
        # Run the test
        result = await self.manager._handle_generate_alert(self.task)
        
        # Verify results
        self.assertEqual(result.task_id, "test_task_id")
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn('message', result.output_data)
        self.assertIn('alert', result.output_data)
        
        alert = result.output_data['alert']
        self.assertEqual(alert['component_id'], "test_component")
        self.assertEqual(alert['alert_type'], "performance")
        self.assertEqual(alert['message'], "High CPU usage detected")
        self.assertEqual(alert['severity'], "high")
        self.assertEqual(alert['status'], "active")
        
        # Verify notification was sent
        mock_send.assert_called_once()
        
    async def test_handle_get_active_alerts_empty(self):
        """Test getting active alerts when none exist."""
        # Create a get_active_alerts task
        task = Task(
            id="test_get_alerts",
            resolver_name="AlertManager",
            input_data={
                "operation": "get_active_alerts"
            }
        )
        
        # Run the test
        result = await self.manager._handle_get_active_alerts(task)
        
        # Verify results
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data['count'], 0)
        self.assertEqual(len(result.output_data['alerts']), 0)
        
    @patch.object(AlertManager, '_send_alert_notifications')
    async def test_handle_get_active_alerts_with_filtering(self, mock_send):
        """Test getting active alerts with filtering."""
        # Generate some test alerts
        alert1_task = Task(
            id="alert1",
            resolver_name="AlertManager",
            input_data={
                "operation": "generate_alert",
                "component_id": "component1",
                "alert_type": "performance",
                "message": "Alert 1",
                "severity": "high"
            }
        )
        
        alert2_task = Task(
            id="alert2",
            resolver_name="AlertManager",
            input_data={
                "operation": "generate_alert",
                "component_id": "component2",
                "alert_type": "health",
                "message": "Alert 2",
                "severity": "medium"
            }
        )
        
        # Create the alerts
        await self.manager._handle_generate_alert(alert1_task)
        await self.manager._handle_generate_alert(alert2_task)
        
        # Create a get_active_alerts task with filtering
        task = Task(
            id="test_get_filtered",
            resolver_name="AlertManager",
            input_data={
                "operation": "get_active_alerts",
                "component_id": "component1"
            }
        )
        
        # Run the test
        result = await self.manager._handle_get_active_alerts(task)
        
        # Verify results
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data['count'], 1)
        self.assertEqual(result.output_data['alerts'][0]['component_id'], "component1")
        
    @patch.object(AlertManager, '_send_alert_notifications')
    async def test_handle_acknowledge_alert(self, mock_send):
        """Test acknowledging an alert."""
        # First generate an alert
        await self.manager._handle_generate_alert(self.task)
        
        # Get the alert ID
        result = await self.manager._handle_get_active_alerts(Task(
            id="get_alerts",
            resolver_name="AlertManager",
            input_data={"operation": "get_active_alerts"}
        ))
        
        alert_id = result.output_data['alerts'][0]['id']
        
        # Create an acknowledge task
        ack_task = Task(
            id="test_ack",
            resolver_name="AlertManager",
            input_data={
                "operation": "acknowledge_alert",
                "alert_id": alert_id,
                "message": "Investigating"
            }
        )
        
        # Run the test
        result = await self.manager._handle_acknowledge_alert(ack_task)
        
        # Verify results
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn('alert', result.output_data)
        
        alert = result.output_data['alert']
        self.assertEqual(alert['status'], "acknowledged")
        self.assertIsNotNone(alert['acknowledged_at'])
        self.assertIn('acknowledgements', alert)
        self.assertEqual(alert['acknowledgements'][0]['message'], "Investigating")
        
    @patch.object(AlertManager, '_send_alert_notifications')
    async def test_handle_resolve_alert(self, mock_send):
        """Test resolving an alert."""
        # First generate an alert
        await self.manager._handle_generate_alert(self.task)
        
        # Get the alert ID
        result = await self.manager._handle_get_active_alerts(Task(
            id="get_alerts",
            resolver_name="AlertManager",
            input_data={"operation": "get_active_alerts"}
        ))
        
        alert_id = result.output_data['alerts'][0]['id']
        
        # Create a resolve task
        resolve_task = Task(
            id="test_resolve",
            resolver_name="AlertManager",
            input_data={
                "operation": "resolve_alert",
                "alert_id": alert_id,
                "message": "Fixed the issue"
            }
        )
        
        # Run the test
        result = await self.manager._handle_resolve_alert(resolve_task)
        
        # Verify results
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn('alert', result.output_data)
        
        alert = result.output_data['alert']
        self.assertEqual(alert['status'], "resolved")
        self.assertIsNotNone(alert['resolved_at'])
        self.assertEqual(alert['resolution_message'], "Fixed the issue")
        
        # Verify the alert was moved to history
        self.assertEqual(len(self.manager.alerts), 0)
        self.assertEqual(len(self.manager.alert_history), 1)
        
    @patch.object(AlertManager, '_send_alert_notifications')
    async def test_handle_get_alert_history(self, mock_send):
        """Test getting alert history."""
        # First generate and resolve an alert
        await self.manager._handle_generate_alert(self.task)
        
        # Get the alert ID
        result = await self.manager._handle_get_active_alerts(Task(
            id="get_alerts",
            resolver_name="AlertManager",
            input_data={"operation": "get_active_alerts"}
        ))
        
        alert_id = result.output_data['alerts'][0]['id']
        
        # Resolve the alert
        await self.manager._handle_resolve_alert(Task(
            id="resolve",
            resolver_name="AlertManager",
            input_data={
                "operation": "resolve_alert",
                "alert_id": alert_id
            }
        ))
        
        # Create a get_alert_history task
        history_task = Task(
            id="test_history",
            resolver_name="AlertManager",
            input_data={
                "operation": "get_alert_history",
                "time_window": "24h"
            }
        )
        
        # Run the test
        result = await self.manager._handle_get_alert_history(history_task)
        
        # Verify results
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data['count'], 1)
        self.assertEqual(len(result.output_data['alerts']), 1)
        self.assertEqual(result.output_data['alerts'][0]['id'], alert_id)
        
    @patch.object(AlertManager, '_send_alert_notifications')
    async def test_handle_clear_old_alerts(self, mock_send):
        """Test clearing old alerts."""
        # Add some test history alerts with timestamps in the past
        past_alert = {
            "id": "old_alert",
            "component_id": "test_component",
            "alert_type": "performance",
            "message": "Old alert",
            "severity": "medium",
            "status": "resolved",
            "created_at": (datetime.now() - timedelta(days=40)).isoformat(),
            "resolved_at": (datetime.now() - timedelta(days=39)).isoformat()
        }
        
        recent_alert = {
            "id": "recent_alert",
            "component_id": "test_component",
            "alert_type": "performance",
            "message": "Recent alert",
            "severity": "medium",
            "status": "resolved",
            "created_at": (datetime.now() - timedelta(days=10)).isoformat(),
            "resolved_at": (datetime.now() - timedelta(days=9)).isoformat()
        }
        
        self.manager.alert_history.append(past_alert)
        self.manager.alert_history.append(recent_alert)
        
        # Create a clear_old_alerts task
        clear_task = Task(
            id="test_clear",
            resolver_name="AlertManager",
            input_data={
                "operation": "clear_old_alerts",
                "retention_days": 30
            }
        )
        
        # Run the test
        result = await self.manager._handle_clear_old_alerts(clear_task)
        
        # Verify results
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data['cleared_count'], 1)
        self.assertEqual(len(self.manager.alert_history), 1)
        self.assertEqual(self.manager.alert_history[0]['id'], "recent_alert")
        
    async def test_health_check(self):
        """Test the health check function."""
        # Run the test
        health_status = await self.manager.health_check()
        
        # The health check should return True
        self.assertTrue(health_status)


if __name__ == '__main__':
    unittest.main() 