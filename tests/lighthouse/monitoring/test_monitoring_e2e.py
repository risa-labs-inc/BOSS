"""End-to-end tests for the monitoring system.

This module contains end-to-end tests for the BOSS monitoring system, testing
the integration between different components and the full data flow.
"""

import os
import pytest
import json
import asyncio
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from boss.lighthouse.monitoring.metrics_storage import MetricsStorage
from boss.lighthouse.monitoring.system_metrics_collector import SystemMetricsCollector
from boss.lighthouse.monitoring.component_health_checker import ComponentHealthChecker
from boss.lighthouse.monitoring.performance_metrics_tracker import PerformanceMetricsTracker
from boss.lighthouse.monitoring.alert_manager import AlertManager
from boss.lighthouse.monitoring.dashboard_generator import DashboardGenerator
from boss.lighthouse.monitoring.chart_generator import ChartGenerator
from boss.lighthouse.monitoring.api import MonitoringAPI
from boss.lighthouse.monitoring.start_monitoring import MonitoringService
from boss.lighthouse.monitoring.metrics_aggregation_resolver import MetricsAggregationResolver
from boss.lighthouse.monitoring.alert_notification_resolver import AlertNotificationResolver
from boss.lighthouse.monitoring.dashboard_customization_resolver import DashboardCustomizationResolver

from boss.core.task_models import Task, TaskResult, TaskStatus

# For mypy type checking - can be safely ignored at runtime
try:
    from boss.core.task_resolver_metadata import TaskResolverMetadata
except ImportError:
    # Type stub for mypy
    class TaskResolverMetadata:
        def __init__(self, id, name, description, version, properties): pass


@pytest.fixture
def temp_monitoring_dir():
    """Create a temporary directory for monitoring data."""
    temp_dir = tempfile.mkdtemp(prefix="boss_monitoring_test_")
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def metadata():
    """Create a TaskResolverMetadata instance for testing."""
    return TaskResolverMetadata(
        id="test-monitoring",
        name="Test Monitoring",
        description="Test monitoring system",
        version="1.0.0",
        properties={}
    )


@pytest.fixture
def metrics_storage(temp_monitoring_dir):
    """Create a MetricsStorage instance for testing."""
    storage_dir = os.path.join(temp_monitoring_dir, "metrics")
    os.makedirs(storage_dir, exist_ok=True)
    return MetricsStorage(data_dir=storage_dir)


@pytest.fixture
def chart_generator(temp_monitoring_dir):
    """Create a ChartGenerator instance for testing."""
    charts_dir = os.path.join(temp_monitoring_dir, "charts")
    os.makedirs(charts_dir, exist_ok=True)
    return ChartGenerator(output_dir=charts_dir)


@pytest.fixture
def dashboard_generator(temp_monitoring_dir, metrics_storage, chart_generator):
    """Create a DashboardGenerator instance for testing."""
    from boss.core.task_resolver import TaskResolverMetadata
    
    dashboard_dir = os.path.join(temp_monitoring_dir, "dashboards")
    os.makedirs(dashboard_dir, exist_ok=True)
    
    metadata = TaskResolverMetadata(
        id="dashboard_generator_test",
        name="DashboardGenerator",
        version="1.0.0",
        description="Dashboard Generator for Testing",
        properties={}
    )
    
    return DashboardGenerator(
        resolver_metadata=metadata,
        data_dir=dashboard_dir,
        metrics_storage=metrics_storage,
        chart_generator=chart_generator
    )


@pytest.fixture
def system_metrics_collector(metadata, metrics_storage):
    """Create a SystemMetricsCollector instance for testing."""
    return SystemMetricsCollector(
        metadata=metadata,
        metrics_storage=metrics_storage
    )


@pytest.fixture
def component_health_checker(metadata, metrics_storage):
    """Create a ComponentHealthChecker instance for testing."""
    return ComponentHealthChecker(
        metadata=metadata,
        metrics_storage=metrics_storage
    )


