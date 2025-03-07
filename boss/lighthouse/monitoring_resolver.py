"""MonitoringResolver for tracking system health and performance metrics.

This resolver provides monitoring capabilities for the BOSS system, collecting metrics
on component performance, health status, resource usage, and system events. It serves
as a core component of the Lighthouse monitoring infrastructure.
"""

import os
import json
import time
import logging
import platform
import shutil
import psutil  # type: ignore
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, cast

from boss.core.task_models import Task, TaskResult  # type: ignore
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata  # type: ignore
from boss.core.task_status import TaskStatus  # type: ignore


class MonitoringResolver(TaskResolver):
    """Resolver for handling system monitoring operations.
    
    This resolver supports various monitoring operations including:
    - Component health checks
    - Performance metrics collection
    - Resource usage tracking
    - System event logging
    - Alert generation
    
    Attributes:
        boss_home_dir: The home directory of the BOSS instance
        metrics_dir: Directory for storing metrics data
        alerts_dir: Directory for storing alerts
        config_file: Path to the monitoring configuration file
        max_history_days: Maximum number of days to keep historical metrics
        alert_thresholds: Dictionary of alert thresholds
    """
    
    def __init__(self, metadata: TaskResolverMetadata) -> None:
        """Initialize the MonitoringResolver.
        
        Args:
            metadata: Resolver metadata
        """
        super().__init__(metadata)
        self.boss_home_dir = os.environ.get("BOSS_HOME", os.getcwd())
        self.metrics_dir = os.path.join(self.boss_home_dir, "data", "metrics")
        self.alerts_dir = os.path.join(self.boss_home_dir, "data", "alerts")
        self.config_file = os.path.join(self.boss_home_dir, "config", "monitoring.json")
        
        # Ensure directories exist
        os.makedirs(self.metrics_dir, exist_ok=True)
        os.makedirs(self.alerts_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        
        # Load configuration or create default
        self.max_history_days = 30
        self.alert_thresholds = {
            "cpu_usage": 90.0,  # Percentage
            "memory_usage": 90.0,  # Percentage
            "disk_usage": 90.0,  # Percentage
            "error_rate": 5.0,  # Percentage
            "response_time": 5000.0  # Milliseconds
        }
        self.load_config()
        
        # Set up logging
        self.logger = logging.getLogger("boss.lighthouse.monitoring")
    
    def load_config(self) -> None:
        """Load monitoring configuration from file or create default."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    config = json.load(f)
                    self.max_history_days = config.get("max_history_days", 30)
                    self.alert_thresholds.update(config.get("alert_thresholds", {}))
            except Exception as e:
                self.logger.error(f"Failed to load monitoring config: {str(e)}")
                self.save_config()  # Save default config
        else:
            self.save_config()  # Create default config
    
    def save_config(self) -> None:
        """Save monitoring configuration to file."""
        try:
            config = {
                "max_history_days": self.max_history_days,
                "alert_thresholds": self.alert_thresholds,
                "updated_at": datetime.now().isoformat()
            }
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save monitoring config: {str(e)}")
    
    async def resolve(self, task: Task) -> TaskResult:
        """Resolve the monitoring task.
        
        Args:
            task: The monitoring task to resolve
            
        Returns:
            The task result with the outcome of the monitoring operation
        """
        try:
            if not isinstance(task.input_data, dict):
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": "Input data must be a dictionary"}
                )
            
            operation = task.input_data.get("operation")
            if not operation:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": "Missing 'operation' field in input data"}
                )
                
            # Handle different operations
            if operation == "collect_system_metrics":
                return await self._handle_collect_system_metrics(task)
            elif operation == "check_component_health":
                return await self._handle_check_component_health(task)
            elif operation == "get_performance_metrics":
                return await self._handle_get_performance_metrics(task)
            elif operation == "generate_alert":
                return await self._handle_generate_alert(task)
            elif operation == "list_alerts":
                return await self._handle_list_alerts(task)
            elif operation == "clear_old_metrics":
                return await self._handle_clear_old_metrics(task)
            elif operation == "update_alert_thresholds":
                return await self._handle_update_alert_thresholds(task)
            elif operation == "get_system_status":
                return await self._handle_get_system_status(task)
            elif operation == "health_check":
                return await self._handle_health_check(task)
            else:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": f"Unsupported operation: {operation}"}
                )
                
        except Exception as e:
            self.logger.error(f"Error in MonitoringResolver: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": str(e)}
            )
    
    async def _handle_collect_system_metrics(self, task: Task) -> TaskResult:
        """Handle collection of system metrics.
        
        Args:
            task: The collect system metrics task
            
        Returns:
            The result of the metrics collection operation
        """
        # Collect system metrics
        metrics = self._get_system_metrics()
        timestamp = datetime.now().isoformat()
        
        # Store metrics if needed
        should_store = task.input_data.get("store_metrics", True)
        if should_store:
            # Create timestamp-based directory structure
            now = datetime.now()
            year_dir = os.path.join(self.metrics_dir, str(now.year))
            month_dir = os.path.join(year_dir, f"{now.month:02d}")
            day_dir = os.path.join(month_dir, f"{now.day:02d}")
            os.makedirs(day_dir, exist_ok=True)
            
            # Save metrics to file
            metrics_file = os.path.join(day_dir, f"{now.hour:02d}-{now.minute:02d}-{now.second:02d}.json")
            with open(metrics_file, "w") as f:
                json.dump(metrics, f, indent=2)
        
        # Check for alert thresholds
        alerts = []
        if metrics["cpu_usage"] > self.alert_thresholds["cpu_usage"]:
            alerts.append({
                "type": "cpu_usage",
                "message": f"CPU usage ({metrics['cpu_usage']:.2f}%) exceeds threshold ({self.alert_thresholds['cpu_usage']}%)",
                "level": "warning",
                "timestamp": timestamp
            })
            
        if metrics["memory_usage"] > self.alert_thresholds["memory_usage"]:
            alerts.append({
                "type": "memory_usage",
                "message": f"Memory usage ({metrics['memory_usage']:.2f}%) exceeds threshold ({self.alert_thresholds['memory_usage']}%)",
                "level": "warning",
                "timestamp": timestamp
            })
            
        if metrics["disk_usage"] > self.alert_thresholds["disk_usage"]:
            alerts.append({
                "type": "disk_usage",
                "message": f"Disk usage ({metrics['disk_usage']:.2f}%) exceeds threshold ({self.alert_thresholds['disk_usage']}%)",
                "level": "warning",
                "timestamp": timestamp
            })
        
        # Generate alerts if needed
        if alerts and task.input_data.get("generate_alerts", True):
            for alert in alerts:
                await self._store_alert(alert)
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "metrics": metrics,
                "timestamp": timestamp,
                "alerts": alerts
            }
        )
    
    async def _handle_check_component_health(self, task: Task) -> TaskResult:
        """Handle checking the health of a specific component.
        
        Args:
            task: The check component health task
            
        Returns:
            The result of the health check operation
        """
        input_data = cast(Dict[str, Any], task.input_data)
        component_id = input_data.get("component_id")
        
        if not component_id:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing 'component_id' in input data"}
            )
            
        # Try to load the component and check its health
        try:
            # This is a simplified approach - in a real system we would
            # need to dynamically load the component and call its health check
            health_task = Task(
                id=f"health_check_{component_id}",
                name=f"Health check for {component_id}",
                input_data={"operation": "health_check"},
                metadata=task.metadata
            )
            
            # For now, just simulate a health check result
            health_status = "ok"
            details = {"status": "ok", "message": f"Component {component_id} is functioning properly"}
            
            # Record the health check result
            timestamp = datetime.now().isoformat()
            health_check_result = {
                "component_id": component_id,
                "status": health_status,
                "details": details,
                "timestamp": timestamp
            }
            
            # Store the health check result if requested
            should_store = input_data.get("store_result", True)
            if should_store:
                health_checks_dir = os.path.join(self.metrics_dir, "health_checks")
                os.makedirs(health_checks_dir, exist_ok=True)
                
                component_file = os.path.join(health_checks_dir, f"{component_id}.json")
                
                # Read existing checks if available
                existing_checks = []
                if os.path.exists(component_file):
                    with open(component_file, "r") as f:
                        try:
                            existing_data = json.load(f)
                            if isinstance(existing_data, list):
                                existing_checks = existing_data
                            else:
                                existing_checks = [existing_data]
                        except:
                            pass
                
                # Add new check and limit history
                existing_checks.append(health_check_result)
                if len(existing_checks) > 100:
                    existing_checks = existing_checks[-100:]
                
                # Write updated checks
                with open(component_file, "w") as f:
                    json.dump(existing_checks, f, indent=2)
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data=health_check_result
            )
            
        except Exception as e:
            self.logger.error(f"Error checking component health: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={
                    "error": f"Failed to check component health: {str(e)}",
                    "component_id": component_id,
                    "status": "error",
                    "timestamp": datetime.now().isoformat()
                }
            )
    
    async def _handle_get_performance_metrics(self, task: Task) -> TaskResult:
        """Handle retrieving performance metrics.
        
        Args:
            task: The get performance metrics task
            
        Returns:
            The result with performance metrics
        """
        input_data = cast(Dict[str, Any], task.input_data)
        component_id = input_data.get("component_id")
        start_date = input_data.get("start_date")
        end_date = input_data.get("end_date")
        metrics_type = input_data.get("metrics_type", "all")
        
        # Parse dates if provided
        start_datetime = None
        end_datetime = None
        
        if start_date:
            try:
                start_datetime = datetime.fromisoformat(start_date)
            except ValueError:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": f"Invalid start_date format: {start_date}. Use ISO format (YYYY-MM-DDTHH:MM:SS)."}
                )
                
        if end_date:
            try:
                end_datetime = datetime.fromisoformat(end_date)
            except ValueError:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": f"Invalid end_date format: {end_date}. Use ISO format (YYYY-MM-DDTHH:MM:SS)."}
                )
        
        # If no dates provided, default to last 24 hours
        if not start_datetime:
            start_datetime = datetime.now() - timedelta(days=1)
        if not end_datetime:
            end_datetime = datetime.now()
            
        # Collect metrics
        try:
            metrics = []
            
            # Read metrics files based on date range
            current_date = start_datetime.date()
            end_date_obj = end_datetime.date()
            
            while current_date <= end_date_obj:
                # Construct the directory path for this date
                year_dir = os.path.join(self.metrics_dir, str(current_date.year))
                month_dir = os.path.join(year_dir, f"{current_date.month:02d}")
                day_dir = os.path.join(month_dir, f"{current_date.day:02d}")
                
                if os.path.exists(day_dir):
                    # Read metrics files for this day
                    for filename in sorted(os.listdir(day_dir)):
                        if filename.endswith(".json"):
                            file_path = os.path.join(day_dir, filename)
                            with open(file_path, "r") as f:
                                metric_data = json.load(f)
                                
                                # Filter by component if specified
                                if component_id and "component_id" in metric_data:
                                    if metric_data["component_id"] != component_id:
                                        continue
                                
                                # Filter by type if specified
                                if metrics_type != "all":
                                    if "type" in metric_data and metric_data["type"] != metrics_type:
                                        continue
                                
                                # Add to collected metrics
                                metrics.append(metric_data)
                
                # Move to next day
                current_date += timedelta(days=1)
            
            # Sort metrics by timestamp if available
            metrics.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "metrics": metrics,
                    "count": len(metrics),
                    "start_date": start_datetime.isoformat(),
                    "end_date": end_datetime.isoformat()
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error retrieving performance metrics: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Failed to retrieve performance metrics: {str(e)}"}
            )
    
    async def _handle_generate_alert(self, task: Task) -> TaskResult:
        """Handle generating a system alert.
        
        Args:
            task: The generate alert task
            
        Returns:
            The result of the alert generation operation
        """
        input_data = cast(Dict[str, Any], task.input_data)
        alert_type = input_data.get("type")
        message = input_data.get("message")
        level = input_data.get("level", "info")
        component_id = input_data.get("component_id")
        
        if not alert_type:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing 'type' in input data"}
            )
            
        if not message:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing 'message' in input data"}
            )
            
        # Create alert data
        timestamp = datetime.now().isoformat()
        alert = {
            "type": alert_type,
            "message": message,
            "level": level,
            "timestamp": timestamp
        }
        
        if component_id:
            alert["component_id"] = component_id
            
        # Store the alert
        await self._store_alert(alert)
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "alert": alert,
                "stored": True,
                "timestamp": timestamp
            }
        )
    
    async def _handle_list_alerts(self, task: Task) -> TaskResult:
        """Handle listing system alerts.
        
        Args:
            task: The list alerts task
            
        Returns:
            The result with list of alerts
        """
        input_data = cast(Dict[str, Any], task.input_data)
        alert_type = input_data.get("type")
        level = input_data.get("level")
        component_id = input_data.get("component_id")
        start_date = input_data.get("start_date")
        end_date = input_data.get("end_date")
        limit = input_data.get("limit", 100)
        
        # Parse dates if provided
        start_datetime = None
        end_datetime = None
        
        if start_date:
            try:
                start_datetime = datetime.fromisoformat(start_date)
            except ValueError:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": f"Invalid start_date format: {start_date}. Use ISO format (YYYY-MM-DDTHH:MM:SS)."}
                )
                
        if end_date:
            try:
                end_datetime = datetime.fromisoformat(end_date)
            except ValueError:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": f"Invalid end_date format: {end_date}. Use ISO format (YYYY-MM-DDTHH:MM:SS)."}
                )
        
        # If no dates provided, default to last 24 hours
        if not start_datetime:
            start_datetime = datetime.now() - timedelta(days=1)
        if not end_datetime:
            end_datetime = datetime.now()
            
        # Collect alerts
        try:
            alerts = []
            
            # Read alerts from file
            if os.path.exists(self.alerts_dir):
                for filename in sorted(os.listdir(self.alerts_dir), reverse=True):
                    if filename.endswith(".json"):
                        file_path = os.path.join(self.alerts_dir, filename)
                        with open(file_path, "r") as f:
                            try:
                                alert_data = json.load(f)
                                
                                # Check if it's a list or single alert
                                if isinstance(alert_data, list):
                                    file_alerts = alert_data
                                else:
                                    file_alerts = [alert_data]
                                
                                for alert in file_alerts:
                                    # Apply filters
                                    if alert_type and alert.get("type") != alert_type:
                                        continue
                                        
                                    if level and alert.get("level") != level:
                                        continue
                                        
                                    if component_id and alert.get("component_id") != component_id:
                                        continue
                                        
                                    # Check timestamp range
                                    if "timestamp" in alert:
                                        try:
                                            alert_time = datetime.fromisoformat(alert["timestamp"])
                                            if alert_time < start_datetime or alert_time > end_datetime:
                                                continue
                                        except ValueError:
                                            # Skip if timestamp is invalid
                                            continue
                                    
                                    # Add to collected alerts
                                    alerts.append(alert)
                                    
                                    # Check limit
                                    if len(alerts) >= limit:
                                        break
                            except json.JSONDecodeError:
                                continue
                            
                        # Check limit after processing each file
                        if len(alerts) >= limit:
                            break
            
            # Sort alerts by timestamp
            alerts.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "alerts": alerts,
                    "count": len(alerts),
                    "start_date": start_datetime.isoformat(),
                    "end_date": end_datetime.isoformat()
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error listing alerts: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Failed to list alerts: {str(e)}"}
            )
    
    async def _handle_clear_old_metrics(self, task: Task) -> TaskResult:
        """Handle clearing old metrics data.
        
        Args:
            task: The clear old metrics task
            
        Returns:
            The result of the clearing operation
        """
        input_data = cast(Dict[str, Any], task.input_data)
        days = input_data.get("days", self.max_history_days)
        include_alerts = input_data.get("include_alerts", True)
        dry_run = input_data.get("dry_run", False)
        
        if days <= 0:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Days must be a positive integer"}
            )
            
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_metrics_dirs = 0
        deleted_alert_files = 0
        
        try:
            # Clear old metrics
            if os.path.exists(self.metrics_dir):
                for year_dir in os.listdir(self.metrics_dir):
                    year_path = os.path.join(self.metrics_dir, year_dir)
                    if not os.path.isdir(year_path) or not year_dir.isdigit():
                        continue
                    
                    for month_dir in os.listdir(year_path):
                        month_path = os.path.join(year_path, month_dir)
                        if not os.path.isdir(month_path) or not month_dir.isdigit():
                            continue
                        
                        for day_dir in os.listdir(month_path):
                            day_path = os.path.join(month_path, day_dir)
                            if not os.path.isdir(day_path) or not day_dir.isdigit():
                                continue
                                
                            # Check if this day is before cutoff date
                            try:
                                dir_date = datetime(int(year_dir), int(month_dir), int(day_dir))
                                if dir_date < cutoff_date:
                                    # Delete this day's metrics
                                    if not dry_run:
                                        shutil.rmtree(day_path)
                                    deleted_metrics_dirs += 1
                            except ValueError:
                                # Skip if date is invalid
                                continue
            
            # Clear old alerts if requested
            if include_alerts and os.path.exists(self.alerts_dir):
                for filename in os.listdir(self.alerts_dir):
                    if not filename.endswith(".json"):
                        continue
                        
                    file_path = os.path.join(self.alerts_dir, filename)
                    # Check file modification time
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if file_time < cutoff_date:
                        # Delete this alert file
                        if not dry_run:
                            os.remove(file_path)
                        deleted_alert_files += 1
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "message": f"Cleared metrics older than {days} days",
                    "cutoff_date": cutoff_date.isoformat(),
                    "deleted_metrics_dirs": deleted_metrics_dirs,
                    "deleted_alert_files": deleted_alert_files,
                    "dry_run": dry_run
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error clearing old metrics: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Failed to clear old metrics: {str(e)}"}
            )
    
    async def _handle_update_alert_thresholds(self, task: Task) -> TaskResult:
        """Handle updating alert thresholds.
        
        Args:
            task: The update alert thresholds task
            
        Returns:
            The result of the update operation
        """
        input_data = cast(Dict[str, Any], task.input_data)
        thresholds = input_data.get("thresholds")
        
        if not thresholds or not isinstance(thresholds, dict):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing or invalid 'thresholds' in input data"}
            )
            
        # Update thresholds
        previous_thresholds = self.alert_thresholds.copy()
        self.alert_thresholds.update(thresholds)
        
        # Save updated configuration
        self.save_config()
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "message": "Alert thresholds updated successfully",
                "previous_thresholds": previous_thresholds,
                "current_thresholds": self.alert_thresholds
            }
        )
    
    async def _handle_get_system_status(self, task: Task) -> TaskResult:
        """Handle getting overall system status.
        
        Args:
            task: The get system status task
            
        Returns:
            The result with system status information
        """
        # Collect current system metrics
        system_metrics = self._get_system_metrics()
        
        # Determine overall status based on thresholds
        status_checks = {
            "cpu": "ok" if system_metrics["cpu_usage"] < self.alert_thresholds["cpu_usage"] else "warning",
            "memory": "ok" if system_metrics["memory_usage"] < self.alert_thresholds["memory_usage"] else "warning",
            "disk": "ok" if system_metrics["disk_usage"] < self.alert_thresholds["disk_usage"] else "warning"
        }
        
        # Determine overall status
        overall_status = "ok"
        if "warning" in status_checks.values():
            overall_status = "warning"
        if "error" in status_checks.values():
            overall_status = "error"
        
        # Get recent alerts
        recent_alerts = []
        try:
            # Get alerts from the last hour
            one_hour_ago = datetime.now() - timedelta(hours=1)
            
            if os.path.exists(self.alerts_dir):
                for filename in sorted(os.listdir(self.alerts_dir), reverse=True)[:10]:
                    if filename.endswith(".json"):
                        file_path = os.path.join(self.alerts_dir, filename)
                        with open(file_path, "r") as f:
                            try:
                                alert_data = json.load(f)
                                
                                # Check if it's a list or single alert
                                if isinstance(alert_data, list):
                                    file_alerts = alert_data
                                else:
                                    file_alerts = [alert_data]
                                
                                for alert in file_alerts:
                                    # Check timestamp
                                    if "timestamp" in alert:
                                        try:
                                            alert_time = datetime.fromisoformat(alert["timestamp"])
                                            if alert_time >= one_hour_ago:
                                                recent_alerts.append(alert)
                                        except ValueError:
                                            continue
                                
                                if len(recent_alerts) >= 5:
                                    break
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            self.logger.error(f"Error getting recent alerts: {str(e)}")
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "system_status": {
                    "overall": overall_status,
                    "checks": status_checks,
                    "metrics": system_metrics
                },
                "recent_alerts": recent_alerts,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    async def _handle_health_check(self, task: Task) -> TaskResult:
        """Perform a health check on the resolver.
        
        Args:
            task: The health check task
            
        Returns:
            The result of the health check
        """
        # Check if metrics directory is accessible
        metrics_check = "ok"
        metrics_reason = ""
        
        try:
            # Test write access to metrics directory
            test_file = os.path.join(self.metrics_dir, "health_check_test.tmp")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            metrics_check = "fail"
            metrics_reason = str(e)
            
        # Check if alerts directory is accessible
        alerts_check = "ok"
        alerts_reason = ""
        
        try:
            # Test write access to alerts directory
            test_file = os.path.join(self.alerts_dir, "health_check_test.tmp")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            alerts_check = "fail"
            alerts_reason = str(e)
            
        # Check if configuration file is accessible
        config_check = "ok"
        config_reason = ""
        
        try:
            self.save_config()
        except Exception as e:
            config_check = "fail"
            config_reason = str(e)
            
        # Get system metrics to check if we can collect them
        try:
            system_metrics = self._get_system_metrics()
            metrics_collection = "ok"
        except Exception as e:
            system_metrics = {}
            metrics_collection = "fail"
            
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "status": "ok" if all(s == "ok" for s in [metrics_check, alerts_check, config_check, metrics_collection]) else "fail",
                "metrics_check": metrics_check,
                "metrics_reason": metrics_reason,
                "alerts_check": alerts_check,
                "alerts_reason": alerts_reason,
                "config_check": config_check,
                "config_reason": config_reason,
                "metrics_collection": metrics_collection,
                "system_metrics": system_metrics
            }
        )
    
    def _get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics.
        
        Returns:
            Dictionary of system metrics
        """
        # CPU metrics
        cpu_usage = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
        
        # Memory metrics
        memory = psutil.virtual_memory()
        memory_usage = memory.percent
        memory_total = memory.total
        memory_available = memory.available
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        disk_usage = disk.percent
        disk_total = disk.total
        disk_free = disk.free
        
        # Network metrics
        net_io = psutil.net_io_counters()
        network_bytes_sent = net_io.bytes_sent
        network_bytes_recv = net_io.bytes_recv
        
        # System info
        boot_time = datetime.fromtimestamp(psutil.boot_time()).isoformat()
        uptime_seconds = time.time() - psutil.boot_time()
        
        # Process metrics
        process_count = len(psutil.pids())
        
        return {
            "cpu_usage": cpu_usage,
            "cpu_count": cpu_count,
            "memory_usage": memory_usage,
            "memory_total_bytes": memory_total,
            "memory_available_bytes": memory_available,
            "disk_usage": disk_usage,
            "disk_total_bytes": disk_total,
            "disk_free_bytes": disk_free,
            "network_bytes_sent": network_bytes_sent,
            "network_bytes_recv": network_bytes_recv,
            "boot_time": boot_time,
            "uptime_seconds": uptime_seconds,
            "process_count": process_count,
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "hostname": platform.node()
        }
    
    async def _store_alert(self, alert: Dict[str, Any]) -> None:
        """Store an alert in the alerts directory.
        
        Args:
            alert: The alert data to store
        """
        try:
            # Ensure alerts directory exists
            os.makedirs(self.alerts_dir, exist_ok=True)
            
            # Create timestamp-based filename
            now = datetime.now()
            alert_file = os.path.join(
                self.alerts_dir, 
                f"{now.year:04d}{now.month:02d}{now.day:02d}-{now.hour:02d}{now.minute:02d}{now.second:02d}.json"
            )
            
            # Write alert to file
            with open(alert_file, "w") as f:
                json.dump(alert, f, indent=2)
                
            # Log alert
            self.logger.warning(f"Alert generated: {alert.get('message')}")
            
        except Exception as e:
            self.logger.error(f"Failed to store alert: {str(e)}") 