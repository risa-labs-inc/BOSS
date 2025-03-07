"""Performance metrics tracker for the BOSS system.

This module provides a component for tracking performance metrics of various 
system components and operations. It extends the BaseMonitoring class with
performance tracking capabilities.
"""

import os
import time
import statistics
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union, cast

from boss.core.task_models import Task, TaskResult
from boss.core.task_resolver import TaskResolverMetadata
from boss.core.task_status import TaskStatus
from boss.lighthouse.monitoring.base_monitoring import BaseMonitoring


class PerformanceMetricsTracker(BaseMonitoring):
    """Component for tracking performance metrics.
    
    This component tracks various performance metrics including:
    - Response times
    - Throughput
    - Error rates
    - Resource utilization
    
    Attributes:
        retention_days: Number of days to retain performance data
        performance_thresholds: Dictionary of thresholds for performance metrics
    """
    
    def __init__(self, metadata: TaskResolverMetadata) -> None:
        """Initialize the PerformanceMetricsTracker.
        
        Args:
            metadata: Resolver metadata
        """
        super().__init__(metadata, "performance_metrics")
        
        # Load configuration
        default_config = {
            "retention_days": 30,
            "performance_thresholds": {
                "response_time_ms": 500,  # milliseconds
                "error_rate_percent": 5.0,  # percentage
                "throughput_min": 10  # operations per second
            }
        }
        config = self.load_config(default_config)
        
        self.retention_days = config["retention_days"]
        self.performance_thresholds = config["performance_thresholds"]
    
    async def resolve(self, task: Task) -> TaskResult:
        """Resolve the task based on its operation.
        
        Args:
            task: The task to resolve
            
        Returns:
            The task result with the outcome of the operation
        """
        try:
            if not isinstance(task.input_data, dict):
                return self._create_error_result(task, "Input data must be a dictionary")
            
            operation = task.input_data.get("operation")
            if not operation:
                return self._create_error_result(task, "Missing 'operation' field in input data")
            
            # Handle different operations
            if operation == "record_performance_metric":
                return await self._handle_record_performance_metric(task)
            elif operation == "get_performance_metrics":
                return await self._handle_get_performance_metrics(task)
            elif operation == "analyze_performance_trend":
                return await self._handle_analyze_performance_trend(task)
            elif operation == "clear_old_metrics":
                return await self._handle_clear_old_metrics(task)
            elif operation == "health_check":
                return await self._handle_health_check(task)
            else:
                return self._create_error_result(task, f"Unsupported operation: {operation}")
        
        except Exception as e:
            self.logger.error(f"Error in PerformanceMetricsTracker: {e}")
            return self._create_error_result(task, f"Internal error: {str(e)}")
    
    async def _handle_record_performance_metric(self, task: Task) -> TaskResult:
        """Record a performance metric.
        
        Args:
            task: The task containing the performance metric
            
        Returns:
            A TaskResult containing the result of the operation
        """
        try:
            # Get required parameters
            component_id = task.input_data.get("component_id")
            if not component_id:
                return self._create_error_result(task, "Missing 'component_id' in input data")
            
            metric_type = task.input_data.get("metric_type")
            if not metric_type:
                return self._create_error_result(task, "Missing 'metric_type' in input data")
            
            value = task.input_data.get("value")
            if value is None:
                return self._create_error_result(task, "Missing 'value' in input data")
            
            # Get optional parameters
            operation_id = task.input_data.get("operation_id")
            context = task.input_data.get("context", {})
            
            # Create the performance metric
            metric: Dict[str, Any] = {
                "component_id": component_id,
                "metric_type": metric_type,
                "value": value,
                "timestamp": datetime.now().isoformat()
            }
            
            if operation_id:
                metric["operation_id"] = operation_id
                
            if context:
                metric["context"] = context
            
            # Check against thresholds and determine status
            threshold = self.performance_thresholds.get(metric_type)
            if threshold is not None:
                # Higher is worse for these metrics
                if metric_type in ["response_time_ms", "error_rate_percent"]:
                    metric["status"] = "ok" if value <= threshold else "warning"
                # Lower is worse for these metrics
                elif metric_type in ["throughput"]:
                    metric["status"] = "ok" if value >= threshold else "warning"
                else:
                    metric["status"] = "ok"  # Default status
            else:
                metric["status"] = "ok"  # Default status
            
            # Store the metric
            await self._store_performance_metric(component_id, metric_type, metric)
            
            return self._create_success_result(task, {
                "message": "Performance metric recorded successfully",
                "metric": metric
            })
            
        except Exception as e:
            self.logger.error(f"Error recording performance metric: {e}")
            return self._create_error_result(task, f"Error recording performance metric: {str(e)}")
    
    async def _handle_get_performance_metrics(self, task: Task) -> TaskResult:
        """Get performance metrics for a component.
        
        Args:
            task: The task requesting performance metrics
            
        Returns:
            A TaskResult containing the performance metrics
        """
        try:
            # Get required parameters
            component_id = task.input_data.get("component_id")
            if not component_id:
                return self._create_error_result(task, "Missing 'component_id' in input data")
            
            # Get optional parameters
            metric_type = task.input_data.get("metric_type")
            days = task.input_data.get("days", 7)
            operation_id = task.input_data.get("operation_id")
            status = task.input_data.get("status")
            limit = task.input_data.get("limit", 100)
            
            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Get performance metrics
            metrics = await self._get_performance_metrics(
                component_id, metric_type, cutoff_date, operation_id, status, limit
            )
            
            # Calculate statistics
            stats = self._calculate_metrics_statistics(metrics)
            
            return self._create_success_result(task, {
                "component_id": component_id,
                "metric_type": metric_type,
                "metrics": metrics,
                "statistics": stats,
                "time_range": {
                    "start": cutoff_date.isoformat(),
                    "end": datetime.now().isoformat()
                },
                "count": len(metrics)
            })
            
        except Exception as e:
            self.logger.error(f"Error getting performance metrics: {e}")
            return self._create_error_result(task, f"Error getting performance metrics: {str(e)}")
    
    async def _handle_analyze_performance_trend(self, task: Task) -> TaskResult:
        """Analyze performance trends for a component.
        
        Args:
            task: The task requesting performance trend analysis
            
        Returns:
            A TaskResult containing the trend analysis
        """
        try:
            # Get required parameters
            component_id = task.input_data.get("component_id")
            if not component_id:
                return self._create_error_result(task, "Missing 'component_id' in input data")
            
            metric_type = task.input_data.get("metric_type")
            if not metric_type:
                return self._create_error_result(task, "Missing 'metric_type' in input data")
            
            # Get optional parameters
            days = task.input_data.get("days", 7)
            window_size = task.input_data.get("window_size", 24)  # hours
            operation_id = task.input_data.get("operation_id")
            
            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Get performance metrics
            metrics = await self._get_performance_metrics(
                component_id, metric_type, cutoff_date, operation_id, None, None
            )
            
            # Calculate trend analysis
            trend_data = self._calculate_performance_trend(metrics, window_size)
            
            # Determine overall trend
            trend_direction = "stable"
            if len(trend_data) >= 2:
                first_value = trend_data[0]["average"]
                last_value = trend_data[-1]["average"]
                
                # Calculate percentage change
                percent_change = 0
                if first_value != 0:
                    percent_change = ((last_value - first_value) / first_value) * 100
                
                # Determine trend direction
                if abs(percent_change) < 5:
                    trend_direction = "stable"
                elif metric_type in ["response_time_ms", "error_rate_percent"]:
                    # For these metrics, increasing is bad
                    trend_direction = "improving" if percent_change < 0 else "degrading"
                else:
                    # For other metrics (like throughput), increasing is good
                    trend_direction = "improving" if percent_change > 0 else "degrading"
            
            return self._create_success_result(task, {
                "component_id": component_id,
                "metric_type": metric_type,
                "trend_data": trend_data,
                "trend_direction": trend_direction,
                "time_range": {
                    "start": cutoff_date.isoformat(),
                    "end": datetime.now().isoformat()
                },
                "window_size_hours": window_size
            })
            
        except Exception as e:
            self.logger.error(f"Error analyzing performance trend: {e}")
            return self._create_error_result(task, f"Error analyzing performance trend: {str(e)}")
    
    async def _handle_clear_old_metrics(self, task: Task) -> TaskResult:
        """Clear old performance metrics.
        
        Args:
            task: The task requesting to clear old metrics
            
        Returns:
            A TaskResult with the result of the operation
        """
        try:
            # Get optional days parameter
            days = task.input_data.get("days", self.retention_days)
            
            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Get all performance metrics files
            removed_count = 0
            for filename in os.listdir(self.data_dir):
                if not filename.startswith("perf_") or not filename.endswith(".json"):
                    continue
                
                file_path = os.path.join(self.data_dir, filename)
                file_time = os.path.getmtime(file_path)
                file_date = datetime.fromtimestamp(file_time)
                
                if file_date < cutoff_date:
                    try:
                        os.remove(file_path)
                        removed_count += 1
                    except OSError as e:
                        self.logger.warning(f"Error removing old metrics file {filename}: {e}")
            
            return self._create_success_result(task, {
                "message": f"Cleared {removed_count} old performance metrics files",
                "removed_count": removed_count,
                "cutoff_date": cutoff_date.isoformat()
            })
            
        except Exception as e:
            self.logger.error(f"Error clearing old metrics: {e}")
            return self._create_error_result(task, f"Error clearing old metrics: {str(e)}")
    
    async def _handle_health_check(self, task: Task) -> TaskResult:
        """Perform a health check on the PerformanceMetricsTracker.
        
        Args:
            task: The health check task
            
        Returns:
            A TaskResult with the health check results
        """
        is_healthy = await self.health_check()
        
        return self._create_success_result(task, {
            "status": "healthy" if is_healthy else "unhealthy",
            "component": "PerformanceMetricsTracker",
            "timestamp": datetime.now().isoformat()
        })
    
    async def _store_performance_metric(
        self, component_id: str, metric_type: str, metric: Dict[str, Any]
    ) -> None:
        """Store a performance metric.
        
        Args:
            component_id: ID of the component
            metric_type: Type of metric
            metric: Metric data to store
        """
        # Create filename for this component and metric type
        filename = f"perf_{component_id}_{metric_type}.json"
        
        # Load existing metrics
        metrics_data = self.load_data(filename) or {"metrics": []}
        
        # Add new metric
        metrics = metrics_data.get("metrics", [])
        metrics.append(metric)
        
        # Limit metrics size
        max_metrics = 10000  # Keep last 10000 metrics
        if len(metrics) > max_metrics:
            metrics = metrics[-max_metrics:]
        
        # Update metrics data
        metrics_data["metrics"] = metrics
        metrics_data["last_updated"] = datetime.now().isoformat()
        
        # Save updated metrics
        self.store_data(filename, metrics_data)
    
    async def _get_performance_metrics(
        self, 
        component_id: str, 
        metric_type: Optional[str] = None,
        cutoff_date: Optional[datetime] = None,
        operation_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get performance metrics matching the criteria.
        
        Args:
            component_id: ID of the component
            metric_type: Optional type of metric to filter by
            cutoff_date: Optional cutoff date for filtering
            operation_id: Optional operation ID to filter by
            status: Optional status to filter by
            limit: Optional maximum number of metrics to return
            
        Returns:
            List of performance metrics
        """
        metrics: List[Dict[str, Any]] = []
        
        # If metric_type is provided, we can just load that specific file
        if metric_type:
            filename = f"perf_{component_id}_{metric_type}.json"
            metrics_data = self.load_data(filename) or {"metrics": []}
            metrics.extend(metrics_data.get("metrics", []))
        else:
            # Otherwise, we need to load all metric files for this component
            prefix = f"perf_{component_id}_"
            for filename in os.listdir(self.data_dir):
                if filename.startswith(prefix) and filename.endswith(".json"):
                    metrics_data = self.load_data(filename) or {"metrics": []}
                    metrics.extend(metrics_data.get("metrics", []))
        
        # Apply filters
        filtered_metrics = []
        for metric in metrics:
            # Apply cutoff date filter
            if cutoff_date and "timestamp" in metric:
                try:
                    metric_time = datetime.fromisoformat(metric["timestamp"])
                    if metric_time < cutoff_date:
                        continue
                except (ValueError, TypeError):
                    # Skip metrics with invalid timestamps
                    continue
            
            # Apply operation_id filter
            if operation_id and metric.get("operation_id") != operation_id:
                continue
            
            # Apply status filter
            if status and metric.get("status") != status:
                continue
            
            # Add to filtered metrics
            filtered_metrics.append(metric)
        
        # Sort by timestamp (newest first)
        filtered_metrics.sort(
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )
        
        # Apply limit if provided
        if limit is not None:
            filtered_metrics = filtered_metrics[:limit]
        
        return filtered_metrics
    
    def _calculate_metrics_statistics(self, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistics for a list of metrics.
        
        Args:
            metrics: List of metrics
            
        Returns:
            Dictionary of statistics
        """
        if not metrics:
            return {
                "count": 0,
                "min": None,
                "max": None,
                "average": None,
                "median": None,
                "p95": None,
                "status_counts": {}
            }
        
        # Extract values
        values = []
        status_counts: Dict[str, int] = {}
        
        for metric in metrics:
            # Add value to list
            value = metric.get("value")
            if value is not None:
                values.append(value)
            
            # Count statuses
            status = metric.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Calculate statistics
        stats = {
            "count": len(metrics),
            "status_counts": status_counts
        }
        
        if values:
            stats.update({
                "min": min(values),
                "max": max(values),
                "average": sum(values) / len(values),
                "median": statistics.median(values) if len(values) > 0 else None
            })
            
            # Calculate 95th percentile if we have enough values
            if len(values) > 1:
                values.sort()
                p95_index = int(len(values) * 0.95)
                stats["p95"] = values[p95_index]
            else:
                stats["p95"] = values[0] if values else None
        
        return stats
    
    def _calculate_performance_trend(
        self, metrics: List[Dict[str, Any]], window_size: int
    ) -> List[Dict[str, Any]]:
        """Calculate performance trend over time.
        
        Args:
            metrics: List of metrics
            window_size: Size of the time window in hours
            
        Returns:
            List of trend data points
        """
        if not metrics:
            return []
        
        # Group metrics by time window
        windows: Dict[str, List[float]] = {}
        
        for metric in metrics:
            if "timestamp" not in metric or "value" not in metric:
                continue
                
            try:
                timestamp = datetime.fromisoformat(metric["timestamp"])
                value = metric["value"]
                
                # Create a window key based on the timestamp
                window_key = timestamp.strftime("%Y-%m-%d %H:00:00")
                if window_size > 1:
                    # Group into larger windows based on window_size
                    hour = timestamp.hour
                    window_hour = (hour // window_size) * window_size
                    window_key = timestamp.strftime(f"%Y-%m-%d {window_hour:02d}:00:00")
                
                if window_key not in windows:
                    windows[window_key] = []
                    
                windows[window_key].append(value)
                
            except (ValueError, TypeError):
                # Skip metrics with invalid timestamps or values
                continue
        
        # Calculate statistics for each window
        trend_data = []
        
        for window_key, values in sorted(windows.items()):
            if not values:
                continue
                
            data_point = {
                "timestamp": window_key,
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "average": sum(values) / len(values)
            }
            
            if len(values) > 1:
                data_point["median"] = statistics.median(values)
                values.sort()
                p95_index = int(len(values) * 0.95)
                data_point["p95"] = values[p95_index]
            else:
                data_point["median"] = values[0]
                data_point["p95"] = values[0]
                
            trend_data.append(data_point)
        
        return trend_data 