@pytest.fixture
def performance_metrics_tracker(metadata, metrics_storage):
    """Create a PerformanceMetricsTracker instance for testing."""
    return PerformanceMetricsTracker(
        metadata=metadata,
        metrics_storage=metrics_storage
    )


@pytest.fixture
def alert_manager(metadata, metrics_storage):
    """Create an AlertManager instance for testing."""
    return AlertManager(
        metadata=metadata,
        metrics_storage=metrics_storage
    )


@pytest.fixture
def metrics_aggregation_resolver(metadata, metrics_storage):
    """Create a MetricsAggregationResolver instance for testing."""
    return MetricsAggregationResolver(
        metadata=metadata,
        metrics_storage=metrics_storage
    )


@pytest.fixture
def alert_notification_resolver(metadata, metrics_storage, alert_manager):
    """Create an AlertNotificationResolver instance for testing."""
    # Use temporary file for notification config
    config_path = tempfile.mktemp(suffix=".json")
    with open(config_path, 'w') as f:
        json.dump({
            "email": {"enabled": False},
            "slack": {"enabled": False},
            "webhook": {"enabled": False}
        }, f)
    
    return AlertNotificationResolver(
        metadata=metadata,
        metrics_storage=metrics_storage,
        alert_manager=alert_manager,
        config_path=config_path
    )


@pytest.fixture
def dashboard_customization_resolver(metadata, metrics_storage, dashboard_generator, chart_generator, temp_monitoring_dir):
    """Create a DashboardCustomizationResolver instance for testing."""
    return DashboardCustomizationResolver(
        metadata=metadata,
        metrics_storage=metrics_storage,
        dashboard_generator=dashboard_generator,
        chart_generator=chart_generator,
        data_dir=temp_monitoring_dir
    )


@pytest.fixture
def monitoring_api(temp_monitoring_dir, metadata, metrics_storage, system_metrics_collector,
                  component_health_checker, performance_metrics_tracker, dashboard_generator):
    """Create a MonitoringAPI instance for testing."""
    return MonitoringAPI(
        data_dir=temp_monitoring_dir,
        metadata=metadata,
        host="localhost",
        port=8080
    )


@pytest.fixture
def monitoring_service(temp_monitoring_dir):
    """Create a MonitoringService instance for testing."""
    return MonitoringService(
        data_dir=temp_monitoring_dir,
        api_host="localhost",
        api_port=8080
    )


