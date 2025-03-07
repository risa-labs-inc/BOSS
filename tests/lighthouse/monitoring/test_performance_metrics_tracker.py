"""Tests for the PerformanceMetricsTracker class."""

import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import json
from datetime import datetime, timedelta

from boss.core.task import Task, TaskResult, TaskStatus
from boss.core.resolvers import TaskResolverMetadata
from boss.lighthouse.monitoring.performance_metrics_tracker import PerformanceMetricsTracker


class TestPerformanceMetricsTracker(unittest.TestCase):
    """Test cases for the PerformanceMetricsTracker class."""

    def setUp(self):
        """Set up the test fixture."""
        self.metadata = TaskResolverMetadata(
            name="TestPerformanceMetricsTracker",
            version="1.0.0",
            description="Test Performance Metrics Tracker"
        )
        self.tracker = PerformanceMetricsTracker(self.metadata)
        
        # Create a sample task for testing
        self.task = Task(
            id="test_task_id",
            resolver_name="PerformanceMetricsTracker",
            input_data={
                "operation": "record_performance_metric",
                "component_id": "test_component",
                "operation_name": "test_operation",
                "execution_time_ms": 150,
                "success": True
            }
        )

    @patch.object(PerformanceMetricsTracker, '_store_performance_metric')
    async def test_handle_record_performance_metric(self, mock_store):
        """Test handling record_performance_metric operation."""
        # Set up mock
        mock_store.return_value = True
        
        # Run the test
        result = await self.tracker._handle_record_performance_metric(self.task)
        
        # Verify results
        self.assertEqual(result.task_id, "test_task_id")
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn('message', result.output_data)
        self.assertIn('recorded', result.output_data['message'])
        
        # Verify the mock was called with the correct data
        mock_store.assert_called_once()
        args = mock_store.call_args[0][0]
        self.assertEqual(args['component_id'], "test_component")
        self.assertEqual(args['operation_name'], "test_operation")
        self.assertEqual(args['execution_time_ms'], 150)
        self.assertTrue(args['success'])
        self.assertIn('timestamp', args)
        
    @patch.object(PerformanceMetricsTracker, '_handle_threshold_violation')
    @patch.object(PerformanceMetricsTracker, '_store_performance_metric')
    async def test_record_performance_metric_with_threshold_violation(self, mock_store, mock_handle_violation):
        """Test that the performance metric recorder detects and handles threshold violations."""
        # Set up mocks
        mock_store.return_value = True
        mock_handle_violation.return_value = None
        
        # Set a threshold that will be violated
        self.tracker.performance_thresholds = {
            "test_component": {
                "test_operation": 100  # 100ms threshold
            }
        }
        
        # Run the test with a metric that exceeds the threshold
        metric = {
            "component_id": "test_component",
            "operation_name": "test_operation",
            "execution_time_ms": 150,  # Exceeds the 100ms threshold
            "success": True,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.tracker._record_performance_metric(metric)
        
        # Verify the threshold violation was handled
        mock_handle_violation.assert_called_once()
        args = mock_handle_violation.call_args[0]
        self.assertEqual(args[0], "test_component")
        self.assertEqual(args[1], "test_operation")
        self.assertEqual(args[2], 150)
        self.assertEqual(args[3], 100)
        
    @patch.object(PerformanceMetricsTracker, '_get_performance_metrics')
    async def test_handle_get_performance_metrics(self, mock_get):
        """Test handling get_performance_metrics operation."""
        # Set up mock data
        mock_metrics = [
            {
                "component_id": "test_component",
                "operation_name": "test_operation",
                "execution_time_ms": 150,
                "success": True,
                "timestamp": (datetime.now() - timedelta(minutes=2)).isoformat()
            },
            {
                "component_id": "test_component",
                "operation_name": "test_operation",
                "execution_time_ms": 100,
                "success": True,
                "timestamp": (datetime.now() - timedelta(minutes=1)).isoformat()
            }
        ]
        mock_get.return_value = mock_metrics
        
        # Create test task
        task = Task(
            id="test_get_metrics",
            resolver_name="PerformanceMetricsTracker",
            input_data={
                "operation": "get_performance_metrics",
                "component_id": "test_component",
                "operation_name": "test_operation",
                "time_window": "1h"
            }
        )
        
        # Run the test
        result = await self.tracker._handle_get_performance_metrics(task)
        
        # Verify results
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn('metrics', result.output_data)
        metrics = result.output_data['metrics']
        self.assertEqual(len(metrics), 2)
        
        # Verify statistics
        self.assertIn('statistics', result.output_data)
        stats = result.output_data['statistics']
        self.assertEqual(stats['count'], 2)
        self.assertEqual(stats['avg_execution_time_ms'], 125.0)
        self.assertEqual(stats['min_execution_time_ms'], 100)
        self.assertEqual(stats['max_execution_time_ms'], 150)
        self.assertEqual(stats['success_rate'], 100.0)
        
    @patch.object(PerformanceMetricsTracker, '_get_performance_metrics')
    async def test_handle_analyze_performance_trend(self, mock_get):
        """Test handling analyze_performance_trend operation."""
        # Generate test data with a clear improving trend (execution times decreasing)
        mock_metrics = []
        base_time = datetime.now()
        
        # Create 10 data points with decreasing execution times
        for i in range(10):
            mock_metrics.append({
                "component_id": "test_component",
                "operation_name": "test_operation",
                "execution_time_ms": 200 - i * 10,  # 200, 190, 180, etc.
                "success": True,
                "timestamp": (base_time - timedelta(minutes=10-i)).isoformat()
            })
            
        mock_get.return_value = mock_metrics
        
        # Create test task
        task = Task(
            id="test_analyze_trend",
            resolver_name="PerformanceMetricsTracker",
            input_data={
                "operation": "analyze_performance_trend",
                "component_id": "test_component",
                "operation_name": "test_operation",
                "time_window": "1h"
            }
        )
        
        # Run the test
        result = await self.tracker._handle_analyze_performance_trend(task)
        
        # Verify results
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn('trend_analysis', result.output_data)
        
        trend = result.output_data['trend_analysis']
        self.assertEqual(trend['trend_direction'], "improving")
        self.assertIn('trend_data', trend)
        self.assertEqual(len(trend['trend_data']), 10)
        
    async def test_health_check(self):
        """Test the health check function."""
        # Run the test
        health_status = await self.tracker.health_check()
        
        # The health check should return True
        self.assertTrue(health_status)
        
    @patch.object(PerformanceMetricsTracker, '_clear_old_metrics')
    async def test_handle_clear_old_metrics(self, mock_clear):
        """Test handling clear_old_metrics operation."""
        # Set up mock
        mock_clear.return_value = 15  # 15 records cleared
        
        # Create test task
        task = Task(
            id="test_clear",
            resolver_name="PerformanceMetricsTracker",
            input_data={
                "operation": "clear_old_metrics",
                "retention_days": 7
            }
        )
        
        # Run the test
        result = await self.tracker._handle_clear_old_metrics(task)
        
        # Verify results
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn('message', result.output_data)
        self.assertIn('records cleared', result.output_data['message'])
        self.assertEqual(result.output_data['records_cleared'], 15)


if __name__ == '__main__':
    unittest.main() 