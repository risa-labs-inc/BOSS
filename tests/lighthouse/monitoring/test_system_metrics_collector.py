"""Tests for the SystemMetricsCollector class."""

import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import json
from datetime import datetime, timedelta

from boss.core.task import Task, TaskResult, TaskStatus
from boss.core.resolvers import TaskResolverMetadata
from boss.lighthouse.monitoring.system_metrics_collector import SystemMetricsCollector


class TestSystemMetricsCollector(unittest.TestCase):
    """Test cases for the SystemMetricsCollector class."""

    def setUp(self):
        """Set up the test fixture."""
        self.metadata = TaskResolverMetadata(
            name="TestSystemMetricsCollector",
            version="1.0.0",
            description="Test System Metrics Collector"
        )
        self.collector = SystemMetricsCollector(self.metadata)
        
        # Create a sample task for testing
        self.task = Task(
            id="test_task_id",
            resolver_name="SystemMetricsCollector",
            input_data={
                "operation": "collect_system_metrics",
                "metrics_type": "cpu"
            }
        )

    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    def test_collect_cpu_metrics(self, mock_memory, mock_cpu):
        """Test collecting CPU metrics."""
        # Set up mocks
        mock_cpu.return_value = 42.5
        mock_memory.return_value = MagicMock(percent=33.3)
        
        # Run the test
        metrics = self.collector._collect_cpu_metrics()
        
        # Verify results
        self.assertIn('usage_percent', metrics)
        self.assertEqual(metrics['usage_percent'], 42.5)
        self.assertIn('timestamp', metrics)
        
    @patch('psutil.disk_usage')
    def test_collect_disk_metrics(self, mock_disk_usage):
        """Test collecting disk metrics."""
        # Set up mock
        mock_disk_return = MagicMock()
        mock_disk_return.total = 1000000000
        mock_disk_return.used = 500000000
        mock_disk_return.free = 500000000
        mock_disk_return.percent = 50.0
        mock_disk_usage.return_value = mock_disk_return
        
        # Run the test
        metrics = self.collector._collect_disk_metrics()
        
        # Verify results
        self.assertIn('total_gb', metrics)
        self.assertIn('used_gb', metrics)
        self.assertIn('free_gb', metrics)
        self.assertIn('usage_percent', metrics)
        self.assertEqual(metrics['usage_percent'], 50.0)

    @patch('psutil.virtual_memory')
    def test_collect_memory_metrics(self, mock_virtual_memory):
        """Test collecting memory metrics."""
        # Set up mock
        mock_memory = MagicMock()
        mock_memory.total = 16000000000
        mock_memory.available = 8000000000
        mock_memory.used = 8000000000
        mock_memory.percent = 50.0
        mock_virtual_memory.return_value = mock_memory
        
        # Run the test
        metrics = self.collector._collect_memory_metrics()
        
        # Verify results
        self.assertIn('total_gb', metrics)
        self.assertIn('available_gb', metrics)
        self.assertIn('used_gb', metrics)
        self.assertIn('usage_percent', metrics)
        self.assertEqual(metrics['usage_percent'], 50.0)

    @patch('psutil.net_io_counters')
    def test_collect_network_metrics(self, mock_net_io):
        """Test collecting network metrics."""
        # Set up mock
        mock_net = MagicMock()
        mock_net.bytes_sent = 1000000
        mock_net.bytes_recv = 2000000
        mock_net.packets_sent = 1000
        mock_net.packets_recv = 2000
        mock_net_io.return_value = mock_net
        
        # Run the test
        metrics = self.collector._collect_network_metrics()
        
        # Verify results
        self.assertIn('bytes_sent_mb', metrics)
        self.assertIn('bytes_received_mb', metrics)
        self.assertIn('packets_sent', metrics)
        self.assertIn('packets_received', metrics)
        self.assertEqual(metrics['packets_sent'], 1000)
        self.assertEqual(metrics['packets_received'], 2000)

    @patch.object(SystemMetricsCollector, '_collect_cpu_metrics')
    @patch.object(SystemMetricsCollector, '_collect_memory_metrics')
    @patch.object(SystemMetricsCollector, '_collect_disk_metrics')
    @patch.object(SystemMetricsCollector, '_collect_network_metrics')
    async def test_handle_collect_system_metrics(self, mock_network, mock_disk, 
                                                mock_memory, mock_cpu):
        """Test handling collect_system_metrics operation."""
        # Set up mocks
        mock_cpu.return_value = {'usage_percent': 42.5, 'timestamp': 'cpu_time'}
        mock_memory.return_value = {'usage_percent': 50.0, 'timestamp': 'mem_time'}
        mock_disk.return_value = {'usage_percent': 60.0, 'timestamp': 'disk_time'}
        mock_network.return_value = {'bytes_sent_mb': 1.0, 'timestamp': 'net_time'}
        
        # Run the test
        result = await self.collector._handle_collect_system_metrics(self.task)
        
        # Verify results
        self.assertEqual(result.task_id, "test_task_id")
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn('metrics', result.output_data)
        
        metrics = result.output_data['metrics']
        # Since we specified metrics_type="cpu" in the task, only CPU metrics should be returned
        self.assertEqual(metrics['type'], 'cpu')
        self.assertEqual(metrics['usage_percent'], 42.5)

    @patch.object(SystemMetricsCollector, '_store_metrics')
    async def test_handle_get_system_metrics(self, mock_store):
        """Test handling get_system_metrics operation."""
        # Set up mock
        mock_metrics = [
            {'type': 'cpu', 'usage_percent': 40.0, 'timestamp': '2023-01-01T00:00:00'},
            {'type': 'cpu', 'usage_percent': 45.0, 'timestamp': '2023-01-01T00:01:00'},
            {'type': 'cpu', 'usage_percent': 50.0, 'timestamp': '2023-01-01T00:02:00'}
        ]
        mock_store.return_value = mock_metrics
        
        # Create test task
        task = Task(
            id="test_get_metrics",
            resolver_name="SystemMetricsCollector",
            input_data={
                "operation": "get_system_metrics",
                "metrics_type": "cpu",
                "time_window": "1h"
            }
        )
        
        # Run the test
        result = await self.collector._handle_get_system_metrics(task)
        
        # Verify results
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn('metrics', result.output_data)
        self.assertEqual(len(result.output_data['metrics']), 3)
        self.assertEqual(result.output_data['metrics_type'], 'cpu')
        
        # Verify statistics
        self.assertIn('statistics', result.output_data)
        self.assertIn('avg_usage_percent', result.output_data['statistics'])
        self.assertEqual(result.output_data['statistics']['avg_usage_percent'], 45.0)

    async def test_health_check(self):
        """Test the health check function."""
        # Run the test
        health_status = await self.collector.health_check()
        
        # The health check should return True
        self.assertTrue(health_status)

    @patch.object(SystemMetricsCollector, '_get_metrics')
    async def test_handle_clear_old_metrics(self, mock_get):
        """Test handling clear_old_metrics operation."""
        # Set up mock
        mock_get.return_value = []
        
        # Create test task
        task = Task(
            id="test_clear_metrics",
            resolver_name="SystemMetricsCollector",
            input_data={
                "operation": "clear_old_metrics",
                "retention_days": 7
            }
        )
        
        # Run the test
        result = await self.collector._handle_clear_old_metrics(task)
        
        # Verify results
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn('message', result.output_data)
        self.assertTrue('cleared' in result.output_data['message'])
        

if __name__ == '__main__':
    unittest.main() 