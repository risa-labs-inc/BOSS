"""Tests for the MonitoringService.

This module contains test cases for the MonitoringService class which manages
all monitoring components and the API server.
"""

import os
import pytest
import asyncio
import signal
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta

from boss.lighthouse.monitoring.start_monitoring import MonitoringService
from boss.lighthouse.monitoring.metrics_storage import MetricsStorage
from boss.lighthouse.monitoring.system_metrics_collector import SystemMetricsCollector
from boss.lighthouse.monitoring.component_health_checker import ComponentHealthChecker
from boss.lighthouse.monitoring.performance_metrics_tracker import PerformanceMetricsTracker
from boss.lighthouse.monitoring.dashboard_generator import DashboardGenerator
from boss.lighthouse.monitoring.api import MonitoringAPI
from boss.core.task_models import Task, TaskResult, TaskStatus


class TestMonitoringService:
    """Test cases for the MonitoringService class."""

    @pytest.fixture
    def data_dir(self, tmp_path):
        """Create a temporary data directory for testing."""
        data_dir = os.path.join(tmp_path, "monitoring_data")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir

    @pytest.fixture
    def metrics_storage(self):
        """Create a metrics storage mock."""
        return MagicMock(spec=MetricsStorage)

    @pytest.fixture
    def system_metrics_collector(self):
        """Create a system metrics collector mock."""
        collector = MagicMock(spec=SystemMetricsCollector)
        collector.return_value = TaskResult(
            task_id="test-task",
            status=TaskStatus.COMPLETED,
            output_data={"success": True}
        )
        return collector

    @pytest.fixture
    def component_health_checker(self):
        """Create a component health checker mock."""
        checker = MagicMock(spec=ComponentHealthChecker)
        checker.return_value = TaskResult(
            task_id="test-task",
            status=TaskStatus.COMPLETED,
            output_data={"success": True}
        )
        return checker

    @pytest.fixture
    def performance_metrics_tracker(self):
        """Create a performance metrics tracker mock."""
        tracker = MagicMock(spec=PerformanceMetricsTracker)
        tracker.return_value = TaskResult(
            task_id="test-task",
            status=TaskStatus.COMPLETED,
            output_data={"success": True}
        )
        return tracker

    @pytest.fixture
    def dashboard_generator(self):
        """Create a dashboard generator mock."""
        generator = MagicMock(spec=DashboardGenerator)
        generator.return_value = TaskResult(
            task_id="test-task",
            status=TaskStatus.COMPLETED,
            output_data={"dashboard_file": "test.html"}
        )
        return generator

    @pytest.fixture
    def api(self):
        """Create a monitoring API mock."""
        api_mock = MagicMock(spec=MonitoringAPI)
        api_mock.start = MagicMock()
        api_mock.start_async = AsyncMock()
        return api_mock

    @pytest.fixture
    def service(self, data_dir):
        """Create a MonitoringService instance for testing."""
        with patch("boss.lighthouse.monitoring.start_monitoring.MetricsStorage"), \
             patch("boss.lighthouse.monitoring.start_monitoring.SystemMetricsCollector"), \
             patch("boss.lighthouse.monitoring.start_monitoring.ComponentHealthChecker"), \
             patch("boss.lighthouse.monitoring.start_monitoring.PerformanceMetricsTracker"), \
             patch("boss.lighthouse.monitoring.start_monitoring.DashboardGenerator"), \
             patch("boss.lighthouse.monitoring.start_monitoring.MonitoringAPI"):
            service = MonitoringService(
                data_dir=data_dir,
                api_host="localhost",
                api_port=8080
            )
            return service

    def test_initialization(self, service, data_dir):
        """Test that the service initializes correctly."""
        assert service.data_dir == data_dir
        assert service.api_host == "localhost"
        assert service.api_port == 8080
        assert service.running is False
        
        assert hasattr(service, "metrics_storage")
        assert hasattr(service, "system_metrics_collector")
        assert hasattr(service, "component_health_checker")
        assert hasattr(service, "performance_metrics_tracker")
        assert hasattr(service, "dashboard_generator")
        assert hasattr(service, "api")

    def test_signal_handler(self, service):
        """Test the signal handler."""
        service.running = True
        service._signal_handler(signal.SIGINT, None)
        assert service.running is False

    @patch("boss.lighthouse.monitoring.start_monitoring.logger")
    def test_setup_signal_handlers(self, mock_logger, service):
        """Test setting up signal handlers."""
        with patch("signal.signal") as mock_signal:
            service._setup_signal_handlers()
            assert mock_signal.call_count == 2  # SIGINT and SIGTERM
            mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_metrics_collection(self, service):
        """Test scheduling metrics collection."""
        # Mock the system_metrics_collector and asyncio.sleep
        service.system_metrics_collector = MagicMock()
        service.system_metrics_collector.return_value = TaskResult(
            task_id="test-task",
            status=TaskStatus.COMPLETED,
            output_data={"success": True}
        )
        
        with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
            # Set running to True then False after one iteration
            service.running = True
            
            # Create a task that runs the method for a short time
            task = asyncio.create_task(service.schedule_metrics_collection())
            await asyncio.sleep(0.1)  # Give the task a chance to start
            service.running = False    # Stop the loop
            await task                 # Wait for task to complete
            
            # Verify the method was called
            service.system_metrics_collector.assert_called_once()
            assert "operation" in service.system_metrics_collector.call_args[0][0].input_data
            assert service.system_metrics_collector.call_args[0][0].input_data["operation"] == "collect"
            mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_health_checks(self, service):
        """Test scheduling health checks."""
        # Mock the component_health_checker and asyncio.sleep
        service.component_health_checker = MagicMock()
        service.component_health_checker.return_value = TaskResult(
            task_id="test-task",
            status=TaskStatus.COMPLETED,
            output_data={"success": True}
        )
        
        with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
            # Set running to True then False after one iteration
            service.running = True
            
            # Create a task that runs the method for a short time
            task = asyncio.create_task(service.schedule_health_checks())
            await asyncio.sleep(0.1)  # Give the task a chance to start
            service.running = False    # Stop the loop
            await task                 # Wait for task to complete
            
            # Verify the method was called
            service.component_health_checker.assert_called_once()
            assert "operation" in service.component_health_checker.call_args[0][0].input_data
            assert service.component_health_checker.call_args[0][0].input_data["operation"] == "check_all"
            mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_dashboard_generation(self, service):
        """Test scheduling dashboard generation."""
        # Mock the dashboard_generator and asyncio.sleep
        service.dashboard_generator = MagicMock()
        service.dashboard_generator.return_value = TaskResult(
            task_id="test-task",
            status=TaskStatus.COMPLETED,
            output_data={"success": True}
        )
        
        with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
            # Set running to True then False after one iteration
            service.running = True
            
            # Create a task that runs the method for a short time
            task = asyncio.create_task(service.schedule_dashboard_generation())
            await asyncio.sleep(0.1)  # Give the task a chance to start
            service.running = False    # Stop the loop
            await task                 # Wait for task to complete
            
            # Verify the method was called
            service.dashboard_generator.assert_called_once()
            assert "operation" in service.dashboard_generator.call_args[0][0].input_data
            assert service.dashboard_generator.call_args[0][0].input_data["operation"] == "generate_dashboard"
            mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_maintenance(self, service):
        """Test scheduling maintenance tasks."""
        # Mock the asyncio.sleep and metrics_storage methods
        service.metrics_storage = MagicMock()
        service.metrics_storage.clean_old_metrics = MagicMock()
        
        with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
            # Set running to True then False after one iteration
            service.running = True
            
            # Create a task that runs the method for a short time
            task = asyncio.create_task(service.schedule_maintenance())
            await asyncio.sleep(0.1)  # Give the task a chance to start
            service.running = False    # Stop the loop
            await task                 # Wait for task to complete
            
            # Verify the method was called
            service.metrics_storage.clean_old_metrics.assert_called_once()
            mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_run(self, service):
        """Test the run method."""
        # Mock the dependent methods
        service.api = MagicMock()
        service.api.start_async = AsyncMock()
        service.schedule_metrics_collection = AsyncMock()
        service.schedule_health_checks = AsyncMock()
        service.schedule_dashboard_generation = AsyncMock()
        service.schedule_maintenance = AsyncMock()
        
        # Set running to True initially and then False to stop
        service.running = True
        
        # Create a task to run the method
        task = asyncio.create_task(service.run())
        await asyncio.sleep(0.1)  # Give the task time to start
        service.running = False    # Signal the run method to stop
        await task                 # Wait for task to complete
        
        # Verify the API was started and tasks were scheduled
        service.api.start_async.assert_called_once()
        service.schedule_metrics_collection.assert_called_once()
        service.schedule_health_checks.assert_called_once()
        service.schedule_dashboard_generation.assert_called_once()
        service.schedule_maintenance.assert_called_once()

    @patch("boss.lighthouse.monitoring.start_monitoring.asyncio.run")
    def test_start(self, mock_asyncio_run, service):
        """Test starting the service."""
        service.run = AsyncMock()
        service.start()
        mock_asyncio_run.assert_called_once_with(service.run())

    def test_stop(self, service):
        """Test stopping the service."""
        service.running = True
        service.stop()
        assert service.running is False 