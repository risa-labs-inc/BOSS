"""Tests for the refactored DashboardComponents classes."""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import json
from datetime import datetime

import pytest
from boss.lighthouse.monitoring.dashboard_components import DashboardTemplateRenderer, DashboardDataProcessor


class TestDashboardTemplateRenderer(unittest.TestCase):
    """Test cases for the DashboardTemplateRenderer class."""

    def setUp(self):
        """Set up the test fixture."""
        self.template_dir = '/test/templates'
        
        # Mock jinja2 Environment and related components
        self.env_mock = MagicMock()
        self.template_mock = MagicMock()
        self.template_mock.render.return_value = "<html>Rendered HTML</html>"
        self.env_mock.get_template.return_value = self.template_mock
        
        # Patch the jinja2.Environment to return our mock
        with patch('jinja2.Environment', return_value=self.env_mock), \
             patch('jinja2.FileSystemLoader'), \
             patch('jinja2.select_autoescape'):
            self.renderer = DashboardTemplateRenderer(self.template_dir)
    
    def test_render_dashboard(self):
        """Test rendering a dashboard template."""
        # Arrange
        template_name = "test_dashboard"
        context = {"title": "Test Dashboard", "data": {}}
        
        # Act
        result = self.renderer.render_dashboard(template_name, context)
        
        # Assert
        self.env_mock.get_template.assert_called_once_with("test_dashboard.html")
        self.template_mock.render.assert_called_once_with(**context)
        self.assertEqual(result, "<html>Rendered HTML</html>")
    
    def test_render_dashboard_fallback(self):
        """Test rendering a dashboard template with fallback."""
        # Arrange
        template_name = "nonexistent_dashboard"
        context = {"title": "Test Dashboard", "data": {}}
        
        # Create a proper jinja2 exception
        class TemplateNotFound(Exception):
            pass
            
        # Patch jinja2.exceptions.TemplateNotFound
        with patch('jinja2.exceptions.TemplateNotFound', TemplateNotFound):
            # Make get_template throw TemplateNotFound for the first call, then return template_mock
            self.env_mock.get_template.side_effect = [
                TemplateNotFound("Template not found"),
                self.template_mock
            ]
            
            # Act
            result = self.renderer.render_dashboard(template_name, context)
            
            # Assert
            self.assertEqual(self.env_mock.get_template.call_count, 2)
            self.template_mock.render.assert_called_once_with(**context)
            self.assertEqual(result, "<html>Rendered HTML</html>")
    
    def test_render_report(self):
        """Test rendering a report template."""
        # Arrange
        template_name = "test_report"
        context = {"title": "Test Report", "data": {}}
        
        # Act
        result = self.renderer.render_report(template_name, context)
        
        # Assert
        self.env_mock.get_template.assert_called_once_with("test_report.html")
        self.template_mock.render.assert_called_once_with(**context)
        self.assertEqual(result, "<html>Rendered HTML</html>")
    
    def test_format_timestamp(self):
        """Test formatting a timestamp."""
        # Arrange
        timestamp = "2025-03-07T10:15:30"
        
        # Act
        result = self.renderer._format_timestamp(timestamp)
        
        # Assert
        self.assertEqual(result, "2025-03-07 10:15:30")
    
    def test_format_duration(self):
        """Test formatting durations in different units."""
        # Test microseconds
        self.assertEqual(self.renderer._format_duration(0.0005), "500.00 μs")
        
        # Test milliseconds
        self.assertEqual(self.renderer._format_duration(0.5), "500.00 ms")
        
        # Test seconds
        self.assertEqual(self.renderer._format_duration(5.5), "5.50 s")
        
        # Test minutes and seconds
        self.assertEqual(self.renderer._format_duration(125), "2m 5s")
        
        # Test hours, minutes and seconds
        self.assertEqual(self.renderer._format_duration(3725), "1h 2m 5s")


