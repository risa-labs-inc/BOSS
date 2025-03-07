"""MonitoringResolver for tracking system health and performance metrics.

This resolver provides monitoring capabilities for the BOSS system, collecting metrics
on component performance, health status, resource usage, and system events. It serves
as a core component of the Lighthouse monitoring infrastructure.

NOTE: This class is being refactored into smaller, more focused components.
See the boss.lighthouse.monitoring package for the newer implementation.
"""

import logging
from typing import Any, Dict, List, Optional, Union, cast
import uuid
from datetime import datetime

from boss.core.task import Task, TaskResult, TaskStatus
from boss.core.resolvers import BaseTaskResolver, TaskResolverMetadata
from boss.core.task_resolver import TaskResolver

# Import the refactored components
try:
    from boss.lighthouse.monitoring import (
        SystemMetricsCollector,
        ComponentHealthChecker,
        PerformanceMetricsTracker,
        AlertManager,
        DashboardGenerator
    )
    REFACTORED_COMPONENTS_AVAILABLE = True
except ImportError:
    REFACTORED_COMPONENTS_AVAILABLE = False


class MonitoringResolver(BaseTaskResolver):
    """Resolver for handling system monitoring operations.
    
    This resolver now acts as a bridge to the refactored components.
    For new development, use the specialized components directly.
    
    Attributes:
        system_metrics_collector: Component for collecting system metrics
        component_health_checker: Component for checking component health
        performance_metrics_tracker: Component for tracking performance metrics
        alert_manager: Component for managing alerts
        dashboard_generator: Component for generating dashboards and reports
    """
    
    def __init__(self, metadata: TaskResolverMetadata) -> None:
        """Initialize the MonitoringResolver.
        
        Args:
            metadata: Resolver metadata
        """
        super().__init__(metadata)
        
        # Set up logging
        self.logger = logging.getLogger("boss.lighthouse.monitoring")
        
        # Initialize component variables with Optional types
        self.system_metrics_collector: Optional[SystemMetricsCollector] = None
        self.component_health_checker: Optional[ComponentHealthChecker] = None
        self.performance_metrics_tracker: Optional[PerformanceMetricsTracker] = None
        self.alert_manager: Optional[AlertManager] = None
        self.dashboard_generator: Optional[DashboardGenerator] = None
        
        # Initialize the refactored components if available
        if REFACTORED_COMPONENTS_AVAILABLE:
            # Initialize SystemMetricsCollector
            system_metrics_metadata = TaskResolverMetadata(
                name="SystemMetricsCollector",
                version=metadata.version,
                description="System metrics collection component"
            )
            self.system_metrics_collector = SystemMetricsCollector(system_metrics_metadata)
            
            # Initialize ComponentHealthChecker
            component_health_metadata = TaskResolverMetadata(
                name="ComponentHealthChecker",
                version=metadata.version,
                description="Component health checking component"
            )
            self.component_health_checker = ComponentHealthChecker(component_health_metadata)
            
            # Initialize PerformanceMetricsTracker
            performance_metrics_metadata = TaskResolverMetadata(
                name="PerformanceMetricsTracker",
                version=metadata.version,
                description="Performance metrics tracking component"
            )
            self.performance_metrics_tracker = PerformanceMetricsTracker(performance_metrics_metadata)
            
            # Initialize AlertManager
            alert_manager_metadata = TaskResolverMetadata(
                name="AlertManager",
                version=metadata.version,
                description="Alert management component"
            )
            self.alert_manager = AlertManager(alert_manager_metadata)
            
            # Initialize DashboardGenerator
            dashboard_generator_metadata = TaskResolverMetadata(
                name="DashboardGenerator",
                version=metadata.version,
                description="Dashboard generation component"
            )
            self.dashboard_generator = DashboardGenerator(dashboard_generator_metadata)
            
            self.logger.info("Using refactored monitoring components")
        else:
            self.logger.warning("Refactored monitoring components not available, using legacy implementation")
    
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
            
            # Route to the appropriate refactored component if available
            if REFACTORED_COMPONENTS_AVAILABLE:
                # System metrics operations
                if operation in ["collect_system_metrics", "get_system_metrics", 
                                "clear_old_metrics", "get_system_info"]:
                    if self.system_metrics_collector:
                        return await self.system_metrics_collector.resolve(task)
                    else:
                        self.logger.error("SystemMetricsCollector is None but REFACTORED_COMPONENTS_AVAILABLE is True")
                
                # Component health operations
                if operation in ["check_component_health", "get_health_history", 
                                "check_all_components", "clear_old_health_checks"]:
                    if self.component_health_checker:
                        return await self.component_health_checker.resolve(task)
                    else:
                        self.logger.error("ComponentHealthChecker is None but REFACTORED_COMPONENTS_AVAILABLE is True")
                
                # Performance metrics operations
                if operation in ["record_performance_metric", "get_performance_metrics", 
                                "analyze_performance_trend"]:
                    if self.performance_metrics_tracker:
                        return await self.performance_metrics_tracker.resolve(task)
                    else:
                        self.logger.error("PerformanceMetricsTracker is None but REFACTORED_COMPONENTS_AVAILABLE is True")
                
                # Alert operations
                if operation in ["generate_alert", "update_alert", "get_active_alerts", 
                                "get_alert_history", "acknowledge_alert", "resolve_alert", 
                                "clear_old_alerts", "update_notification_channels"]:
                    if self.alert_manager:
                        return await self.alert_manager.resolve(task)
                    else:
                        self.logger.error("AlertManager is None but REFACTORED_COMPONENTS_AVAILABLE is True")
                
                # Dashboard operations
                if operation in ["generate_dashboard", "generate_report", "get_dashboard_url", 
                                "list_dashboards"]:
                    if self.dashboard_generator:
                        return await self.dashboard_generator.resolve(task)
                    else:
                        self.logger.error("DashboardGenerator is None but REFACTORED_COMPONENTS_AVAILABLE is True")
                
                # Handle health check operation specially to check all components
                if operation == "health_check":
                    return await self._handle_health_check(task)
            
            # Fall back to the original implementation for operations not yet moved to refactored components
            if operation == "collect_system_metrics":
                # This should never be reached if REFACTORED_COMPONENTS_AVAILABLE is True
                return await self._legacy_handle_collect_system_metrics(task)
            elif operation == "check_component_health":
                # This should never be reached if REFACTORED_COMPONENTS_AVAILABLE is True
                return await self._legacy_handle_check_component_health(task)
            elif operation == "get_performance_metrics":
                # This should never be reached if REFACTORED_COMPONENTS_AVAILABLE is True
                return await self._legacy_handle_get_performance_metrics(task)
            elif operation == "generate_alert":
                return await self._legacy_handle_generate_alert(task)
            elif operation == "list_alerts":
                return await self._legacy_handle_list_alerts(task)
            elif operation == "clear_old_metrics":
                # This should never be reached if REFACTORED_COMPONENTS_AVAILABLE is True
                return await self._legacy_handle_clear_old_metrics(task)
            elif operation == "update_alert_thresholds":
                return await self._legacy_handle_update_alert_thresholds(task)
            elif operation == "get_system_status":
                # This should never be reached if REFACTORED_COMPONENTS_AVAILABLE is True
                return await self._legacy_handle_get_system_status(task)
            elif operation == "health_check":
                # This should never be reached if REFACTORED_COMPONENTS_AVAILABLE is True
                return await self._legacy_handle_health_check(task)
            else:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": f"Unsupported operation: {operation}"}
                )
                
        except Exception as e:
            self.logger.error(f"Error in MonitoringResolver: {e}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={
                    "error": f"Internal error: {str(e)}"
                }
            )
    
    async def _handle_health_check(self, task: Task) -> TaskResult:
        """Check the health of all monitoring components.
        
        Args:
            task: The health check task
            
        Returns:
            A TaskResult with health check results for all components
        """
        component_health = {}
        
        # Check SystemMetricsCollector
        if self.system_metrics_collector:
            component_health["system_metrics_collector"] = await self.system_metrics_collector.health_check()
            
        # Check ComponentHealthChecker
        if self.component_health_checker:
            component_health["component_health_checker"] = await self.component_health_checker.health_check()
            
        # Check PerformanceMetricsTracker
        if self.performance_metrics_tracker:
            component_health["performance_metrics_tracker"] = await self.performance_metrics_tracker.health_check()
            
        # Check AlertManager
        if self.alert_manager:
            component_health["alert_manager"] = await self.alert_manager.health_check()
            
        # Check DashboardGenerator
        if self.dashboard_generator:
            component_health["dashboard_generator"] = await self.dashboard_generator.health_check()
        
        # Overall status is healthy if all components are healthy
        overall_status = all(component_health.values()) if component_health else False
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "status": "healthy" if overall_status else "unhealthy",
                "components": component_health
            }
        )
    
    # Legacy method implementations follow
    # These will be removed as each operation is migrated to a specialized component
    
    async def _legacy_handle_collect_system_metrics(self, task: Task) -> TaskResult:
        """Legacy implementation of collect_system_metrics.
        
        This method is deprecated and will be removed once all clients
        are using the refactored components.
        """
        self.logger.warning("Using legacy implementation of collect_system_metrics")
        # Legacy implementation would go here
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.ERROR,
            output_data={"error": "Legacy implementation not available"}
        )
    
    async def _legacy_handle_check_component_health(self, task: Task) -> TaskResult:
        """Legacy implementation of check_component_health."""
        self.logger.warning("Using legacy implementation of check_component_health")
        # Legacy implementation would go here
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.ERROR,
            output_data={"error": "Legacy implementation not available"}
        )
    
    async def _legacy_handle_get_performance_metrics(self, task: Task) -> TaskResult:
        """Legacy implementation of get_performance_metrics."""
        self.logger.warning("Using legacy implementation of get_performance_metrics")
        # Legacy implementation would go here
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.ERROR,
            output_data={"error": "Legacy implementation not available"}
        )
    
    async def _legacy_handle_generate_alert(self, task: Task) -> TaskResult:
        """Legacy handler for the generate_alert operation.
        
        This method delegates to the AlertManager if available, otherwise
        it provides a simplified implementation.
        
        Args:
            task: The alert generation task
            
        Returns:
            A TaskResult with the generated alert
        """
        if REFACTORED_COMPONENTS_AVAILABLE and self.alert_manager:
            self.logger.info("Delegating generate_alert to AlertManager")
            return await self.alert_manager.resolve(task)
            
        self.logger.warning("Using legacy alert generation - consider using AlertManager")
        
        try:
            # Extract required data
            if not isinstance(task.input_data, dict):
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": "Input data must be a dictionary"}
                )
                
            component_id = task.input_data.get("component_id")
            if not component_id:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": "Missing component_id in input data"}
                )
                
            alert_type = task.input_data.get("alert_type")
            if not alert_type:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": "Missing alert_type in input data"}
                )
                
            message = task.input_data.get("message")
            if not message:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": "Missing message in input data"}
                )
                
            # Generate a simple alert
            alert = {
                "id": str(uuid.uuid4()),
                "component_id": component_id,
                "alert_type": alert_type,
                "message": message,
                "severity": task.input_data.get("severity", "medium"),
                "timestamp": datetime.now().isoformat(),
                "details": task.input_data.get("details", {})
            }
            
            self.logger.warning(f"ALERT: [{alert['severity']}] {component_id}: {message}")
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "message": "Alert generated successfully",
                    "alert": alert
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error in legacy generate_alert: {e}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Internal error: {str(e)}"}
            )
            
    async def _legacy_handle_list_alerts(self, task: Task) -> TaskResult:
        """Legacy handler for the list_alerts operation.
        
        This method delegates to the AlertManager if available, otherwise
        it returns a simplified implementation.
        
        Args:
            task: The list alerts task
            
        Returns:
            A TaskResult with the list of alerts
        """
        if REFACTORED_COMPONENTS_AVAILABLE and self.alert_manager:
            # Translate legacy list_alerts to get_active_alerts for AlertManager
            task_data = task.input_data.copy() if isinstance(task.input_data, dict) else {}
            task_data["operation"] = "get_active_alerts"
            
            new_task = Task(
                id=task.id,
                resolver_name=task.resolver_name,
                input_data=task_data
            )
            
            self.logger.info("Delegating list_alerts to AlertManager.get_active_alerts")
            return await self.alert_manager.resolve(new_task)
            
        self.logger.warning("Using legacy alert listing - consider using AlertManager")
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "alerts": [],
                "message": "Legacy alert listing not implemented. Use AlertManager instead."
            }
        )
        
    async def _legacy_handle_clear_old_metrics(self, task: Task) -> TaskResult:
        """Legacy implementation of clear_old_metrics."""
        self.logger.warning("Using legacy implementation of clear_old_metrics")
        # Legacy implementation would go here
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.ERROR,
            output_data={"error": "Legacy implementation not available"}
        )
    
    async def _legacy_handle_update_alert_thresholds(self, task: Task) -> TaskResult:
        """Legacy handler for the update_alert_thresholds operation.
        
        Args:
            task: The update alert thresholds task
            
        Returns:
            A TaskResult with the updated thresholds
        """
        if REFACTORED_COMPONENTS_AVAILABLE and self.performance_metrics_tracker:
            # Translate to a format understood by PerformanceMetricsTracker
            if isinstance(task.input_data, dict) and "thresholds" in task.input_data:
                thresholds = task.input_data.get("thresholds", {})
                
                # Store thresholds in the performance metrics tracker
                self.performance_metrics_tracker.performance_thresholds = thresholds
                
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data={
                        "message": "Alert thresholds updated successfully",
                        "thresholds": thresholds
                    }
                )
                
        self.logger.warning("Using legacy threshold update - consider using PerformanceMetricsTracker")
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "message": "Legacy threshold updates not fully implemented. Use PerformanceMetricsTracker instead."
            }
        )
    
    async def _legacy_handle_get_system_status(self, task: Task) -> TaskResult:
        """Legacy implementation of get_system_status."""
        self.logger.warning("Using legacy implementation of get_system_status")
        # Legacy implementation would go here
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.ERROR,
            output_data={"error": "Legacy implementation not available"}
        )
    
    async def _legacy_handle_health_check(self, task: Task) -> TaskResult:
        """Legacy implementation of health_check."""
        self.logger.warning("Using legacy implementation of health_check")
        # Legacy implementation would go here
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.ERROR,
            output_data={"error": "Legacy implementation not available"}
        ) 