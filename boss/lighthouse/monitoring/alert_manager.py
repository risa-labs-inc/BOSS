"""AlertManager component for managing system alerts.

This component is responsible for generating, storing, updating, and notifying
about system alerts based on various monitoring conditions.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, cast

from boss.core.task_models import Task, TaskResult, TaskStatus
from boss.lighthouse.monitoring.base_monitoring import BaseMonitoring


class AlertManager(BaseMonitoring):
    """Component for managing system alerts.
    
    This component handles alert generation, storage, notification, and tracking.
    It works with other monitoring components to trigger alerts based on
    system conditions and thresholds.
    
    Attributes:
        alerts: Dictionary storing all active alerts
        alert_history: List of historical alerts
        notification_channels: List of notification channels for alerts
        severity_levels: Dictionary mapping severity levels to their numeric values
    """
    
    def __init__(self, metadata: Any) -> None:
        """Initialize the AlertManager.
        
        Args:
            metadata: Resolver metadata
        """
        super().__init__(metadata, component_name="alert_manager")
        
        # Set up component-specific attributes
        self.logger = logging.getLogger("boss.lighthouse.monitoring.alert_manager")
        
        # Alert storage - in a real implementation, this would be stored in a database
        self.alerts: Dict[str, Dict[str, Any]] = {}
        self.alert_history: List[Dict[str, Any]] = []
        
        # Configure notification channels
        self.notification_channels: List[str] = ["log"]  # Default to just logging
        
        # Define severity levels and their numeric values
        self.severity_levels = {
            "critical": 1,
            "high": 2,
            "medium": 3,
            "low": 4,
            "info": 5
        }
        
        # Define alert retention period in days
        self.alert_retention_days = 30
        
    async def resolve(self, task: Task) -> TaskResult:
        """Resolve alert management tasks.
        
        Args:
            task: The alert management task to resolve
            
        Returns:
            The result of the alert management operation
        """
        if not isinstance(task.input_data, dict):
            return self._create_error_result(task, "Input data must be a dictionary")
            
        operation = task.input_data.get("operation")
        if not operation:
            return self._create_error_result(task, "Missing 'operation' field")
            
        try:
            # Route to the appropriate handler based on the operation
            if operation == "generate_alert":
                return await self._handle_generate_alert(task)
            elif operation == "update_alert":
                return await self._handle_update_alert(task)
            elif operation == "get_active_alerts":
                return await self._handle_get_active_alerts(task)
            elif operation == "get_alert_history":
                return await self._handle_get_alert_history(task)
            elif operation == "acknowledge_alert":
                return await self._handle_acknowledge_alert(task)
            elif operation == "resolve_alert":
                return await self._handle_resolve_alert(task)
            elif operation == "clear_old_alerts":
                return await self._handle_clear_old_alerts(task)
            elif operation == "update_notification_channels":
                return await self._handle_update_notification_channels(task)
            elif operation == "health_check":
                return await self._handle_health_check(task)
            else:
                return self._create_error_result(task, f"Unsupported operation: {operation}")
                
        except Exception as e:
            self.logger.error(f"Error in AlertManager: {e}")
            return self._create_error_result(task, f"Internal error: {str(e)}")
            
    async def _handle_generate_alert(self, task: Task) -> TaskResult:
        """Handle the generate_alert operation.
        
        Args:
            task: The task containing alert details
            
        Returns:
            A TaskResult with the generated alert information
        """
        # Extract required parameters
        component_id = task.input_data.get("component_id")
        if not component_id:
            return self._create_error_result(task, "Missing 'component_id' field")
            
        alert_type = task.input_data.get("alert_type")
        if not alert_type:
            return self._create_error_result(task, "Missing 'alert_type' field")
            
        message = task.input_data.get("message")
        if not message:
            return self._create_error_result(task, "Missing 'message' field")
            
        # Extract optional parameters
        severity = task.input_data.get("severity", "medium")
        details = task.input_data.get("details", {})
        
        # Validate severity
        if severity not in self.severity_levels:
            return self._create_error_result(task, f"Invalid severity: {severity}")
            
        # Generate alert ID
        alert_id = str(uuid.uuid4())
        
        # Create the alert
        alert = {
            "id": alert_id,
            "component_id": component_id,
            "alert_type": alert_type,
            "message": message,
            "severity": severity,
            "severity_level": self.severity_levels[severity],
            "status": "active",
            "details": details,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "acknowledged_at": None,
            "resolved_at": None
        }
        
        # Store the alert
        self.alerts[alert_id] = alert
        
        # Send notifications
        await self._send_alert_notifications(alert)
        
        return self._create_success_result(task, {
            "message": "Alert generated successfully",
            "alert": alert
        })
        
    async def _handle_update_alert(self, task: Task) -> TaskResult:
        """Handle the update_alert operation.
        
        Args:
            task: The task containing update details
            
        Returns:
            A TaskResult with the updated alert information
        """
        # Extract required parameters
        alert_id = task.input_data.get("alert_id")
        if not alert_id:
            return self._create_error_result(task, "Missing 'alert_id' field")
            
        # Check if alert exists
        if alert_id not in self.alerts:
            return self._create_error_result(task, f"Alert not found: {alert_id}")
            
        alert = self.alerts[alert_id]
        
        # Extract optional update fields
        message = task.input_data.get("message")
        severity = task.input_data.get("severity")
        details = task.input_data.get("details")
        status = task.input_data.get("status")
        
        # Update the alert
        if message:
            alert["message"] = message
            
        if severity:
            if severity not in self.severity_levels:
                return self._create_error_result(task, f"Invalid severity: {severity}")
            alert["severity"] = severity
            alert["severity_level"] = self.severity_levels[severity]
            
        if details:
            alert["details"] = details
            
        if status:
            if status not in ["active", "acknowledged", "resolved"]:
                return self._create_error_result(task, f"Invalid status: {status}")
            alert["status"] = status
            
            # Update status-specific timestamps
            if status == "acknowledged" and not alert["acknowledged_at"]:
                alert["acknowledged_at"] = datetime.now().isoformat()
            elif status == "resolved" and not alert["resolved_at"]:
                alert["resolved_at"] = datetime.now().isoformat()
                
                # Move to history if resolved
                self.alert_history.append(alert.copy())
                del self.alerts[alert_id]
                return self._create_success_result(task, {
                    "message": "Alert resolved and moved to history",
                    "alert": alert
                })
                
        # Update the timestamp
        alert["updated_at"] = datetime.now().isoformat()
        
        return self._create_success_result(task, {
            "message": "Alert updated successfully",
            "alert": alert
        })
        
    async def _handle_get_active_alerts(self, task: Task) -> TaskResult:
        """Handle the get_active_alerts operation.
        
        Args:
            task: The task requesting active alerts
            
        Returns:
            A TaskResult with all active alerts
        """
        # Extract optional filters
        component_id = task.input_data.get("component_id")
        severity = task.input_data.get("severity")
        alert_type = task.input_data.get("alert_type")
        
        # Apply filters
        filtered_alerts = list(self.alerts.values())
        
        if component_id:
            filtered_alerts = [a for a in filtered_alerts if a["component_id"] == component_id]
            
        if severity:
            filtered_alerts = [a for a in filtered_alerts if a["severity"] == severity]
            
        if alert_type:
            filtered_alerts = [a for a in filtered_alerts if a["alert_type"] == alert_type]
            
        # Sort by severity level (critical first)
        filtered_alerts.sort(key=lambda a: a["severity_level"])
        
        return self._create_success_result(task, {
            "count": len(filtered_alerts),
            "alerts": filtered_alerts
        })
        
    async def _handle_get_alert_history(self, task: Task) -> TaskResult:
        """Handle the get_alert_history operation.
        
        Args:
            task: The task requesting alert history
            
        Returns:
            A TaskResult with historical alerts
        """
        # Extract optional filters
        component_id = task.input_data.get("component_id")
        severity = task.input_data.get("severity")
        alert_type = task.input_data.get("alert_type")
        time_window = task.input_data.get("time_window", "7d")
        
        # Calculate the cutoff date
        cutoff_date = self._parse_time_window(time_window)
        
        # Get alerts created after the cutoff date
        filtered_history = [
            alert for alert in self.alert_history
            if datetime.fromisoformat(alert["created_at"]) >= cutoff_date
        ]
        
        # Apply additional filters
        if component_id:
            filtered_history = [a for a in filtered_history if a["component_id"] == component_id]
            
        if severity:
            filtered_history = [a for a in filtered_history if a["severity"] == severity]
            
        if alert_type:
            filtered_history = [a for a in filtered_history if a["alert_type"] == alert_type]
            
        # Sort by created_at (newest first)
        filtered_history.sort(key=lambda a: a["created_at"], reverse=True)
        
        return self._create_success_result(task, {
            "count": len(filtered_history),
            "alerts": filtered_history,
            "time_range": {
                "start": cutoff_date.isoformat(),
                "end": datetime.now().isoformat()
            }
        })
        
    async def _handle_acknowledge_alert(self, task: Task) -> TaskResult:
        """Handle the acknowledge_alert operation.
        
        Args:
            task: The task containing the alert to acknowledge
            
        Returns:
            A TaskResult with the acknowledged alert information
        """
        # Extract required parameters
        alert_id = task.input_data.get("alert_id")
        if not alert_id:
            return self._create_error_result(task, "Missing 'alert_id' field")
            
        # Check if alert exists
        if alert_id not in self.alerts:
            return self._create_error_result(task, f"Alert not found: {alert_id}")
            
        alert = self.alerts[alert_id]
        
        # Already acknowledged?
        if alert["status"] == "acknowledged":
            return self._create_success_result(task, {
                "message": "Alert already acknowledged",
                "alert": alert
            })
            
        # Already resolved?
        if alert["status"] == "resolved":
            return self._create_error_result(task, "Cannot acknowledge a resolved alert")
            
        # Update the alert
        alert["status"] = "acknowledged"
        alert["acknowledged_at"] = datetime.now().isoformat()
        alert["updated_at"] = datetime.now().isoformat()
        
        # Add optional acknowledgement message
        ack_message = task.input_data.get("message")
        if ack_message:
            if "acknowledgements" not in alert:
                alert["acknowledgements"] = []
            alert["acknowledgements"].append({
                "timestamp": datetime.now().isoformat(),
                "message": ack_message
            })
            
        return self._create_success_result(task, {
            "message": "Alert acknowledged successfully",
            "alert": alert
        })
        
    async def _handle_resolve_alert(self, task: Task) -> TaskResult:
        """Handle the resolve_alert operation.
        
        Args:
            task: The task containing the alert to resolve
            
        Returns:
            A TaskResult with the resolved alert information
        """
        # Extract required parameters
        alert_id = task.input_data.get("alert_id")
        if not alert_id:
            return self._create_error_result(task, "Missing 'alert_id' field")
            
        # Check if alert exists
        if alert_id not in self.alerts:
            return self._create_error_result(task, f"Alert not found: {alert_id}")
            
        alert = self.alerts[alert_id]
        
        # Already resolved?
        if alert["status"] == "resolved":
            return self._create_success_result(task, {
                "message": "Alert already resolved",
                "alert": alert
            })
            
        # Update the alert
        alert["status"] = "resolved"
        alert["resolved_at"] = datetime.now().isoformat()
        alert["updated_at"] = datetime.now().isoformat()
        
        # Add optional resolution message
        resolution_message = task.input_data.get("message")
        if resolution_message:
            alert["resolution_message"] = resolution_message
            
        # Move to history
        self.alert_history.append(alert.copy())
        del self.alerts[alert_id]
        
        return self._create_success_result(task, {
            "message": "Alert resolved successfully",
            "alert": alert
        })
        
    async def _handle_clear_old_alerts(self, task: Task) -> TaskResult:
        """Handle the clear_old_alerts operation.
        
        Args:
            task: The task with clear parameters
            
        Returns:
            A TaskResult with the number of alerts cleared
        """
        # Extract optional parameters
        retention_days = task.input_data.get("retention_days", self.alert_retention_days)
        
        # Calculate the cutoff date
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        # Count alerts before clearing
        original_count = len(self.alert_history)
        
        # Clear old alerts
        self.alert_history = [
            alert for alert in self.alert_history
            if datetime.fromisoformat(alert["created_at"]) >= cutoff_date
        ]
        
        # Calculate how many were cleared
        cleared_count = original_count - len(self.alert_history)
        
        return self._create_success_result(task, {
            "message": f"{cleared_count} alerts cleared from history",
            "cleared_count": cleared_count,
            "retention_days": retention_days
        })
        
    async def _handle_update_notification_channels(self, task: Task) -> TaskResult:
        """Handle the update_notification_channels operation.
        
        Args:
            task: The task with notification channel updates
            
        Returns:
            A TaskResult with the updated notification channels
        """
        # Extract required parameters
        channels = task.input_data.get("channels")
        if not channels or not isinstance(channels, list):
            return self._create_error_result(task, "Missing or invalid 'channels' field")
            
        # Update the channels
        self.notification_channels = channels
        
        return self._create_success_result(task, {
            "message": "Notification channels updated successfully",
            "channels": self.notification_channels
        })
        
    async def _handle_health_check(self, task: Task) -> TaskResult:
        """Handle the health check operation.
        
        Args:
            task: The health check task
            
        Returns:
            A TaskResult with the health status
        """
        # Perform a simple health check
        health_status = await self.health_check()
        
        if health_status:
            return self._create_success_result(task, {
                "status": "healthy",
                "active_alerts": len(self.alerts),
                "historical_alerts": len(self.alert_history)
            })
        else:
            return self._create_error_result(task, "AlertManager health check failed")
            
    async def health_check(self) -> bool:
        """Perform a health check on the AlertManager.
        
        Returns:
            True if healthy, False otherwise
        """
        # For now, simply return True as the component is stateless
        return True
        
    async def _send_alert_notifications(self, alert: Dict[str, Any]) -> None:
        """Send notifications for a new or updated alert.
        
        Args:
            alert: The alert to send notifications for
        """
        # Log the alert (always done)
        log_level = logging.INFO
        if alert["severity"] == "critical":
            log_level = logging.CRITICAL
        elif alert["severity"] == "high":
            log_level = logging.ERROR
        elif alert["severity"] == "medium":
            log_level = logging.WARNING
            
        self.logger.log(log_level, f"ALERT [{alert['severity']}] {alert['component_id']}: {alert['message']}")
        
        # Check if we need to send to other channels
        for channel in self.notification_channels:
            if channel == "log":
                continue  # Already logged above
            elif channel == "email":
                await self._send_email_notification(alert)
            elif channel == "webhook":
                await self._send_webhook_notification(alert)
            # Add other notification channels as needed
                
    async def _send_email_notification(self, alert: Dict[str, Any]) -> None:
        """Send an email notification for an alert.
        
        Args:
            alert: The alert to send an email for
        """
        # This would be implemented to send an actual email
        self.logger.info(f"Would send email notification for alert {alert['id']}")
        
    async def _send_webhook_notification(self, alert: Dict[str, Any]) -> None:
        """Send a webhook notification for an alert.
        
        Args:
            alert: The alert to send a webhook notification for
        """
        # This would be implemented to send an actual webhook request
        self.logger.info(f"Would send webhook notification for alert {alert['id']}")
        
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