class TestDashboardDataProcessor(unittest.TestCase):
    """Test cases for the DashboardDataProcessor class."""
    
    def test_process_system_metrics_empty(self):
        """Test processing empty system metrics."""
        # Arrange
        metrics = {}
        
        # Act
        result = DashboardDataProcessor.process_system_metrics(metrics)
        
        # Assert
        self.assertEqual(result, {"summary": {}, "time_series": {}, "latest": {}})
    
    def test_process_system_metrics(self):
        """Test processing system metrics."""
        # Arrange
        metrics = {
            "time_series": {
                "timestamps": ["2025-03-07T10:00:00", "2025-03-07T10:01:00", "2025-03-07T10:02:00"],
                "cpu": [10.5, 20.5, 30.5],
                "memory": [40.2, 50.2, 60.2],
                "disk": [15.3, 25.3, 35.3]
            }
        }
        
        # Act
        result = DashboardDataProcessor.process_system_metrics(metrics)
        
        # Assert
        # Check time_series is preserved
        self.assertEqual(result["time_series"], metrics["time_series"])
        
        # Check latest values are correct
        self.assertEqual(result["latest"]["cpu"], 30.5)
        self.assertEqual(result["latest"]["memory"], 60.2)
        self.assertEqual(result["latest"]["disk"], 35.3)
        
        # Check summary values are calculated correctly
        self.assertAlmostEqual(result["summary"]["avg_cpu"], 20.5)
        self.assertAlmostEqual(result["summary"]["avg_memory"], 50.2)
        self.assertAlmostEqual(result["summary"]["avg_disk"], 25.3)
        self.assertAlmostEqual(result["summary"]["max_cpu"], 30.5)
        self.assertAlmostEqual(result["summary"]["max_memory"], 60.2)
        self.assertAlmostEqual(result["summary"]["max_disk"], 35.3)
    
    def test_process_health_data_empty(self):
        """Test processing empty health data."""
        # Arrange
        health_data = {}
        
        # Act
        result = DashboardDataProcessor.process_health_data(health_data)
        
        # Assert
        self.assertEqual(result["summary"]["healthy"], 0)
        self.assertEqual(result["summary"]["warning"], 0)
        self.assertEqual(result["summary"]["critical"], 0)
        self.assertEqual(result["summary"]["unknown"], 0)
        self.assertEqual(result["summary"]["total"], 0)
        self.assertEqual(result["components"], {})
    
    def test_process_health_data(self):
        """Test processing health data."""
        # Arrange
        health_data = {
            "components": {
                "component1": {"status": "healthy", "details": {}},
                "component2": {"status": "warning", "details": {}},
                "component3": {"status": "critical", "details": {}},
                "component4": {"status": "unknown", "details": {}}
            }
        }
        
        # Act
        result = DashboardDataProcessor.process_health_data(health_data)
        
        # Assert
        self.assertEqual(result["summary"]["healthy"], 1)
        self.assertEqual(result["summary"]["warning"], 1)
        self.assertEqual(result["summary"]["critical"], 1)
        self.assertEqual(result["summary"]["unknown"], 1)
        self.assertEqual(result["summary"]["total"], 4)
        self.assertEqual(result["components"], health_data["components"])
    
    def test_process_alerts_data_empty(self):
        """Test processing empty alerts data."""
        # Arrange
        alerts_data = {}
        
        # Act
        result = DashboardDataProcessor.process_alerts_data(alerts_data)
        
        # Assert
        expected_summary = {
            "critical": 0, "error": 0, "warning": 0, "info": 0,
            "total": 0, "active": 0, "resolved": 0
        }
        self.assertEqual(result["summary"], expected_summary)
        self.assertEqual(result["alerts"], [])
        self.assertEqual(result["history"], [])
    
    def test_process_alerts_data(self):
        """Test processing alerts data."""
        # Arrange
        alerts_data = {
            "active_alerts": [
                {"severity": "critical", "details": {}},
                {"severity": "error", "details": {}},
                {"severity": "warning", "details": {}},
                {"severity": "info", "details": {}}
            ],
            "alert_history": [
                {"status": "resolved", "details": {}},
                {"status": "resolved", "details": {}},
                {"status": "acknowledged", "details": {}}
            ]
        }
        
        # Act
        result = DashboardDataProcessor.process_alerts_data(alerts_data)
        
        # Assert
        self.assertEqual(result["summary"]["critical"], 1)
        self.assertEqual(result["summary"]["error"], 1)
        self.assertEqual(result["summary"]["warning"], 1)
        self.assertEqual(result["summary"]["info"], 1)
        self.assertEqual(result["summary"]["total"], 4)
        self.assertEqual(result["summary"]["active"], 4)
        self.assertEqual(result["summary"]["resolved"], 2)
        self.assertEqual(result["alerts"], alerts_data["active_alerts"])
        self.assertEqual(result["history"], alerts_data["alert_history"])
    
    def test_process_performance_data_empty(self):
        """Test processing empty performance data."""
        # Arrange
        performance_data = {}
        
        # Act
        result = DashboardDataProcessor.process_performance_data(performance_data)
        
        # Assert
        expected_summary = {
            "avg_execution_time": 0,
            "max_execution_time": 0,
            "throughput": 0
        }
        self.assertEqual(result["summary"], expected_summary)
        self.assertEqual(result["component_stats"], {})
        self.assertEqual(result["time_series"], {})
    
    def test_process_performance_data(self):
        """Test processing performance data."""
        # Arrange
        performance_data = {
            "component_stats": {
                "component1": {"avg_execution_time": 10.5},
                "component2": {"avg_execution_time": 20.5},
                "component3": {"avg_execution_time": 30.5}
            },
            "time_series": {
                "throughput": [100, 200, 300]
            }
        }
        
        # Act
        result = DashboardDataProcessor.process_performance_data(performance_data)
        
        # Assert
        self.assertAlmostEqual(result["summary"]["avg_execution_time"], 20.5)
        self.assertAlmostEqual(result["summary"]["max_execution_time"], 30.5)
        self.assertAlmostEqual(result["summary"]["throughput"], 200.0)
        self.assertEqual(result["component_stats"], performance_data["component_stats"])
        self.assertEqual(result["time_series"], performance_data["time_series"])


if __name__ == '__main__':
    unittest.main() 