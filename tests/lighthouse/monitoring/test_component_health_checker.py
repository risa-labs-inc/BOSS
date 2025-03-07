"""Tests for the ComponentHealthChecker class."""

import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import json
from datetime import datetime, timedelta

from boss.core.task import Task, TaskResult, TaskStatus
from boss.core.resolvers import TaskResolverMetadata
from boss.lighthouse.monitoring.component_health_checker import ComponentHealthChecker


class TestComponentHealthChecker(unittest.TestCase):
    """Test cases for the ComponentHealthChecker class."""

    def setUp(self):
        """Set up the test fixture."""
        self.metadata = TaskResolverMetadata(
            name="TestComponentHealthChecker",
            version="1.0.0",
            description="Test Component Health Checker"
        )
        self.checker = ComponentHealthChecker(self.metadata)
        
        # Create a sample task for testing
        self.task = Task(
            id="test_task_id",
            resolver_name="ComponentHealthChecker",
            input_data={
                "operation": "check_component_health",
                "component_id": "test_component"
            }
        )

    @patch.object(ComponentHealthChecker, '_check_component_health')
    async def test_handle_check_component_health(self, mock_check):
        """Test handling check_component_health operation."""
        # Set up mock
        health_result = {
            "component_id": "test_component",
            "status": "healthy",
            "response_time_ms": 42,
            "timestamp": datetime.now().isoformat()
        }
        mock_check.return_value = health_result
        
        # Run the test
        result = await self.checker._handle_check_component_health(self.task)
        
        # Verify results
        self.assertEqual(result.task_id, "test_task_id")
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn('health_check', result.output_data)
        health_check = result.output_data['health_check']
        self.assertEqual(health_check['component_id'], "test_component")
        self.assertEqual(health_check['status'], "healthy")
        
    @patch.object(ComponentHealthChecker, '_store_health_check')
    async def test_check_component_health(self, mock_store):
        """Test the _check_component_health method."""
        # Set up mock
        mock_store.return_value = True
        
        # Create a mock component with a health_check method
        mock_component = MagicMock()
        mock_component.health_check = AsyncMock(return_value=True)
        
        # Simulate the component registry
        with patch.object(self.checker, '_get_component', return_value=mock_component):
            # Run the test
            result = await self.checker._check_component_health("test_component", timeout=1.0)
            
            # Verify results
            self.assertEqual(result['component_id'], "test_component")
            self.assertEqual(result['status'], "healthy")
            self.assertIn('response_time_ms', result)
            self.assertIn('timestamp', result)
            
            # Verify the component's health_check method was called
            mock_component.health_check.assert_called_once()
            
            # Verify the result was stored
            mock_store.assert_called_once()
            
    @patch.object(ComponentHealthChecker, '_get_component')
    async def test_check_component_health_with_timeout(self, mock_get):
        """Test that the component health check handles timeouts properly."""
        # Set up a component that takes too long to respond
        async def slow_health_check():
            await asyncio.sleep(0.2)  # Simulate a slow component
            return True
            
        mock_component = MagicMock()
        mock_component.health_check = slow_health_check
        mock_get.return_value = mock_component
        
        # Run the test with a short timeout
        result = await self.checker._check_component_health("slow_component", timeout=0.1)
        
        # Verify the component timed out
        self.assertEqual(result['component_id'], "slow_component")
        self.assertEqual(result['status'], "unhealthy")
        self.assertIn('error', result)
        self.assertIn('timeout', result['error'])
        
    @patch.object(ComponentHealthChecker, '_get_health_history')
    async def test_handle_get_health_history(self, mock_history):
        """Test handling get_health_history operation."""
        # Set up mock
        mock_history_data = [
            {
                "component_id": "test_component",
                "status": "healthy",
                "response_time_ms": 10,
                "timestamp": (datetime.now() - timedelta(minutes=2)).isoformat()
            },
            {
                "component_id": "test_component",
                "status": "healthy",
                "response_time_ms": 15,
                "timestamp": (datetime.now() - timedelta(minutes=1)).isoformat()
            }
        ]
        mock_history.return_value = mock_history_data
        
        # Create test task
        task = Task(
            id="test_history",
            resolver_name="ComponentHealthChecker",
            input_data={
                "operation": "get_health_history",
                "component_id": "test_component",
                "time_window": "1h"
            }
        )
        
        # Run the test
        result = await self.checker._handle_get_health_history(task)
        
        # Verify results
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn('health_history', result.output_data)
        health_history = result.output_data['health_history']
        self.assertEqual(len(health_history), 2)
        
        # Verify statistics
        self.assertIn('statistics', result.output_data)
        self.assertEqual(result.output_data['statistics']['total_checks'], 2)
        self.assertEqual(result.output_data['statistics']['healthy_percent'], 100.0)
        self.assertEqual(result.output_data['statistics']['avg_response_time_ms'], 12.5)
        
    @patch.object(ComponentHealthChecker, '_get_all_component_ids')
    @patch.object(ComponentHealthChecker, '_check_component_health')
    async def test_handle_check_all_components(self, mock_check, mock_ids):
        """Test handling check_all_components operation."""
        # Set up mocks
        mock_ids.return_value = ["component1", "component2"]
        
        component1_result = {
            "component_id": "component1",
            "status": "healthy",
            "response_time_ms": 10,
            "timestamp": datetime.now().isoformat()
        }
        
        component2_result = {
            "component_id": "component2",
            "status": "unhealthy",
            "error": "Connection refused",
            "response_time_ms": 500,
            "timestamp": datetime.now().isoformat()
        }
        
        mock_check.side_effect = [component1_result, component2_result]
        
        # Create test task
        task = Task(
            id="test_check_all",
            resolver_name="ComponentHealthChecker",
            input_data={
                "operation": "check_all_components"
            }
        )
        
        # Run the test
        result = await self.checker._handle_check_all_components(task)
        
        # Verify results
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn('component_health', result.output_data)
        
        component_health = result.output_data['component_health']
        self.assertEqual(len(component_health), 2)
        
        # Verify the summary
        self.assertIn('summary', result.output_data)
        self.assertEqual(result.output_data['summary']['total_components'], 2)
        self.assertEqual(result.output_data['summary']['healthy_components'], 1)
        self.assertEqual(result.output_data['summary']['unhealthy_components'], 1)
        
    async def test_health_check(self):
        """Test the health check function."""
        # Run the test
        health_status = await self.checker.health_check()
        
        # The health check should return True
        self.assertTrue(health_status)
        
    @patch.object(ComponentHealthChecker, '_clear_old_health_checks')
    async def test_handle_clear_old_health_checks(self, mock_clear):
        """Test handling clear_old_health_checks operation."""
        # Set up mock
        mock_clear.return_value = 10  # 10 records cleared
        
        # Create test task
        task = Task(
            id="test_clear",
            resolver_name="ComponentHealthChecker",
            input_data={
                "operation": "clear_old_health_checks",
                "retention_days": 7
            }
        )
        
        # Run the test
        result = await self.checker._handle_clear_old_health_checks(task)
        
        # Verify results
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn('message', result.output_data)
        self.assertIn('records cleared', result.output_data['message'])
        self.assertEqual(result.output_data['records_cleared'], 10)


if __name__ == '__main__':
    unittest.main() 