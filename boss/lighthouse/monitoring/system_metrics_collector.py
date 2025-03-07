"""System metrics collector for the BOSS system.

This module provides a component for collecting system metrics like CPU, memory,
and disk usage. It extends the BaseMonitoring class with system metrics specific
functionality.
"""

import logging
import os
import time
import platform
import psutil  # type: ignore
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from boss.core.task_models import Task, TaskResult
from boss.core.task_resolver import TaskResolverMetadata
from boss.core.task_status import TaskStatus
from boss.lighthouse.monitoring.base_monitoring import BaseMonitoring
from boss.lighthouse.monitoring.metrics_storage import MetricsStorage


class SystemMetricsCollector(BaseMonitoring):
    """Component for collecting system metrics.
    
    This component collects various system metrics including:
    - CPU usage
    - Memory usage
    - Disk usage
    - Network I/O
    - System uptime
    
    Attributes:
        collection_interval: Interval (in seconds) between metrics collections
        retention_days: Number of days to retain metrics data
    """
    
    def __init__(self, metadata: TaskResolverMetadata) -> None:
        """Initialize the SystemMetricsCollector.
        
        Args:
            metadata: Resolver metadata
        """
        super().__init__(metadata, "system_metrics")
        
        # Load configuration
        default_config = {
            "collection_interval": 60,  # seconds
            "retention_days": 30
        }
        config = self.load_config(default_config)
        
        self.collection_interval = config["collection_interval"]
        self.retention_days = config["retention_days"]
        
        # Set up component-specific attributes
        self.logger = logging.getLogger("boss.lighthouse.monitoring.system_metrics_collector")
        
        # In-memory metrics storage (temporary)
        self.metrics: Dict[str, Any] = {}
        
        # Initialize persistent storage
        self.metrics_storage = MetricsStorage(self.data_dir)
    
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
            if operation == "collect_system_metrics":
                return await self._handle_collect_system_metrics(task)
            elif operation == "get_system_metrics":
                return await self._handle_get_system_metrics(task)
            elif operation == "clear_old_metrics":
                return await self._handle_clear_old_metrics(task)
            elif operation == "get_system_info":
                return await self._handle_get_system_info(task)
            elif operation == "health_check":
                return await self._handle_health_check(task)
            else:
                return self._create_error_result(task, f"Unsupported operation: {operation}")
        
        except Exception as e:
            self.logger.error(f"Error in SystemMetricsCollector: {e}")
            return self._create_error_result(task, f"Internal error: {str(e)}")
    
    async def _handle_collect_system_metrics(self, task: Task) -> TaskResult:
        """Handle the collect_system_metrics operation.
        
        Args:
            task: The task to handle
            
        Returns:
            A TaskResult with the collected metrics
        """
        if not isinstance(task.input_data, dict):
            return self._create_error_result(task, "Input data must be a dictionary")
            
        # Get optional metrics type parameter
        metrics_type = task.input_data.get("metrics_type")
        
        # Collect the specified metrics or all if not specified
        collected_metrics = {}
        
        try:
            if metrics_type == "cpu" or metrics_type is None:
                collected_metrics["cpu"] = self._collect_cpu_metrics()
                
            if metrics_type == "memory" or metrics_type is None:
                collected_metrics["memory"] = self._collect_memory_metrics()
                
            if metrics_type == "disk" or metrics_type is None:
                collected_metrics["disk"] = self._collect_disk_metrics()
                
            if metrics_type == "network" or metrics_type is None:
                collected_metrics["network"] = self._collect_network_metrics()
                
            # Store the metrics persistently
            for metric_type, metric_data in collected_metrics.items():
                self.metrics_storage.store_system_metric(metric_type, metric_data)
                
            # Determine what to return based on the metrics_type
            if metrics_type and metrics_type in collected_metrics:
                result_metrics = collected_metrics[metrics_type]
                result_metrics["type"] = metrics_type
            else:
                # If no specific type was requested, return all metrics
                result_metrics = {
                    "timestamp": datetime.now().isoformat(),
                    "metrics": collected_metrics
                }
                
            return self._create_success_result(task, {
                "metrics": result_metrics
            })
            
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
            return self._create_error_result(task, f"Error collecting system metrics: {str(e)}")
    
    async def _handle_get_system_metrics(self, task: Task) -> TaskResult:
        """Handle the get_system_metrics operation.
        
        Args:
            task: The task to handle
            
        Returns:
            A TaskResult with the requested metrics
        """
        if not isinstance(task.input_data, dict):
            return self._create_error_result(task, "Input data must be a dictionary")
            
        try:
            # Get optional parameters
            metrics_type = task.input_data.get("metrics_type")
            time_window = task.input_data.get("time_window", "24h")
            aggregation = task.input_data.get("aggregation")
            
            # Parse the time window to get start and end times
            start_time = self._parse_time_window(time_window)
            end_time = datetime.now()
            
            # Retrieve metrics from persistent storage
            metrics = self.metrics_storage.get_system_metrics(
                metric_type=metrics_type,
                start_time=start_time,
                end_time=end_time
            )
            
            # Apply aggregation if requested
            if aggregation:
                metrics = self._aggregate_metrics(metrics, aggregation)
                
            # Calculate statistics
            statistics = self._calculate_statistics(metrics, metrics_type)
                
            return self._create_success_result(task, {
                "metrics": metrics,
                "metrics_type": metrics_type or "all",
                "time_window": time_window,
                "count": len(metrics),
                "statistics": statistics
            })
            
        except Exception as e:
            self.logger.error(f"Error retrieving system metrics: {e}")
            return self._create_error_result(task, f"Error retrieving system metrics: {str(e)}")
    
    async def _handle_clear_old_metrics(self, task: Task) -> TaskResult:
        """Handle the clear_old_metrics operation.
        
        Args:
            task: The task to handle
            
        Returns:
            A TaskResult with the result of the operation
        """
        if not isinstance(task.input_data, dict):
            return self._create_error_result(task, "Input data must be a dictionary")
            
        try:
            # Get optional parameters
            retention_days = task.input_data.get("retention_days", self.retention_days)
            
            # Clear old metrics from persistent storage
            cleared_count = self.metrics_storage.clear_old_system_metrics(retention_days)
            
            return self._create_success_result(task, {
                "message": f"Successfully cleared {cleared_count} old metrics records",
                "cleared_count": cleared_count,
                "retention_days": retention_days
            })
            
        except Exception as e:
            self.logger.error(f"Error clearing old metrics: {e}")
            return self._create_error_result(task, f"Error clearing old metrics: {str(e)}")
    
    async def _handle_get_system_info(self, task: Task) -> TaskResult:
        """Get general system information.
        
        Args:
            task: The task requesting system information
            
        Returns:
            A TaskResult containing system information
        """
        try:
            system_info = {
                "platform": platform.platform(),
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "processor": platform.processor(),
                "hostname": platform.node(),
                "python_version": platform.python_version(),
                "uptime": self._get_uptime(),
                "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat()
            }
            
            # Get CPU info
            cpu_info = {
                "physical_cores": psutil.cpu_count(logical=False),
                "logical_cores": psutil.cpu_count(logical=True),
                "max_frequency": psutil.cpu_freq().max if psutil.cpu_freq() else None,
                "min_frequency": psutil.cpu_freq().min if psutil.cpu_freq() else None
            }
            
            # Get memory info
            memory = psutil.virtual_memory()
            memory_info = {
                "total": memory.total,
                "total_gb": round(memory.total / (1024**3), 2)
            }
            
            # Get disk info
            disk_info = []
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_info.append({
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "filesystem_type": partition.fstype,
                        "total_gb": round(usage.total / (1024**3), 2),
                        "free_gb": round(usage.free / (1024**3), 2)
                    })
                except (PermissionError, OSError):
                    # Some mountpoints might not be accessible
                    pass
            
            system_info.update({
                "cpu": cpu_info,
                "memory": memory_info,
                "disks": disk_info
            })
            
            return self._create_success_result(task, {
                "system_info": system_info
            })
            
        except Exception as e:
            self.logger.error(f"Error getting system info: {e}")
            return self._create_error_result(task, f"Error getting system info: {str(e)}")
    
    async def _handle_health_check(self, task: Task) -> TaskResult:
        """Perform a health check on the SystemMetricsCollector.
        
        Args:
            task: The health check task
            
        Returns:
            A TaskResult with the health check results
        """
        is_healthy = await self.health_check()
        
        return self._create_success_result(task, {
            "status": "healthy" if is_healthy else "unhealthy",
            "component": "SystemMetricsCollector",
            "timestamp": datetime.now().isoformat()
        })
    
    def _collect_cpu_metrics(self) -> Dict[str, Any]:
        """Collect CPU metrics.
        
        Returns:
            A dictionary of CPU metrics
        """
        cpu_times_percent = psutil.cpu_times_percent(interval=0.5)
        return {
            "usage_percent": psutil.cpu_percent(interval=0.5),
            "per_cpu_percent": psutil.cpu_percent(interval=0.5, percpu=True),
            "user_percent": cpu_times_percent.user,
            "system_percent": cpu_times_percent.system,
            "idle_percent": cpu_times_percent.idle,
            "load_avg": os.getloadavg() if hasattr(os, 'getloadavg') else None
        }
    
    def _collect_memory_metrics(self) -> Dict[str, Any]:
        """Collect memory metrics.
        
        Returns:
            A dictionary of memory metrics
        """
        virtual_memory = psutil.virtual_memory()
        swap_memory = psutil.swap_memory()
        
        return {
            "total": virtual_memory.total,
            "available": virtual_memory.available,
            "used": virtual_memory.used,
            "free": virtual_memory.free,
            "percent": virtual_memory.percent,
            "swap_total": swap_memory.total,
            "swap_used": swap_memory.used,
            "swap_free": swap_memory.free,
            "swap_percent": swap_memory.percent
        }
    
    def _collect_disk_metrics(self) -> Dict[str, Any]:
        """Collect disk metrics.
        
        Returns:
            A dictionary of disk metrics
        """
        partitions = []
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                partitions.append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent
                })
            except (PermissionError, OSError):
                # Some mountpoints might not be accessible
                pass
        
        # Get disk I/O counters
        disk_io = psutil.disk_io_counters()
        
        return {
            "partitions": partitions,
            "io_counters": {
                "read_count": disk_io.read_count if disk_io else 0,
                "write_count": disk_io.write_count if disk_io else 0,
                "read_bytes": disk_io.read_bytes if disk_io else 0,
                "write_bytes": disk_io.write_bytes if disk_io else 0,
                "read_time": disk_io.read_time if disk_io else 0,
                "write_time": disk_io.write_time if disk_io else 0
            }
        }
    
    def _collect_network_metrics(self) -> Dict[str, Any]:
        """Collect network metrics.
        
        Returns:
            A dictionary of network metrics
        """
        interfaces = {}
        for interface, stats in psutil.net_io_counters(pernic=True).items():
            interfaces[interface] = {
                "bytes_sent": stats.bytes_sent,
                "bytes_recv": stats.bytes_recv,
                "packets_sent": stats.packets_sent,
                "packets_recv": stats.packets_recv,
                "errin": stats.errin,
                "errout": stats.errout,
                "dropin": stats.dropin,
                "dropout": stats.dropout
            }
        
        # Get total network I/O
        total_io = psutil.net_io_counters()
        
        return {
            "interfaces": interfaces,
            "total": {
                "bytes_sent": total_io.bytes_sent,
                "bytes_recv": total_io.bytes_recv,
                "packets_sent": total_io.packets_sent,
                "packets_recv": total_io.packets_recv
            }
        }
    
    def _get_uptime(self) -> float:
        """Get system uptime in seconds.
        
        Returns:
            System uptime in seconds
        """
        return time.time() - psutil.boot_time()
    
    def _calculate_statistics(self, metrics: List[Dict[str, Any]], metrics_type: Optional[str] = None) -> Dict[str, Any]:
        """Calculate statistics for the given metrics.
        
        Args:
            metrics: List of metrics to calculate statistics for
            metrics_type: Optional type of metrics to focus on
            
        Returns:
            A dictionary of statistics
        """
        if not metrics:
            return {}
            
        statistics = {}
        
        # Handle CPU metrics
        if metrics_type == "cpu" or metrics_type is None:
            cpu_usage = [m.get("usage_percent", 0) for m in metrics if "usage_percent" in m]
            if cpu_usage:
                statistics["avg_cpu_usage_percent"] = sum(cpu_usage) / len(cpu_usage)
                statistics["max_cpu_usage_percent"] = max(cpu_usage)
                statistics["min_cpu_usage_percent"] = min(cpu_usage)
                
        # Handle memory metrics
        if metrics_type == "memory" or metrics_type is None:
            memory_percent = [m.get("usage_percent", 0) for m in metrics if "usage_percent" in m]
            if memory_percent:
                statistics["avg_memory_usage_percent"] = sum(memory_percent) / len(memory_percent)
                statistics["max_memory_usage_percent"] = max(memory_percent)
                statistics["min_memory_usage_percent"] = min(memory_percent)
                
        # Handle disk metrics
        if metrics_type == "disk" or metrics_type is None:
            disk_percent = [m.get("usage_percent", 0) for m in metrics if "usage_percent" in m]
            if disk_percent:
                statistics["avg_disk_usage_percent"] = sum(disk_percent) / len(disk_percent)
                statistics["max_disk_usage_percent"] = max(disk_percent)
                statistics["min_disk_usage_percent"] = min(disk_percent)
                
        return statistics
    
    def _parse_time_window(self, time_window: str) -> datetime:
        """Parse a time window string into a cutoff date.
        
        Args:
            time_window: String in format "Xh", "Xd", "Xw" for hours, days, weeks
            
        Returns:
            A datetime representing the cutoff date
        """
        try:
            # Default to 24 hours if the format is invalid
            if not time_window or not isinstance(time_window, str):
                return datetime.now() - timedelta(hours=24)
                
            # Extract the number and unit
            import re
            match = re.match(r"(\d+)([hdw])", time_window.lower())
            if not match:
                return datetime.now() - timedelta(hours=24)
                
            value = int(match.group(1))
            unit = match.group(2)
            
            if unit == "h":
                return datetime.now() - timedelta(hours=value)
            elif unit == "d":
                return datetime.now() - timedelta(days=value)
            elif unit == "w":
                return datetime.now() - timedelta(weeks=value)
            else:
                return datetime.now() - timedelta(hours=24)
                
        except Exception:
            # Default to 24 hours if there's any error
            return datetime.now() - timedelta(hours=24)
    
    def _aggregate_metrics(self, metrics: List[Dict[str, Any]], aggregation: str) -> List[Dict[str, Any]]:
        """Aggregate metrics based on the specified time aggregation.
        
        Args:
            metrics: The list of metrics to aggregate
            aggregation: The aggregation level (hourly, daily)
            
        Returns:
            A list of aggregated metrics
        """
        aggregated_metrics = []
        
        # Group metrics by the aggregation period
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        
        for metric in metrics:
            timestamp_str = metric.get("timestamp", "")
            if not timestamp_str:
                continue
                
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
                
                # Create the group key based on aggregation
                if aggregation == "hourly":
                    group_key = timestamp.strftime("%Y-%m-%d %H:00:00")
                elif aggregation == "daily":
                    group_key = timestamp.strftime("%Y-%m-%d 00:00:00")
                else:
                    # Default to no aggregation
                    aggregated_metrics.append(metric)
                    continue
                    
                if group_key not in grouped:
                    grouped[group_key] = []
                    
                grouped[group_key].append(metric)
                
            except ValueError:
                self.logger.warning(f"Invalid timestamp format: {timestamp_str}")
                
        # If we're not aggregating, return the original metrics
        if aggregation not in ["hourly", "daily"]:
            return metrics
            
        # Process each group
        for timestamp_key, group in grouped.items():
            aggregated: Dict[str, Any] = {
                "timestamp": timestamp_key,
                "metrics": {}  # Initialize metrics as empty dict
            }
            
            # Aggregate CPU metrics
            cpu_usage = [m["metrics"].get("cpu", {}).get("usage_percent", 0) for m in group if "metrics" in m and "cpu" in m["metrics"]]
            if cpu_usage:
                # Create the CPU metrics dictionary if it doesn't exist
                if "cpu" not in aggregated["metrics"]:
                    aggregated["metrics"]["cpu"] = {}
                
                # Now assign to the dictionary
                metrics_cpu = aggregated["metrics"]["cpu"]
                metrics_cpu["usage_percent_avg"] = sum(cpu_usage) / len(cpu_usage)
                metrics_cpu["usage_percent_max"] = max(cpu_usage)
                metrics_cpu["usage_percent_min"] = min(cpu_usage)
                
            # Aggregate memory metrics
            memory_percent = [m["metrics"].get("memory", {}).get("percent", 0) for m in group if "metrics" in m and "memory" in m["metrics"]]
            if memory_percent:
                # Create the memory metrics dictionary if it doesn't exist
                if "memory" not in aggregated["metrics"]:
                    aggregated["metrics"]["memory"] = {}
                
                # Now assign to the dictionary
                metrics_memory = aggregated["metrics"]["memory"]
                metrics_memory["percent_avg"] = sum(memory_percent) / len(memory_percent)
                metrics_memory["percent_max"] = max(memory_percent)
                metrics_memory["percent_min"] = min(memory_percent)
                
            aggregated_metrics.append(aggregated)
        
        # Sort by timestamp using a specific type annotation to satisfy the linter
        from typing import Any, Callable
        
        def get_timestamp(x: Dict[str, Any]) -> str:
            return str(x.get("timestamp", ""))
            
        aggregated_metrics.sort(key=get_timestamp)
        
        return aggregated_metrics 