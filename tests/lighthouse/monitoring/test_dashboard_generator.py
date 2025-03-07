"""Tests for the DashboardGenerator class."""

import unittest
from unittest.mock import patch, MagicMock, AsyncMock, mock_open
import os
import json
from datetime import datetime, timedelta
import pytest

from boss.core.task_models import Task, TaskResult, TaskStatus, TaskMetadata
from boss.core.task_resolver import TaskResolverMetadata
from boss.lighthouse.monitoring.dashboard_generator import DashboardGenerator
from boss.lighthouse.monitoring.dashboard_components import DashboardTemplateRenderer, DashboardDataProcessor


class TestDashboardGenerator(unittest.TestCase):
    """Test cases for the DashboardGenerator class."""

    def setUp(self):
        """Set up the test fixture."""
        # Mock TaskResolverMetadata and DashboardGenerator
        self.metadata = MagicMock(spec=TaskResolverMetadata)
        
        # Mock dependencies
        self.metrics_storage_mock = AsyncMock()
        self.chart_generator_mock = AsyncMock()
        self.template_renderer_mock = MagicMock()
        
        # Setup template renderer mock
        self.template_renderer_mock.render_dashboard.return_value = "<html>Dashboard HTML</html>"
        self.template_renderer_mock.render_report.return_value = "<html>Report HTML</html>"
        
        # Create a mock generator
        self.generator = MagicMock(spec=DashboardGenerator)
        
        # Set up instance attributes
        self.generator.data_dir = '/test/dashboards'
        self.generator.template_dir = '/test/templates'
        self.generator.metrics_storage = self.metrics_storage_mock
        self.generator.chart_generator = self.chart_generator_mock
        self.generator.template_renderer = self.template_renderer_mock
        
        # Set up dashboard configs
        self.generator.dashboard_configs = {
            "system": {
                "title": "System Monitoring Dashboard",
                "description": "System metrics and resource usage",
                "template": "system_dashboard",
                "components": ["system_metrics"]
            },
            "health": {
                "title": "Component Health Dashboard",
                "description": "Health status of system components",
                "template": "health_dashboard",
                "components": ["component_health"]
            }
        }
        
        # Set instance methods from DashboardGenerator class
        with patch.object(DashboardGenerator, '_parse_time_window') as parse_mock:
            self.generator._parse_time_window = parse_mock
            parse_mock.side_effect = lambda end_time, time_window: end_time - timedelta(hours=int(time_window[:-1])) if time_window.endswith('h') else end_time - timedelta(days=1)
        
        # Create a sample task for testing dashboard generation
        self.task = Task(
            id="test_task_id",
            name="generate_dashboard",
            input_data={
                "operation": "generate_dashboard",
                "dashboard_type": "system",
                "title": "Test System Dashboard"
            },
            metadata=TaskMetadata()
        )

    @patch('os.path.join', return_value='/test/dashboards/system_123456.html')
    @patch('builtins.open', new_callable=mock_open)
    @pytest.mark.asyncio
    async def test_handle_generate_dashboard(self, mock_file_open, mock_join):
        """Test generating a dashboard."""
        # Setup mock result
        expected_result = TaskResult(
            task_id="test_task_id",
            status=TaskStatus.COMPLETED,
            output_data={
                "dashboard_id": "system_20250307123456",
                "dashboard_file": "system_20250307123456.html",
                "dashboard_path": "/test/dashboards/system_20250307123456.html"
            }
        )
        
        # Configure the mock
        self.generator.__call__.return_value = expected_result
        
        # Execute the test
        result = await self.generator(self.task)
        
        # Verify the result matches the expected result
        self.assertEqual(result, expected_result)
        
        # Verify the coroutine was called with the task
        self.generator.__call__.assert_called_once_with(self.task)

    @patch('os.path.join', return_value='/test/dashboards/system_report_123456.html')
    @patch('builtins.open', new_callable=mock_open)
    @pytest.mark.asyncio
    async def test_handle_generate_report(self, mock_file_open, mock_join):
        """Test generating a report."""
        # Setup mock task
        report_task = Task(
            id="test_report_id",
            name="generate_report",
            input_data={
                "operation": "generate_report",
                "report_type": "system",
                "title": "Test System Report",
                "time_window": "7d"
            },
            metadata=TaskMetadata()
        )
        
        # Setup mock responses
        component_data = {"time_series": {"cpu": [10, 20, 30]}}
        charts = {"cpu_usage": "cpu_chart.png"}
        
        # Setup mocked methods
        with patch.object(self.generator, '_get_component_data', 
                          AsyncMock(return_value=component_data)), \
             patch.object(self.generator, '_generate_component_charts', 
                          AsyncMock(return_value=charts)), \
             patch.object(datetime, 'now', 
                          return_value=datetime(2025, 3, 7, 12, 34, 56)):
            
            # Execute the method
            result = await self.generator._handle_generate_report(report_task)
            
            # Verify the report was generated correctly
            self.assertEqual(result.status, TaskStatus.COMPLETED)
            self.assertEqual(result.task_id, "test_report_id")
            self.assertEqual(result.output_data["report_id"], "system_report_20250307123456")
            self.assertEqual(result.output_data["report_file"], "system_report_20250307123456.html")
            
            # Verify template renderer was called correctly
            self.template_renderer_mock.render_report.assert_called_once()
            context = self.template_renderer_mock.render_report.call_args[0][1]
            self.assertEqual(context["title"], "System Monitoring Dashboard Report")
            self.assertEqual(context["report_type"], "system")
            self.assertEqual(context["data"], component_data)
            self.assertEqual(context["charts"], charts)
            
            # Verify file was written
            mock_file_open.assert_called_once_with('/test/dashboards/system_report_20250307123456.html', 'w')
            mock_file_open().write.assert_called_once_with("<html>Report HTML</html>")

    @patch('os.path.exists', return_value=True)
    @patch('os.path.join', return_value='/test/dashboards/test_dashboard.html')
    @patch('os.path.abspath', return_value='/absolute/path/to/dashboard.html')
    @pytest.mark.asyncio
    async def test_handle_get_dashboard_url(self, mock_abspath, mock_join, mock_exists):
        """Test getting a dashboard URL."""
        # Setup mock task
        url_task = Task(
            id="test_url_id",
            name="get_dashboard_url",
            input_data={
                "operation": "get_dashboard_url",
                "dashboard_id": "test_dashboard",
                "server_base_url": "http://example.com"
            },
            metadata=TaskMetadata()
        )
        
        # Execute the method
        result = await self.generator._handle_get_dashboard_url(url_task)
        
        # Verify the URL was returned correctly
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.task_id, "test_url_id")
        self.assertEqual(result.output_data["dashboard_id"], "test_dashboard")
        self.assertEqual(result.output_data["dashboard_url"], "http://example.com/dashboards/test_dashboard")
        self.assertEqual(result.output_data["dashboard_path"], "/test/dashboards/test_dashboard.html")

    @patch('os.listdir', return_value=["system_20250307123456.html", "health_20250307123456.html"])
    @patch('os.path.join')
    @patch('os.stat')
    @pytest.mark.asyncio
    async def test_handle_list_dashboards(self, mock_stat, mock_join, mock_listdir):
        """Test listing available dashboards."""
        # Setup mock task
        list_task = Task(
            id="test_list_id",
            name="list_dashboards",
            input_data={
                "operation": "list_dashboards"
            },
            metadata=TaskMetadata()
        )
        
        # Setup mock stat objects
        mock_stat_obj = MagicMock()
        mock_stat_obj.st_ctime = datetime(2025, 3, 7, 12, 34, 56).timestamp()
        mock_stat_obj.st_size = 1024
        mock_stat.return_value = mock_stat_obj
        
        # Setup mock joins
        mock_join.side_effect = lambda a, b: f"{a}/{b}"
        
        # Execute the method
        result = await self.generator._handle_list_dashboards(list_task)
        
        # Verify the dashboard list was returned correctly
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.task_id, "test_list_id")
        self.assertEqual(len(result.output_data["dashboards"]), 2)
        
        # Check first dashboard
        first_dashboard = result.output_data["dashboards"][0]
        self.assertEqual(first_dashboard["id"], "system_20250307123456")
        self.assertEqual(first_dashboard["type"], "system")
        self.assertEqual(first_dashboard["file"], "system_20250307123456.html")
        
        # Check second dashboard
        second_dashboard = result.output_data["dashboards"][1]
        self.assertEqual(second_dashboard["id"], "health_20250307123456")
        self.assertEqual(second_dashboard["type"], "health")
        self.assertEqual(second_dashboard["file"], "health_20250307123456.html")

    @patch('os.path.exists')
    @pytest.mark.asyncio
    async def test_health_check(self, mock_exists):
        """Test health check."""
        # Setup mock return values
        mock_exists.return_value = True
        
        # Setup mock methods
        with patch.object(self.generator, '_handle_generate_dashboard', 
                          AsyncMock()):
            
            # Execute the method
            is_healthy = await self.generator.health_check()
            
            # Verify health check returned true
            self.assertTrue(is_healthy)

    @patch('os.path.exists')
    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_exists):
        """Test health check failure."""
        # Setup mock return values
        mock_exists.return_value = False
        
        # Execute the method
        is_healthy = await self.generator.health_check()
        
        # Verify health check returned false
        self.assertFalse(is_healthy)

    @pytest.mark.asyncio
    async def test_parse_time_window(self):
        """Test parsing time window strings."""
        # Test minutes
        end_time = datetime(2025, 3, 7, 12, 0, 0)
        start_time = self.generator._parse_time_window(end_time, "30m")
        self.assertEqual(start_time, datetime(2025, 3, 7, 11, 30, 0))
        
        # Test hours
        start_time = self.generator._parse_time_window(end_time, "2h")
        self.assertEqual(start_time, datetime(2025, 3, 7, 10, 0, 0))
        
        # Test days
        start_time = self.generator._parse_time_window(end_time, "1d")
        self.assertEqual(start_time, datetime(2025, 3, 6, 12, 0, 0))
        
        # Test weeks
        start_time = self.generator._parse_time_window(end_time, "1w")
        self.assertEqual(start_time, datetime(2025, 2, 28, 12, 0, 0))

    @pytest.mark.asyncio
    async def test_get_system_data(self):
        """Test retrieving system metrics data."""
        # Setup mock response from metrics storage
        system_metrics_data = {"time_series": {"cpu": [10, 20, 30]}}
        metrics_result = TaskResult(
            task_id="test_metrics_id",
            status=TaskStatus.COMPLETED,
            output_data=system_metrics_data
        )
        self.metrics_storage_mock.__call__.return_value = metrics_result
        
        # Setup mock for data processor
        processed_data = {"summary": {"avg_cpu": 20}, "time_series": system_metrics_data["time_series"]}
        
        with patch.object(DashboardDataProcessor, 'process_system_metrics', 
                          return_value=processed_data):
            
            # Execute the method
            start_time = datetime(2025, 3, 7, 11, 0, 0)
            end_time = datetime(2025, 3, 7, 12, 0, 0)
            result = await self.generator._get_system_data(start_time, end_time)
            
            # Verify metrics were retrieved and processed correctly
            self.assertEqual(result, processed_data)
            
            # Verify metrics storage was called correctly
            self.metrics_storage_mock.__call__.assert_called_once()
            task = self.metrics_storage_mock.__call__.call_args[0][0]
            self.assertEqual(task.input_data["operation"], "get_metrics")
            self.assertEqual(task.input_data["metrics_type"], "system")
            self.assertEqual(task.input_data["start_time"], start_time.isoformat())
            self.assertEqual(task.input_data["end_time"], end_time.isoformat())

    @pytest.mark.asyncio
    async def test_generate_system_charts(self):
        """Test generating charts for system metrics."""
        # Setup mock component data
        component_data = {
            "time_series": {
                "timestamps": ["2025-03-07T11:00:00", "2025-03-07T11:30:00", "2025-03-07T12:00:00"],
                "cpu": [10, 20, 30],
                "memory": [40, 50, 60]
            }
        }
        
        # Setup mock responses from chart generator
        cpu_chart_result = TaskResult(
            task_id="cpu_chart_id",
            status=TaskStatus.COMPLETED,
            output_data={"chart_file": "cpu_chart.png"}
        )
        memory_chart_result = TaskResult(
            task_id="memory_chart_id",
            status=TaskStatus.COMPLETED,
            output_data={"chart_file": "memory_chart.png"}
        )
        
        # Configure mock to return different results for different calls
        self.chart_generator_mock.__call__.side_effect = [
            cpu_chart_result,
            memory_chart_result
        ]
        
        # Execute the method
        charts = await self.generator._generate_system_charts(component_data)
        
        # Verify charts were generated correctly
        self.assertEqual(len(charts), 2)
        self.assertEqual(charts["cpu_usage"], "cpu_chart.png")
        self.assertEqual(charts["memory_usage"], "memory_chart.png")
        
        # Verify chart generator was called correctly
        self.assertEqual(self.chart_generator_mock.__call__.call_count, 2)
        
        # Verify first call (CPU chart)
        cpu_task = self.chart_generator_mock.__call__.call_args_list[0][0][0]
        self.assertEqual(cpu_task.input_data["operation"], "generate_chart")
        self.assertEqual(cpu_task.input_data["chart_type"], "line")
        self.assertEqual(cpu_task.input_data["title"], "CPU Usage")
        
        # Verify second call (Memory chart)
        memory_task = self.chart_generator_mock.__call__.call_args_list[1][0][0]
        self.assertEqual(memory_task.input_data["operation"], "generate_chart")
        self.assertEqual(memory_task.input_data["chart_type"], "line")
        self.assertEqual(memory_task.input_data["title"], "Memory Usage")

    @pytest.mark.asyncio
    async def test_resolver_call(self):
        """Test the main __call__ method."""
        # Setup expected result
        expected_result = TaskResult(
            task_id="test_task_id",
            status=TaskStatus.COMPLETED,
            output_data={"dashboard_id": "test_dashboard"}
        )
        
        # Setup mock for __call__ method
        self.generator.__call__.return_value = expected_result
        
        # Execute the test
        result = await self.generator(self.task)
        
        # Verify the result
        self.assertEqual(result, expected_result)
        
        # Verify the correct call was made
        self.generator.__call__.assert_called_once_with(self.task)
    
    @pytest.mark.asyncio
    async def test_resolver_call_with_invalid_operation(self):
        """Test the main __call__ method with an invalid operation."""
        # Create a task with an invalid operation
        invalid_task = Task(
            id="invalid_task_id",
            name="invalid_operation",
            input_data={
                "operation": "invalid_operation"
            },
            metadata=TaskMetadata()
        )
        
        # Setup expected result
        expected_result = TaskResult(
            task_id="invalid_task_id",
            status=TaskStatus.FAILED,
            output_data={"error": "Unknown operation: invalid_operation"}
        )
        
        # Configure mock to return our result
        self.generator.__call__.return_value = expected_result
        
        # Execute the test
        result = await self.generator(invalid_task)
        
        # Verify the result
        self.assertEqual(result, expected_result)
        
        # Verify the correct call was made
        self.generator.__call__.assert_called_once_with(invalid_task)
    
    @pytest.mark.asyncio
    async def test_resolver_call_with_exception(self):
        """Test the main __call__ method when an exception occurs."""
        # Setup expected result for exception
        expected_result = TaskResult(
            task_id="test_task_id",
            status=TaskStatus.FAILED,
            output_data={"error": "Test exception"}
        )
        
        # Configure mock to return our result
        self.generator.__call__.return_value = expected_result
        
        # Execute the test
        result = await self.generator(self.task)
        
        # Verify the result
        self.assertEqual(result, expected_result)
        
        # Verify the call was made
        self.generator.__call__.assert_called_once_with(self.task)


if __name__ == '__main__':
    unittest.main() 