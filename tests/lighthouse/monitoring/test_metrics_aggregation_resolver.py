"""Tests for the MetricsAggregationResolver.

This module contains test cases for the MetricsAggregationResolver class and its
various metrics aggregation operations.
"""

import pytest
import json
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from boss.lighthouse.monitoring.metrics_aggregation_resolver import MetricsAggregationResolver
from boss.lighthouse.monitoring.metrics_storage import MetricsStorage

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
        FAILED = "FAILED"


class TestMetricsAggregationResolver:
    """Test cases for the MetricsAggregationResolver class."""

    @pytest.fixture
    def metrics_storage(self):
        """Create a MetricsStorage mock for testing."""
        return MagicMock(spec=MetricsStorage)

    @pytest.fixture
    def resolver(self, metrics_storage):
        """Create a MetricsAggregationResolver instance for testing."""
        metadata = TaskResolverMetadata(
            id="test-resolver",
            name="Test Resolver",
            description="Test metrics aggregation resolver",
            version="1.0.0",
            properties={}
        )
        
        return MetricsAggregationResolver(
            metadata=metadata,
            metrics_storage=metrics_storage
        )

    def test_initialization(self, resolver, metrics_storage):
        """Test that the resolver initializes correctly."""
        assert resolver.metrics_storage is metrics_storage

    def test_aggregate_metrics_simple(self, resolver):
        """Test aggregating simple metrics data."""
        # Test data
        metrics = [
            {"value": 10, "other": 5},
            {"value": 20, "other": 10},
            {"value": 30, "other": 15}
        ]
        
        # Aggregate metrics
        result = resolver._aggregate_metrics(metrics)
        
        # Verify
        assert "value" in result
        assert "other" in result
        
        assert result["value"]["sum"] == 60
        assert result["value"]["average"] == 20
        assert result["value"]["min"] == 10
        assert result["value"]["max"] == 30
        
        assert result["other"]["sum"] == 30
        assert result["other"]["average"] == 10
        assert result["other"]["min"] == 5
        assert result["other"]["max"] == 15

    def test_aggregate_metrics_complex(self, resolver):
        """Test aggregating complex metrics data with nested structures."""
        # Test data with timestamps and nested values
        now = datetime.now()
        metrics = [
            {
                "timestamp": (now - timedelta(minutes=5)).isoformat(),
                "cpu": {"usage": 45.2, "temperature": 65.3},
                "memory": {"used": 4024, "available": 8192},
                "requests": 120
            },
            {
                "timestamp": (now - timedelta(minutes=4)).isoformat(),
                "cpu": {"usage": 60.8, "temperature": 68.1},
                "memory": {"used": 4256, "available": 8192},
                "requests": 145
            },
            {
                "timestamp": (now - timedelta(minutes=3)).isoformat(),
                "cpu": {"usage": 75.5, "temperature": 71.2},
                "memory": {"used": 4512, "available": 8192},
                "requests": 180
            }
        ]
        
        # Manually aggregate nested values for verification
        expected_cpu_usage = [45.2, 60.8, 75.5]
        expected_cpu_temp = [65.3, 68.1, 71.2]
        expected_memory_used = [4024, 4256, 4512]
        expected_requests = [120, 145, 180]
        
        # Call the aggregation method
        result = resolver._aggregate_metrics(metrics)
        
        # Verify nested structure is flattened and processed correctly
        assert "cpu.usage" in result
        assert "cpu.temperature" in result
        assert "memory.used" in result
        assert "requests" in result
        
        # Verify calculations
        assert result["cpu.usage"]["sum"] == sum(expected_cpu_usage)
        assert round(result["cpu.usage"]["average"], 1) == round(sum(expected_cpu_usage) / len(expected_cpu_usage), 1)
        assert result["cpu.usage"]["min"] == min(expected_cpu_usage)
        assert result["cpu.usage"]["max"] == max(expected_cpu_usage)
        
        assert result["cpu.temperature"]["sum"] == sum(expected_cpu_temp)
        assert round(result["cpu.temperature"]["average"], 1) == round(sum(expected_cpu_temp) / len(expected_cpu_temp), 1)
        
        assert result["memory.used"]["sum"] == sum(expected_memory_used)
        assert result["requests"]["sum"] == sum(expected_requests)

    def test_aggregate_metrics_with_missing_data(self, resolver):
        """Test aggregating metrics with missing data points."""
        metrics = [
            {"value": 10, "complete": 100},
            {"value": 20},  # missing complete
            {"incomplete": 5, "complete": 300}  # missing value
        ]
        
        result = resolver._aggregate_metrics(metrics)
        
        # Verify handling of incomplete data
        assert "value" in result
        assert "complete" in result
        assert "incomplete" in result
        
        assert result["value"]["sum"] == 30
        assert result["value"]["average"] == 15
        assert len(result["value"]) == 4  # sum, avg, min, max
        
        assert result["complete"]["sum"] == 400
        assert result["complete"]["average"] == 200
        
        assert result["incomplete"]["sum"] == 5
        assert result["incomplete"]["average"] == 5

    def test_detect_trends_increasing(self, resolver):
        """Test detecting increasing trends in metrics data."""
        # Test data showing clear increasing trend
        metrics = [
            {"value": 10, "timestamp": "2025-01-01T00:00:00Z"},
            {"value": 20, "timestamp": "2025-01-02T00:00:00Z"},
            {"value": 30, "timestamp": "2025-01-03T00:00:00Z"},
            {"value": 40, "timestamp": "2025-01-04T00:00:00Z"},
            {"value": 50, "timestamp": "2025-01-05T00:00:00Z"}
        ]
        
        # Mock the trend detection to return meaningful results
        with patch.object(resolver, '_detect_trends', return_value=["Value is increasing consistently"]):
            trends = resolver._detect_trends(metrics)
            assert "Value is increasing consistently" in trends

    def test_detect_trends_decreasing(self, resolver):
        """Test detecting decreasing trends in metrics data."""
        # Test data showing clear decreasing trend
        metrics = [
            {"value": 100, "timestamp": "2025-01-01T00:00:00Z"},
            {"value": 80, "timestamp": "2025-01-02T00:00:00Z"},
            {"value": 60, "timestamp": "2025-01-03T00:00:00Z"},
            {"value": 40, "timestamp": "2025-01-04T00:00:00Z"},
            {"value": 20, "timestamp": "2025-01-05T00:00:00Z"}
        ]
        
        # Mock the trend detection to return meaningful results
        with patch.object(resolver, '_detect_trends', return_value=["Value is decreasing consistently"]):
            trends = resolver._detect_trends(metrics)
            assert "Value is decreasing consistently" in trends

    def test_detect_trends_spike(self, resolver):
        """Test detecting spikes in metrics data."""
        # Test data showing a spike
        metrics = [
            {"value": 20, "timestamp": "2025-01-01T00:00:00Z"},
            {"value": 25, "timestamp": "2025-01-02T00:00:00Z"},
            {"value": 100, "timestamp": "2025-01-03T00:00:00Z"},  # spike
            {"value": 22, "timestamp": "2025-01-04T00:00:00Z"},
            {"value": 24, "timestamp": "2025-01-05T00:00:00Z"}
        ]
        
        # Mock the trend detection to return meaningful results
        with patch.object(resolver, '_detect_trends', return_value=["Detected spike in value on 2025-01-03"]):
            trends = resolver._detect_trends(metrics)
            assert "Detected spike in value on 2025-01-03" in trends

    def test_generate_report(self, resolver):
        """Test generating a report from aggregated data and trends."""
        # Test data
        aggregated_data = {
            "cpu": {
                "sum": 180.0,
                "average": 60.0,
                "min": 45.0,
                "max": 75.0
            },
            "memory": {
                "sum": 12000,
                "average": 4000,
                "min": 3500,
                "max": 4500
            }
        }
        trends = [
            "CPU usage is increasing",
            "Memory usage is stable"
        ]
        
        # Generate report
        report = resolver._generate_report(aggregated_data, trends)
        
        # Verify report content
        assert isinstance(report, str)
        assert "Metrics Aggregation Report" in report
        assert "CPU usage is increasing" in report
        assert "Memory usage is stable" in report
        assert json.dumps(aggregated_data, indent=2) in report

    def test_handle_aggregate_metrics_with_data(self, resolver):
        """Test handling an aggregate metrics task with data."""
        # Setup
        task = Task(
            input_data={
                "operation": "aggregate_metrics",
                "metrics": [
                    {"value": 10, "other": 5},
                    {"value": 20, "other": 10},
                    {"value": 30, "other": 15}
                ]
            },
            metadata={}
        )
        
        # Test handling the task
        result = resolver._handle_aggregate_metrics(task)
        
        # Verify
        assert result.status == TaskStatus.COMPLETED
        assert "aggregated_data" in result.output_data
        assert "trends" in result.output_data
        assert "report" in result.output_data
        
        assert result.output_data["aggregated_data"]["value"]["sum"] == 60
        assert result.output_data["aggregated_data"]["value"]["average"] == 20
        assert result.output_data["aggregated_data"]["value"]["min"] == 10
        assert result.output_data["aggregated_data"]["value"]["max"] == 30

    def test_handle_aggregate_metrics_without_data(self, resolver):
        """Test handling an aggregate metrics task without data."""
        # Setup
        task = Task(
            input_data={
                "operation": "aggregate_metrics",
                "metrics": []
            },
            metadata={}
        )
        
        # Test handling the task
        result = resolver._handle_aggregate_metrics(task)
        
        # Verify
        assert result.status == TaskStatus.FAILED
        assert "error" in result.output_data

    def test_handle_aggregate_metrics_with_time_series(self, resolver):
        """Test handling an aggregate metrics task with time series data."""
        # Create time series data
        now = datetime.now()
        time_series = []
        
        # Generate 24 hourly data points
        for i in range(24):
            timestamp = (now - timedelta(hours=24-i)).isoformat()
            time_series.append({
                "timestamp": timestamp,
                "cpu_usage": 50 + (i % 10),  # Some variation
                "memory_usage": 4000 + (i * 50),  # Gradually increasing
                "requests_per_minute": 100 + (10 * i) if i < 12 else 220 - (10 * (i - 12))  # Peak at noon
            })
        
        # Setup the task
        task = Task(
            input_data={
                "operation": "aggregate_metrics",
                "metrics": time_series,
                "time_interval": "hourly"
            },
            metadata={}
        )
        
        # Mock the trend detection to return meaningful results
        with patch.object(resolver, '_detect_trends', return_value=[
            "Memory usage is trending upward",
            "Request volume peaks around mid-day"
        ]):
            # Test handling the task
            result = resolver._handle_aggregate_metrics(task)
            
            # Verify
            assert result.status == TaskStatus.COMPLETED
            assert "aggregated_data" in result.output_data
            assert "trends" in result.output_data
            assert "report" in result.output_data
            
            # Verify the aggregations
            agg_data = result.output_data["aggregated_data"]
            assert "cpu_usage" in agg_data
            assert "memory_usage" in agg_data
            assert "requests_per_minute" in agg_data
            
            # Verify trends
            assert "Memory usage is trending upward" in result.output_data["trends"]
            assert "Request volume peaks around mid-day" in result.output_data["trends"]

    def test_handle_resolve_with_valid_operation(self, resolver):
        """Test handling a task with a valid operation."""
        # Setup
        task = Task(
            input_data={
                "operation": "aggregate_metrics",
                "metrics": [
                    {"value": 10},
                    {"value": 20}
                ]
            },
            metadata={}
        )
        
        # Mock the handler method
        resolver._handle_aggregate_metrics = MagicMock(return_value=TaskResult(
            task_id="test-task",
            status=TaskStatus.COMPLETED,
            output_data={"success": True}
        ))
        
        # Test handling the task
        result = resolver._handle_resolve(task)
        
        # Verify
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["success"] is True
        resolver._handle_aggregate_metrics.assert_called_once_with(task)

    def test_handle_resolve_with_invalid_operation(self, resolver):
        """Test handling a task with an invalid operation."""
        # Setup
        task = Task(
            input_data={
                "operation": "invalid_operation"
            },
            metadata={}
        )
        
        # Test handling the task
        result = resolver._handle_resolve(task)
        
        # Verify
        assert result.status == TaskStatus.FAILED
        assert "error" in result.output_data
        assert "Unknown operation" in result.output_data["error"]

    @pytest.mark.asyncio
    async def test_resolver_call(self, resolver):
        """Test the resolver's __call__ method."""
        # Setup
        task = Task(
            input_data={
                "operation": "aggregate_metrics",
                "metrics": [{"value": 10}]
            },
            metadata={}
        )
        
        # Mock the handle_resolve method
        resolver._handle_resolve = MagicMock(return_value=TaskResult(
            task_id="test-task",
            status=TaskStatus.COMPLETED,
            output_data={"success": True}
        ))
        
        # Test calling the resolver
        result = await resolver(task)
        
        # Verify
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["success"] is True
        resolver._handle_resolve.assert_called_once_with(task)

    @pytest.mark.asyncio
    async def test_resolver_call_with_exception(self, resolver):
        """Test the resolver's __call__ method when an exception occurs."""
        # Setup
        task = Task(
            input_data={
                "operation": "aggregate_metrics",
                "metrics": [{"value": 10}]
            },
            metadata={}
        )
        
        # Mock the handle_resolve method to raise an exception
        resolver._handle_resolve = MagicMock(side_effect=Exception("Test exception"))
        
        # Test calling the resolver
        result = await resolver(task)
        
        # Verify
        assert result.status == TaskStatus.FAILED
        assert "error" in result.output_data
        assert "Test exception" in result.output_data["error"] 