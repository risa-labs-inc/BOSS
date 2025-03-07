"""Tests for the DashboardGenerator class."""

import unittest
from unittest.mock import patch, MagicMock, AsyncMock, mock_open
import os
import json
from datetime import datetime, timedelta

from boss.core.task import Task, TaskResult, TaskStatus
from boss.core.resolvers import TaskResolverMetadata
from boss.lighthouse.monitoring.dashboard_generator import DashboardGenerator


class TestDashboardGenerator(unittest.TestCase):
    """Test cases for the DashboardGenerator class."""

    def setUp(self):
        """Set up the test fixture."""
        self.metadata = TaskResolverMetadata(
            name="TestDashboardGenerator",
            version="1.0.0",
            description="Test Dashboard Generator"
        )
        
        # Mock the os.path.join and os.makedirs to avoid filesystem operations
        with patch('os.path.join', return_value='/test/path'), \
             patch('os.makedirs') as mock_makedirs:
            self.generator = DashboardGenerator(self.metadata)
            
            # Verify makedirs was called with exist_ok=True
            mock_makedirs.assert_called_with('/test/path', exist_ok=True)
        
        # Override the output_dir and template_dir for testing
        self.generator.output_dir = '/test/dashboards'
        self.generator.template_dir = '/test/templates'
        
        # Create a sample task for testing dashboard generation
        self.task = Task(
            id="test_task_id",
            resolver_name="DashboardGenerator",
            input_data={
                "operation": "generate_dashboard",
                "dashboard_type": "system",
                "title": "Test System Dashboard"
            }
        )

    @patch('os.path.join', return_value='/test/dashboards/system_123456.html')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    async def test_handle_generate_dashboard(self, mock_json_dump, mock_file_open, mock_join):
        """Test handling generate_dashboard operation."""
        # Mock the HTML generation
        with patch.object(self.generator, '_generate_dashboard_html', return_value="<html>Test</html>"):
            # Run the test
            result = await self.generator._handle_generate_dashboard(self.task)
            
            # Verify results
            self.assertEqual(result.status, TaskStatus.COMPLETED)
            self.assertIn('message', result.output_data)
            self.assertIn('dashboard_id', result.output_data)
            self.assertIn('dashboard_url', result.output_data)
            
            # Verify that the file was opened for writing
            mock_file_open.assert_called()
            
            # Verify that HTML was written to the file
            file_handle = mock_file_open()
            file_handle.write.assert_called_with("<html>Test</html>")
            
            # Verify that the config was written as JSON
            mock_json_dump.assert_called()

    @patch('os.path.join', return_value='/test/dashboards/system_report_123456.html')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    async def test_handle_generate_report(self, mock_json_dump, mock_file_open, mock_join):
        """Test handling generate_report operation."""
        # Create a report task
        report_task = Task(
            id="test_report_id",
            resolver_name="DashboardGenerator",
            input_data={
                "operation": "generate_report",
                "report_type": "system",
                "title": "Test System Report"
            }
        )
        
        # Mock the HTML generation
        with patch.object(self.generator, '_generate_report_html', return_value="<html>Report</html>"):
            # Run the test
            result = await self.generator._handle_generate_report(report_task)
            
            # Verify results
            self.assertEqual(result.status, TaskStatus.COMPLETED)
            self.assertIn('message', result.output_data)
            self.assertIn('report_id', result.output_data)
            self.assertIn('report_url', result.output_data)
            
            # Verify that the file was opened for writing
            mock_file_open.assert_called()
            
            # Verify that HTML was written to the file
            file_handle = mock_file_open()
            file_handle.write.assert_called_with("<html>Report</html>")
            
            # Verify that the config was written as JSON
            mock_json_dump.assert_called()

    @patch('os.path.exists', return_value=True)
    @patch('os.path.join', return_value='/test/dashboards/test_dashboard.json')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    async def test_handle_get_dashboard_url(self, mock_json_load, mock_file_open, mock_join, mock_exists):
        """Test handling get_dashboard_url operation."""
        # Mock the config data
        mock_json_load.return_value = {
            "id": "test_dashboard",
            "type": "system",
            "title": "Test Dashboard"
        }
        
        # Create a get dashboard URL task
        task = Task(
            id="test_get_url",
            resolver_name="DashboardGenerator",
            input_data={
                "operation": "get_dashboard_url",
                "dashboard_id": "test_dashboard"
            }
        )
        
        # Run the test
        result = await self.generator._handle_get_dashboard_url(task)
        
        # Verify results
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn('dashboard_id', result.output_data)
        self.assertIn('dashboard_url', result.output_data)
        self.assertEqual(result.output_data['dashboard_id'], "test_dashboard")
        self.assertEqual(result.output_data['dashboard_url'], "/dashboards/test_dashboard.html")

    @patch('os.listdir')
    @patch('os.path.join')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    async def test_handle_list_dashboards(self, mock_json_load, mock_file_open, mock_join, mock_listdir):
        """Test handling list_dashboards operation."""
        # Mock the directory listing
        mock_listdir.return_value = [
            "system_dashboard.json",
            "health_dashboard.json",
            "system_report.json"  # This should be filtered out
        ]
        
        # Mock path joining
        mock_join.side_effect = lambda a, b: f"{a}/{b}"
        
        # Mock the config data
        dashboard1 = {
            "id": "system_dashboard",
            "type": "system",
            "title": "System Dashboard",
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00"
        }
        
        dashboard2 = {
            "id": "health_dashboard",
            "type": "health",
            "title": "Health Dashboard",
            "created_at": "2023-01-02T00:00:00",
            "updated_at": "2023-01-02T00:00:00"
        }
        
        # Set up the mock to return different values based on which file is being opened
        mock_json_load.side_effect = [dashboard1, dashboard2]
        
        # Create a list dashboards task
        task = Task(
            id="test_list",
            resolver_name="DashboardGenerator",
            input_data={
                "operation": "list_dashboards"
            }
        )
        
        # Run the test
        result = await self.generator._handle_list_dashboards(task)
        
        # Verify results
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn('dashboards', result.output_data)
        self.assertEqual(result.output_data['count'], 2)
        
        # The dashboards should be sorted by created_at (newest first)
        self.assertEqual(result.output_data['dashboards'][0]['id'], "health_dashboard")
        self.assertEqual(result.output_data['dashboards'][1]['id'], "system_dashboard")

    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.remove')
    async def test_health_check(self, mock_remove, mock_open, mock_makedirs, mock_exists):
        """Test the health check function."""
        # Mock os.path.exists to return False first (to test directory creation)
        mock_exists.return_value = False
        
        # Run the test
        health_status = await self.generator.health_check()
        
        # Verify the directory was created if it didn't exist
        mock_makedirs.assert_called_with(self.generator.output_dir, exist_ok=True)
        
        # Verify a test file was created and then removed
        mock_open.assert_called()
        mock_remove.assert_called()
        
        # The health check should return True
        self.assertTrue(health_status)
        
    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('builtins.open')
    async def test_health_check_failure(self, mock_open, mock_makedirs, mock_exists):
        """Test health check when there's a failure."""
        # Mock os.makedirs to raise an exception
        mock_exists.return_value = False
        mock_makedirs.side_effect = Exception("Permission denied")
        
        # Run the test
        health_status = await self.generator.health_check()
        
        # The health check should return False
        self.assertFalse(health_status)
        
    def test_generate_dashboard_html(self):
        """Test the dashboard HTML generation."""
        # Create a test configuration
        config = {
            "type": "system",
            "title": "Test Dashboard",
            "components": ["cpu", "memory"],
            "refresh_interval": 30
        }
        
        # Run the test
        html = self.generator._generate_dashboard_html(config)
        
        # Verify the HTML contains the expected elements
        self.assertIn("<title>Test Dashboard</title>", html)
        self.assertIn("Auto-refreshes every 30 seconds", html)
        self.assertIn("<h2>Cpu</h2>", html)
        self.assertIn("<h2>Memory</h2>", html)
        
    def test_generate_report_html(self):
        """Test the report HTML generation."""
        # Create a test configuration
        config = {
            "type": "system",
            "title": "Test Report",
            "time_window": "3d"
        }
        
        # Run the test
        html = self.generator._generate_report_html(config)
        
        # Verify the HTML contains the expected elements
        self.assertIn("<title>Test Report</title>", html)
        self.assertIn("Time Window: 3d", html)
        self.assertIn("<h2>Overview</h2>", html)


if __name__ == '__main__':
    unittest.main() 