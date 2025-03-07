"""Tests for the monitoring API.

This module contains test cases for the MonitoringAPI class and its various endpoints.
"""

import json
import os
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta

# Import FastAPI TestClient with type stub fallback
try:
    from fastapi.testclient import TestClient
except ImportError:
    # Type stub for mypy if module is not installed
    class TestClient:
        def __init__(self, app): 
            self.app = app
        
        def get(self, url, params=None):
            pass
            
        def post(self, url, params=None, json=None):
            pass

from boss.lighthouse.monitoring.api import MonitoringAPI
from boss.lighthouse.monitoring.metrics_storage import MetricsStorage
from boss.lighthouse.monitoring.system_metrics_collector import SystemMetricsCollector
from boss.lighthouse.monitoring.component_health_checker import ComponentHealthChecker
from boss.lighthouse.monitoring.performance_metrics_tracker import PerformanceMetricsTracker
from boss.lighthouse.monitoring.dashboard_generator import DashboardGenerator

# For mypy type checking - can be safely ignored at runtime
try:
    from boss.core.task_resolver_metadata import TaskResolverMetadata
    from boss.core.task_models import Task, TaskResult, TaskStatus
except ImportError:
    # Type stubs for mypy
    class TaskResolverMetadata:
        def __init__(self, id, name, description, version, properties): pass
    
    class Task: pass
    class TaskResult: pass
    class TaskStatus:
        @staticmethod
        def is_success(): pass
        COMPLETED = "COMPLETED"


class TestMonitoringAPI:
    """Test cases for the MonitoringAPI class."""

    @pytest.fixture
    def metrics_storage(self, tmp_path):
        """Create a MetricsStorage instance for testing."""
        return MagicMock(spec=MetricsStorage)

    @pytest.fixture
    def system_metrics_collector(self, metrics_storage):
        """Create a SystemMetricsCollector mock for testing."""
        collector = MagicMock(spec=SystemMetricsCollector)
        collector.return_value = TaskResult(
            task_id="test-task",
            status=TaskStatus.COMPLETED,
            output_data={"success": True}
        )
        return collector

    @pytest.fixture
    def component_health_checker(self, metrics_storage):
        """Create a ComponentHealthChecker mock for testing."""
        checker = MagicMock(spec=ComponentHealthChecker)
        checker.return_value = TaskResult(
            task_id="test-task",
            status=TaskStatus.COMPLETED,
            output_data={"success": True}
        )
        return checker

    @pytest.fixture
    def performance_metrics_tracker(self, metrics_storage):
        """Create a PerformanceMetricsTracker mock for testing."""
        tracker = MagicMock(spec=PerformanceMetricsTracker)
        tracker.return_value = TaskResult(
            task_id="test-task",
            status=TaskStatus.COMPLETED,
            output_data={"success": True}
        )
        return tracker

    @pytest.fixture
    def dashboard_generator(self, metrics_storage):
        """Create a DashboardGenerator mock for testing."""
        generator = MagicMock(spec=DashboardGenerator)
        generator.return_value = TaskResult(
            task_id="test-task",
            status=TaskStatus.COMPLETED,
            output_data={"dashboard_file": "test.html"}
        )
        return generator

    @pytest.fixture
    def api(self, tmp_path, metrics_storage, system_metrics_collector, 
            component_health_checker, performance_metrics_tracker, dashboard_generator):
        """Create a MonitoringAPI instance for testing."""
        metadata = TaskResolverMetadata(
            id="test-monitoring",
            name="Test Monitoring",
            description="Test monitoring service",
            version="1.0.0",
            properties={}
        )
        
        api = MonitoringAPI(
            data_dir=str(tmp_path),
            metadata=metadata,
            host="localhost",
            port=8000
        )
        
        # Replace components with mocks
        api.metrics_storage = metrics_storage
        api.system_metrics_collector = system_metrics_collector
        api.component_health_checker = component_health_checker
        api.performance_metrics_tracker = performance_metrics_tracker
        api.dashboard_generator = dashboard_generator
        
        return api

    @pytest.fixture
    def client(self, api):
        """Create a test client for the FastAPI app."""
        return TestClient(api.app)

    def test_health_check(self, client):
        """Test the health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_get_system_metrics(self, client, metrics_storage):
        """Test the get system metrics endpoint."""
        # Mock the metrics storage
        metrics_storage.get_metrics.return_value = [
            {"timestamp": datetime.now().isoformat(), "cpu": 50, "memory": 1024}
        ]
        
        # Test the endpoint
        response = client.get("/metrics/system")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert "cpu" in data[0]
        assert "memory" in data[0]

    def test_collect_system_metrics(self, client, system_metrics_collector):
        """Test the collect system metrics endpoint."""
        response = client.post("/metrics/system/collect?metrics_type=all")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "task_id" in data

    def test_get_component_health(self, client, metrics_storage):
        """Test the get component health endpoint."""
        # Mock the metrics storage
        metrics_storage.get_component_health.return_value = [
            {"component_id": "test-component", "status": "healthy", "timestamp": datetime.now().isoformat()}
        ]
        
        # Test the endpoint
        response = client.get("/health/components")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["component_id"] == "test-component"
        assert data[0]["status"] == "healthy"

    def test_get_component_health_history(self, client, metrics_storage):
        """Test the get component health history endpoint."""
        # Mock the metrics storage
        metrics_storage.get_component_health_history.return_value = {
            "component_id": "test-component",
            "history": [
                {"status": "healthy", "timestamp": datetime.now().isoformat()}
            ]
        }
        
        # Test the endpoint
        response = client.get("/health/components/test-component")
        assert response.status_code == 200
        data = response.json()
        assert data["component_id"] == "test-component"
        assert len(data["history"]) == 1

    def test_check_component_health(self, client, component_health_checker):
        """Test the check component health endpoint."""
        response = client.post("/health/components/test-component/check")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "task_id" in data

    def test_get_performance_metrics(self, client, metrics_storage):
        """Test the get performance metrics endpoint."""
        # Mock the metrics storage
        metrics_storage.get_performance_metrics.return_value = [
            {
                "component_id": "test-component", 
                "operation": "test-operation", 
                "execution_time_ms": 100,
                "timestamp": datetime.now().isoformat()
            }
        ]
        
        # Test the endpoint
        response = client.get("/metrics/performance")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["component_id"] == "test-component"
        assert data[0]["operation"] == "test-operation"
        assert data[0]["execution_time_ms"] == 100

    def test_record_performance_metric(self, client, performance_metrics_tracker):
        """Test the record performance metric endpoint."""
        response = client.post(
            "/metrics/performance/record?component_id=test-component&operation_name=test-operation&execution_time_ms=100"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "task_id" in data

    def test_list_dashboards(self, client, dashboard_generator):
        """Test the list dashboards endpoint."""
        # Mock the dashboard generator
        dashboard_generator.list_dashboards.return_value = [
            {"id": "test-dashboard", "title": "Test Dashboard", "type": "system"}
        ]
        
        # Test the endpoint
        response = client.get("/dashboards")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "test-dashboard"
        assert data[0]["title"] == "Test Dashboard"
        assert data[0]["type"] == "system"

    def test_generate_dashboard(self, client, dashboard_generator):
        """Test the generate dashboard endpoint."""
        response = client.post("/dashboards/generate?dashboard_type=system&title=Test%20Dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "dashboard_id" in data
        assert "dashboard_file" in data 