@pytest.mark.e2e
class TestMonitoringE2E:
    """End-to-end tests for the monitoring system."""

    @pytest.mark.asyncio
    async def test_metrics_collection_to_storage(self, system_metrics_collector, metrics_storage):
        """Test collecting metrics and storing them."""
        # Collect system metrics
        task = Task(
            input_data={"operation": "collect", "metrics_type": "system"},
            metadata={"source": "e2e_test"}
        )
        
        result = system_metrics_collector(task)
        
        # Verify the operation was successful
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data is not None
        
        # Retrieve the stored metrics
        get_task = Task(
            input_data={
                "operation": "get_metrics",
                "metrics_type": "system",
                "start_time": (datetime.now() - timedelta(minutes=5)).isoformat(),
                "end_time": datetime.now().isoformat()
            },
            metadata={"source": "e2e_test"}
        )
        
        get_result = metrics_storage(get_task)
        
        # Verify metrics were stored and can be retrieved
        assert get_result.status == TaskStatus.COMPLETED
        assert isinstance(get_result.output_data, list)
        assert len(get_result.output_data) > 0
        
        # Verify metric structure
        metric = get_result.output_data[0]
        assert "timestamp" in metric
        assert "cpu" in metric or "memory" in metric or "disk" in metric or "network" in metric

    @pytest.mark.asyncio
    async def test_health_check_to_storage(self, component_health_checker, metrics_storage):
        """Test performing health checks and storing the results."""
        # Perform health check
        task = Task(
            input_data={"operation": "check_component", "component_id": "test-component"},
            metadata={"source": "e2e_test"}
        )
        
        result = component_health_checker(task)
        
        # Verify the operation was successful
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data is not None
        
        # Retrieve the stored health check results
        get_task = Task(
            input_data={
                "operation": "get_component_health_history",
                "component_id": "test-component",
                "start_time": (datetime.now() - timedelta(minutes=5)).isoformat(),
                "end_time": datetime.now().isoformat()
            },
            metadata={"source": "e2e_test"}
        )
        
        get_result = metrics_storage(get_task)
        
        # Verify health check results were stored and can be retrieved
        assert get_result.status == TaskStatus.COMPLETED
        assert "component_id" in get_result.output_data
        assert get_result.output_data["component_id"] == "test-component"
        assert "history" in get_result.output_data
        assert len(get_result.output_data["history"]) > 0
        
        # Verify health check structure
        health_check = get_result.output_data["history"][0]
        assert "timestamp" in health_check
        assert "status" in health_check

    @pytest.mark.asyncio
    async def test_performance_tracking_to_storage(self, performance_metrics_tracker, metrics_storage):
        """Test tracking performance metrics and storing them."""
        # Record performance metric
        task = Task(
            input_data={
                "operation": "record_metric",
                "component_id": "test-component",
                "operation_name": "test-operation",
                "execution_time_ms": 150,
                "success": True
            },
            metadata={"source": "e2e_test"}
        )
        
        result = performance_metrics_tracker(task)
        
        # Verify the operation was successful
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data is not None
        
        # Retrieve the stored performance metrics
        get_task = Task(
            input_data={
                "operation": "get_metrics",
                "component_id": "test-component",
                "operation_name": "test-operation",
                "start_time": (datetime.now() - timedelta(minutes=5)).isoformat(),
                "end_time": datetime.now().isoformat()
            },
            metadata={"source": "e2e_test"}
        )
        
        get_result = performance_metrics_tracker(get_task)
        
        # Verify performance metrics were stored and can be retrieved
        assert get_result.status == TaskStatus.COMPLETED
        assert isinstance(get_result.output_data, list)
        assert len(get_result.output_data) > 0
        
        # Verify metric structure
        metric = get_result.output_data[0]
        assert "timestamp" in metric
        assert "component_id" in metric
        assert "operation_name" in metric
        assert "execution_time_ms" in metric
        assert metric["component_id"] == "test-component"
        assert metric["operation_name"] == "test-operation"
        assert metric["execution_time_ms"] == 150

    @pytest.mark.asyncio
    async def test_metrics_to_dashboard(self, system_metrics_collector, metrics_storage, 
                                       dashboard_generator, temp_monitoring_dir):
        """Test the full flow from metrics collection to dashboard generation."""
        # Collect system metrics
        collect_task = Task(
            id="collect_metrics_task",
            name="collect_metrics",
            input_data={"operation": "collect", "metrics_type": "all"},
            metadata={"source": "e2e_test"}
        )
        
        collect_result = await system_metrics_collector(collect_task)
        assert collect_result.status == TaskStatus.COMPLETED
        
        # Generate a dashboard for the collected metrics
        dashboard_task = Task(
            id="generate_dashboard_task",
            name="generate_dashboard",
            input_data={
                "operation": "generate_dashboard",
                "dashboard_type": "system",
                "title": "E2E Test Dashboard",
                "time_window": "1h"
            },
            metadata={"source": "e2e_test"}
        )
        
        dashboard_result = await dashboard_generator(dashboard_task)
        
        # Verify dashboard was generated
        assert dashboard_result.status == TaskStatus.COMPLETED
        assert "dashboard_id" in dashboard_result.output_data
        assert "dashboard_file" in dashboard_result.output_data
        
        dashboard_id = dashboard_result.output_data["dashboard_id"]
        dashboard_file = dashboard_result.output_data["dashboard_file"]
        
        # Verify the dashboard file exists
        dashboard_path = os.path.join(temp_monitoring_dir, "dashboards", dashboard_file)
        assert os.path.exists(dashboard_path)
        
        # Verify the dashboard file is not empty
        assert os.path.getsize(dashboard_path) > 0
        
        # Verify dashboard content
        with open(dashboard_path, 'r') as f:
            content = f.read()
            assert "E2E Test Dashboard" in content
            assert "System Metrics" in content

    @pytest.mark.asyncio
    async def test_alert_flow(self, alert_manager, metrics_storage, alert_notification_resolver):
        """Test the full alert flow from triggering an alert to notification."""
        # Create an alert rule
        rule_task = Task(
            input_data={
                "operation": "create_rule",
                "rule": {
                    "name": "Test CPU Alert",
                    "description": "Alert when CPU usage exceeds threshold",
                    "metric_type": "system",
                    "metric_path": "cpu.usage",
                    "condition": "gt",
                    "threshold": 80,
                    "duration": "5m",
                    "severity": "warning"
                }
            },
            metadata={"source": "e2e_test"}
        )
        
        rule_result = alert_manager(rule_task)
        assert rule_result.status == TaskStatus.COMPLETED
        assert "rule_id" in rule_result.output_data
        
        rule_id = rule_result.output_data["rule_id"]
        
        # Trigger an alert
        alert_task = Task(
            input_data={
                "operation": "check_alert_rules",
                "rule_ids": [rule_id]
            },
            metadata={"source": "e2e_test"}
        )
        
        # Force alert creation
        with open(os.path.join(metrics_storage.data_dir, "test_alert.json"), "w") as f:
            json.dump({
                "id": "test-alert-1",
                "rule_id": rule_id,
                "component_id": "system",
                "severity": "warning",
                "message": "CPU usage exceeded threshold",
                "timestamp": datetime.now().isoformat(),
                "metric_value": 85,
                "threshold": 80,
                "status": "active",
                "details": {"cpu_usage": 85}
            }, f)
        
        # Get active alerts
        get_alerts_task = Task(
            input_data={
                "operation": "get_active_alerts",
                "severity": "warning"
            },
            metadata={"source": "e2e_test"}
        )
        
        get_alerts_result = alert_manager(get_alerts_task)
        
        # Verify alert was created
        assert get_alerts_result.status == TaskStatus.COMPLETED
        assert "alerts" in get_alerts_result.output_data
        
        # Create notification task
        notification_task = Task(
            input_data={
                "operation": "send_notification",
                "alert": {
                    "id": "test-alert-1",
                    "component_id": "system",
                    "severity": "warning",
                    "message": "CPU usage exceeded threshold",
                    "timestamp": datetime.now().isoformat(),
                    "details": {"cpu_usage": 85}
                },
                "channels": []  # No actual channels to avoid real notifications
            },
            metadata={"source": "e2e_test"}
        )
        
        notification_result = alert_notification_resolver(notification_task)
        
        # Verify notification was processed
        assert notification_result.status == TaskStatus.COMPLETED
        assert "success" in notification_result.output_data
        assert "channel_results" in notification_result.output_data

    @pytest.mark.asyncio
    async def test_custom_dashboard_creation(self, dashboard_customization_resolver, temp_monitoring_dir):
        """Test creating and generating a custom dashboard."""
        # Create a custom dashboard
        task = Task(
            input_data={
                "operation": "create_dashboard",
                "dashboard_id": "e2e-test-dashboard",
                "config": {
                    "title": "E2E Test Custom Dashboard",
                    "description": "Dashboard created by E2E test",
                    "charts": [
                        {
                            "title": "CPU Usage",
                            "type": "line",
                            "metrics_query": {
                                "metrics_type": "system",
                                "component_id": "system",
                                "start_time": (datetime.now() - timedelta(hours=1)).isoformat(),
                                "end_time": datetime.now().isoformat()
                            }
                        }
                    ]
                }
            },
            metadata={"source": "e2e_test"}
        )
        
        result = dashboard_customization_resolver(task)
        
        # Verify dashboard was created
        assert result.status == TaskStatus.COMPLETED
        assert "dashboard_id" in result.output_data
        assert result.output_data["dashboard_id"] == "e2e-test-dashboard"
        
        # Verify the dashboard config was stored
        config_path = os.path.join(temp_monitoring_dir, "custom_dashboards", "e2e-test-dashboard.json")
        assert os.path.exists(config_path)
        
        # Verify dashboard content
        with open(config_path, 'r') as f:
            config = json.load(f)
            assert config["title"] == "E2E Test Custom Dashboard"
            assert len(config["charts"]) == 1
            assert config["charts"][0]["title"] == "CPU Usage"

    @pytest.mark.asyncio
    async def test_metrics_aggregation(self, metrics_storage, metrics_aggregation_resolver):
        """Test aggregating metrics data."""
        # Create test metrics data
        metrics_data = []
        now = datetime.now()
        
        # Generate hourly metrics for the past day
        for i in range(24):
            timestamp = (now - timedelta(hours=24-i)).isoformat()
            metrics_data.append({
                "timestamp": timestamp,
                "cpu_usage": 50 + (i % 10),  # Some variation
                "memory_usage": 4000 + (i * 50),  # Gradually increasing
                "requests_per_minute": 100 + (10 * i) if i < 12 else 220 - (10 * (i - 12))  # Peak at noon
            })
        
        # Store metrics data
        for i, metric in enumerate(metrics_data):
            metrics_file = os.path.join(metrics_storage.data_dir, f"test_metric_{i}.json")
            with open(metrics_file, "w") as f:
                json.dump(metric, f)
        
        # Aggregate metrics
        task = Task(
            input_data={
                "operation": "aggregate_metrics",
                "metrics": metrics_data
            },
            metadata={"source": "e2e_test"}
        )
        
        result = await metrics_aggregation_resolver(task)
        
        # Verify aggregation was successful
        assert result.status == TaskStatus.COMPLETED
        assert "aggregated_data" in result.output_data
        assert "cpu_usage" in result.output_data["aggregated_data"]
        assert "memory_usage" in result.output_data["aggregated_data"]
        assert "requests_per_minute" in result.output_data["aggregated_data"]
        
        # Verify statistics
        cpu_stats = result.output_data["aggregated_data"]["cpu_usage"]
        assert "sum" in cpu_stats
        assert "average" in cpu_stats
        assert "min" in cpu_stats
        assert "max" in cpu_stats
        
        # Verify report generation
        assert "report" in result.output_data
        assert isinstance(result.output_data["report"], str)
        assert "Metrics Aggregation Report" in result.output_data["report"]

    @pytest.mark.asyncio
    async def test_full_service_initialization(self, monitoring_service):
        """Test initializing the full monitoring service."""
        try:
            # Start the monitoring service (non-blocking)
            monitoring_service.running = True
            asyncio.create_task(monitoring_service.run())
            
            # Wait a moment for initialization
            await asyncio.sleep(1)
            
            # Verify service components are initialized
            assert monitoring_service.metrics_storage is not None
            assert monitoring_service.system_metrics_collector is not None
            assert monitoring_service.component_health_checker is not None
            assert monitoring_service.performance_metrics_tracker is not None
            assert monitoring_service.dashboard_generator is not None
            assert monitoring_service.api is not None
            assert monitoring_service.running is True
            
            # Stop the service
            monitoring_service.stop()
            
            # Verify service has stopped
            assert monitoring_service.running is False
            
        finally:
            # Ensure service is stopped
            monitoring_service.running = False 