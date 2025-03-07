"""Component health checker for the BOSS system.

This module provides a component for checking the health of various system components.
It extends the BaseMonitoring class with component health checking capabilities.
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, cast
import re

from boss.core.task_models import Task, TaskResult
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_status import TaskStatus
from boss.lighthouse.monitoring.base_monitoring import BaseMonitoring


class ComponentHealthChecker(BaseMonitoring):
    """Component for checking health of system components.
    
    This component checks the health of various system components and provides
    health status information and history.
    
    Attributes:
        health_check_interval: Interval (in seconds) between health checks
        retention_days: Number of days to retain health check data
        component_timeouts: Dictionary of timeouts for different components
    """
    
    def __init__(self, metadata: TaskResolverMetadata) -> None:
        """Initialize the ComponentHealthChecker.
        
        Args:
            metadata: Resolver metadata
        """
        super().__init__(metadata, "component_health")
        
        # Load configuration
        default_config = {
            "health_check_interval": 300,  # seconds
            "retention_days": 30,
            "component_timeouts": {
                "default": 10,  # seconds
                "database": 5,
                "api": 30,
                "file_system": 5
            }
        }
        config = self.load_config(default_config)
        
        self.health_check_interval = config["health_check_interval"]
        self.retention_days = config["retention_days"]
        self.component_timeouts = config["component_timeouts"]
    
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
            if operation == "check_component_health":
                return await self._handle_check_component_health(task)
            elif operation == "get_health_history":
                return await self._handle_get_health_history(task)
            elif operation == "check_all_components":
                return await self._handle_check_all_components(task)
            elif operation == "clear_old_health_checks":
                return await self._handle_clear_old_health_checks(task)
            elif operation == "health_check":
                return await self._handle_health_check(task)
            else:
                return self._create_error_result(task, f"Unsupported operation: {operation}")
        
        except Exception as e:
            self.logger.error(f"Error in ComponentHealthChecker: {e}")
            return self._create_error_result(task, f"Internal error: {str(e)}")
    
    async def _handle_check_component_health(self, task: Task) -> TaskResult:
        """Check the health of a specific component.
        
        Args:
            task: The task requesting component health check
            
        Returns:
            A TaskResult containing the health check result
        """
        try:
            # Get required parameters
            component_id = task.input_data.get("component_id")
            if not component_id:
                return self._create_error_result(task, "Missing 'component_id' in input data")
            
            # Get optional parameters
            timeout = task.input_data.get("timeout")
            if not timeout:
                timeout = self.component_timeouts.get(
                    component_id, self.component_timeouts.get("default", 10)
                )
            
            # Perform the health check
            health_check_result = await self._check_component(component_id, timeout)
            
            # Store the health check result
            should_store = task.input_data.get("store_result", True)
            if should_store:
                await self._store_health_check(component_id, health_check_result)
            
            return self._create_success_result(task, health_check_result)
            
        except Exception as e:
            self.logger.error(f"Error checking component health: {e}")
            return self._create_error_result(task, f"Error checking component health: {str(e)}")
    
    async def _handle_get_health_history(self, task: Task) -> TaskResult:
        """Handle the get_health_history operation.
        
        Args:
            task: The task to handle
            
        Returns:
            A TaskResult with the health history and statistics
        """
        if not isinstance(task.input_data, dict):
            return self._create_error_result(task, "Input data must be a dictionary")
        
        component_id = task.input_data.get("component_id")
        if not component_id:
            return self._create_error_result(task, "Component ID is required")
        
        try:
            # Parse the time window and get the cutoff date
            time_window = task.input_data.get("time_window", "24h")
            cutoff_date = self._parse_time_window(time_window)
            
            # Retrieve the health history
            health_history = await self._get_component_health_history(component_id, cutoff_date)
            
            # Calculate statistics
            total_checks = len(health_history)
            healthy_checks = sum(1 for check in health_history if check.get("status") == "healthy")
            
            # Calculate response time statistics if there are response times
            response_times = [
                float(check.get("response_time_ms", 0)) 
                for check in health_history 
                if check.get("response_time_ms") is not None
            ]
            
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0
            
            # Calculate health percentage as a float
            health_percentage: float = 0.0
            if total_checks > 0:
                health_percentage = (healthy_checks / total_checks) * 100.0
            
            return self._create_success_result(task, {
                "component_id": component_id,
                "health_history": health_history,
                "statistics": {
                    "total_checks": total_checks,
                    "healthy_checks": healthy_checks,
                    "unhealthy_checks": total_checks - healthy_checks,
                    "healthy_percent": health_percentage,
                    "avg_response_time_ms": avg_response_time
                }
            })
        
        except Exception as e:
            return self._create_error_result(task, f"Error retrieving health history: {str(e)}")
    
    async def _handle_check_all_components(self, task: Task) -> TaskResult:
        """Check the health of all registered components.
        
        Args:
            task: The task requesting to check all components
            
        Returns:
            A TaskResult containing all health check results
        """
        try:
            # Get the list of components to check
            components = task.input_data.get("components")
            
            if not components:
                # If not specified, get all components that have been checked before
                components = await self._get_all_component_ids()
            
            # If still no components found, return an error
            if not components:
                return self._create_error_result(task, "No components found to check")
            
            # Check each component
            results = {}
            for component_id in components:
                timeout = self.component_timeouts.get(
                    component_id, self.component_timeouts.get("default", 10)
                )
                results[component_id] = await self._check_component(component_id, timeout)
                
                # Store the health check result
                should_store = task.input_data.get("store_results", True)
                if should_store:
                    await self._store_health_check(component_id, results[component_id])
            
            # Calculate overall status
            all_healthy = all(result.get("status") == "healthy" for result in results.values())
            
            return self._create_success_result(task, {
                "overall_status": "healthy" if all_healthy else "unhealthy",
                "component_count": len(results),
                "results": results,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            self.logger.error(f"Error checking all components: {e}")
            return self._create_error_result(task, f"Error checking all components: {str(e)}")
    
    async def _handle_clear_old_health_checks(self, task: Task) -> TaskResult:
        """Clear old health check data.
        
        Args:
            task: The task requesting to clear old health checks
            
        Returns:
            A TaskResult with the result of the operation
        """
        try:
            # Get optional days parameter
            days = task.input_data.get("days", self.retention_days)
            
            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Get all health check files
            removed_count = 0
            for filename in os.listdir(self.data_dir):
                if not filename.startswith("health_") or not filename.endswith(".json"):
                    continue
                
                file_path = os.path.join(self.data_dir, filename)
                file_time = os.path.getmtime(file_path)
                file_date = datetime.fromtimestamp(file_time)
                
                if file_date < cutoff_date:
                    try:
                        os.remove(file_path)
                        removed_count += 1
                    except OSError as e:
                        self.logger.warning(f"Error removing old health check file {filename}: {e}")
            
            return self._create_success_result(task, {
                "message": f"Cleared {removed_count} old health check files",
                "removed_count": removed_count,
                "cutoff_date": cutoff_date.isoformat()
            })
            
        except Exception as e:
            self.logger.error(f"Error clearing old health checks: {e}")
            return self._create_error_result(task, f"Error clearing old health checks: {str(e)}")
    
    async def _handle_health_check(self, task: Task) -> TaskResult:
        """Perform a health check on the ComponentHealthChecker.
        
        Args:
            task: The health check task
            
        Returns:
            A TaskResult with the health check results
        """
        is_healthy = await self.health_check()
        
        return self._create_success_result(task, {
            "status": "healthy" if is_healthy else "unhealthy",
            "component": "ComponentHealthChecker",
            "timestamp": datetime.now().isoformat()
        })
    
    async def _check_component(self, component_id: str, timeout: float) -> Dict[str, Any]:
        """Check the health of a component.
        
        In a real implementation, this would dynamically check different
        components using appropriate methods. For this example, we'll simulate
        health checks.
        
        Args:
            component_id: ID of the component to check
            timeout: Timeout in seconds
            
        Returns:
            A dictionary with the health check result
        """
        # In a real implementation, we would perform an actual health check
        # For this example, we'll simulate using component_id to determine status
        
        timestamp = datetime.now().isoformat()
        
        # Define special components with simulated behaviors
        special_components = {
            "unstable_component": lambda: (0.7 > 0.5, "Simulated 70% reliability"),
            "database": lambda: (True, "Database connection successful"),
            "api": lambda: (True, "API endpoints responding"),
            "file_system": lambda: (True, "File system access verified"),
            "failing_component": lambda: (False, "Component is in a failed state")
        }
        
        # Check if this is a special component
        if component_id in special_components:
            is_healthy, message = special_components[component_id]()
        else:
            # Default component is healthy
            is_healthy = True
            message = f"Component {component_id} is functioning properly"
        
        # Create the health check result
        result = {
            "component_id": component_id,
            "status": "healthy" if is_healthy else "unhealthy",
            "message": message,
            "timestamp": timestamp,
            "response_time_ms": 0  # Placeholder, would be actual response time in real implementation
        }
        
        return result
    
    async def _store_health_check(self, component_id: str, result: Dict[str, Any]) -> None:
        """Store a health check result for a component.
        
        Args:
            component_id: ID of the component
            result: Health check result
        """
        # Load existing health checks for this component
        history_file = f"health_{component_id}.json"
        history_data = self.load_data(history_file) or {"history": []}
        
        # Add new health check
        history = history_data.get("history", [])
        history.append(result)
        
        # Limit history size
        max_history = 1000  # Keep last 1000 health checks
        if len(history) > max_history:
            history = history[-max_history:]
        
        # Update history data
        history_data["history"] = history
        history_data["last_updated"] = datetime.now().isoformat()
        
        # Save updated health checks
        self.store_data(history_file, history_data)
    
    async def _get_component_health_history(
        self, component_id: str, cutoff_date: datetime, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get health check history for a component.
        
        Args:
            component_id: ID of the component
            cutoff_date: Cutoff date for filtering history
            limit: Maximum number of history items to return
            
        Returns:
            List of health check results
        """
        # Load health check history for this component
        history_file = f"health_{component_id}.json"
        history_data = self.load_data(history_file) or {"history": []}
        
        # Get history
        history = history_data.get("history", [])
        
        # Filter by cutoff date
        filtered_history = []
        for check in history:
            if "timestamp" in check:
                try:
                    check_time = datetime.fromisoformat(check["timestamp"])
                    if check_time >= cutoff_date:
                        filtered_history.append(check)
                except (ValueError, TypeError):
                    # Skip checks with invalid timestamps
                    continue
        
        # Sort by timestamp (newest first) and apply limit
        filtered_history.sort(
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )
        
        return filtered_history[:limit]
    
    async def _get_all_component_ids(self) -> List[str]:
        """Get all component IDs that have been checked before.
        
        Returns:
            List of component IDs
        """
        component_ids = []
        
        # Look for health check files
        prefix = "health_"
        suffix = ".json"
        
        for filename in os.listdir(self.data_dir):
            if filename.startswith(prefix) and filename.endswith(suffix):
                # Extract component ID from filename
                component_id = filename[len(prefix):-len(suffix)]
                if component_id:
                    component_ids.append(component_id)
        
        return component_ids
    
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