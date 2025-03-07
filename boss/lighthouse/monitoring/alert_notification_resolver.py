"""Alert Notification Resolver for customizable alert notifications.

This module provides a TaskResolver for sending alert notifications through
various channels like email, SMS, Slack, or custom webhooks.
"""

import logging
import json
import os
import smtplib
import requests
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from boss.core.task_models import Task, TaskResult, TaskStatus
from boss.core.task_resolver import TaskResolver
from boss.core.task_resolver_metadata import TaskResolverMetadata
from boss.lighthouse.monitoring.metrics_storage import MetricsStorage
from boss.lighthouse.monitoring.alert_manager import AlertManager

logger = logging.getLogger(__name__)

class AlertNotificationResolver(TaskResolver):
    """Resolver for sending customizable alert notifications.
    
    This resolver enables sending notifications for alerts through various
    communication channels like email, SMS, Slack, or custom webhooks.
    
    Attributes:
        metadata: Metadata about this resolver
        metrics_storage: Storage for alert metrics
        alert_manager: Manager for alert rules and status
        notification_channels: Dictionary of configured notification channels
        templates_dir: Directory containing notification templates
    """
    
    def __init__(
        self,
        metadata: TaskResolverMetadata,
        metrics_storage: MetricsStorage,
        alert_manager: Optional[AlertManager] = None,
        config_path: Optional[str] = None
    ) -> None:
        """Initialize the AlertNotificationResolver.
        
        Args:
            metadata: Metadata about this resolver
            metrics_storage: Storage for alert metrics
            alert_manager: Optional alert manager to use (will create one if not provided)
            config_path: Path to notification configuration file
        """
        super().__init__(metadata)
        self.metrics_storage = metrics_storage
        self.alert_manager = alert_manager or AlertManager(metadata, metrics_storage)
        
        # Load notification configuration
        self.config_path = config_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "config",
            "notification_config.json"
        )
        self.notification_channels = self._load_notification_config()
        
        # Set up templates directory
        self.templates_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "templates",
            "notifications"
        )
        os.makedirs(self.templates_dir, exist_ok=True)
        
        logger.info("AlertNotificationResolver initialized")
    
    def _load_notification_config(self) -> Dict[str, Dict[str, Any]]:
        """Load notification configuration from file.
        
        Returns:
            Dictionary of notification channel configurations
        """
        default_config = {
            "email": {
                "enabled": False,
                "smtp_server": "smtp.example.com",
                "smtp_port": 587,
                "smtp_username": "",
                "smtp_password": "",
                "from_address": "alerts@example.com",
                "default_recipients": []
            },
            "slack": {
                "enabled": False,
                "webhook_url": "",
                "default_channel": "alerts"
            },
            "sms": {
                "enabled": False,
                "provider": "twilio",
                "account_sid": "",
                "auth_token": "",
                "from_number": "",
                "default_recipients": []
            },
            "webhook": {
                "enabled": False,
                "urls": [],
                "headers": {}
            }
        }
        
        # Create config file with defaults if it doesn't exist
        if not os.path.exists(self.config_path):
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(default_config, f, indent=2)
            return default_config
        
        # Load config from file
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
            return config
        except Exception as e:
            logger.error(f"Error loading notification config: {e}")
            return default_config
    
    def _parse_time_window(self, time_window: str) -> int:
        """Parse a time window string into seconds.
        
        Args:
            time_window: String like "5m", "1h", "1d"
            
        Returns:
            Number of seconds
        """
        unit = time_window[-1]
        value = int(time_window[:-1])
        
        if unit == "s":
            return value
        elif unit == "m":
            return value * 60
        elif unit == "h":
            return value * 3600
        elif unit == "d":
            return value * 86400
        else:
            raise ValueError(f"Invalid time window unit: {unit}")
    
    def _create_notification_content(
        self, 
        alert: Dict[str, Any], 
        template_name: Optional[str] = None
    ) -> Dict[str, str]:
        """Create notification content from alert data.
        
        Args:
            alert: Alert data
            template_name: Optional template name to use
            
        Returns:
            Dictionary with subject and body for the notification
        """
        severity = alert.get("severity", "unknown").upper()
        component = alert.get("component_id", "unknown")
        timestamp = alert.get("timestamp", datetime.now().isoformat())
        message = alert.get("message", "No message provided")
        details = alert.get("details", {})
        
        # Format timestamp
        try:
            dt = datetime.fromisoformat(timestamp)
            formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            formatted_time = timestamp
        
        # Default content
        subject = f"[{severity}] Alert for {component}"
        body = f"""
Alert Details:
=============
Severity: {severity}
Component: {component}
Time: {formatted_time}
Message: {message}

Additional Details:
{json.dumps(details, indent=2)}
"""
        
        # Use template if provided
        if template_name:
            template_path = os.path.join(self.templates_dir, f"{template_name}.txt")
            if os.path.exists(template_path):
                try:
                    with open(template_path, "r") as f:
                        template = f.read()
                    
                    # Simple template substitution
                    template = template.replace("{severity}", severity)
                    template = template.replace("{component}", component)
                    template = template.replace("{timestamp}", formatted_time)
                    template = template.replace("{message}", message)
                    template = template.replace("{details}", json.dumps(details, indent=2))
                    
                    # Extract subject line (first line)
                    lines = template.split("\n")
                    if lines:
                        subject = lines[0]
                        body = "\n".join(lines[1:])
                except Exception as e:
                    logger.error(f"Error applying template {template_name}: {e}")
        
        return {
            "subject": subject,
            "body": body
        }
    
    def _send_email_notification(
        self, 
        recipients: List[str], 
        content: Dict[str, str],
        alert: Dict[str, Any]
    ) -> bool:
        """Send an email notification.
        
        Args:
            recipients: List of email addresses
            content: Dictionary with subject and body
            alert: Original alert data
            
        Returns:
            True if successful, False otherwise
        """
        config = self.notification_channels.get("email", {})
        if not config.get("enabled", False):
            logger.warning("Email notifications are disabled")
            return False
        
        try:
            msg = MIMEMultipart()
            msg["From"] = config.get("from_address", "alerts@example.com")
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = content["subject"]
            
            # Add body
            msg.attach(MIMEText(content["body"], "plain"))
            
            # Connect to SMTP server
            server = smtplib.SMTP(
                config.get("smtp_server", "smtp.example.com"),
                config.get("smtp_port", 587)
            )
            server.starttls()
            
            # Login if credentials are provided
            username = config.get("smtp_username")
            password = config.get("smtp_password")
            if username and password:
                server.login(username, password)
            
            # Send email
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email notification sent to {len(recipients)} recipients")
            return True
        
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            return False
    
    def _send_slack_notification(
        self,
        channel: Optional[str],
        content: Dict[str, str],
        alert: Dict[str, Any]
    ) -> bool:
        """Send a Slack notification.
        
        Args:
            channel: Optional Slack channel
            content: Dictionary with subject and body
            alert: Original alert data
            
        Returns:
            True if successful, False otherwise
        """
        config = self.notification_channels.get("slack", {})
        if not config.get("enabled", False):
            logger.warning("Slack notifications are disabled")
            return False
        
        webhook_url = config.get("webhook_url", "")
        if not webhook_url:
            logger.error("Slack webhook URL not configured")
            return False
        
        try:
            # Determine channel
            target_channel = channel or config.get("default_channel", "alerts")
            
            # Format message
            severity = alert.get("severity", "unknown").upper()
            severity_emoji = {
                "CRITICAL": ":red_circle:",
                "ERROR": ":rotating_light:",
                "WARNING": ":warning:",
                "INFO": ":information_source:"
            }.get(severity, ":bell:")
            
            # Create Slack payload
            payload = {
                "channel": f"#{target_channel}",
                "username": "BOSS Alert System",
                "text": f"{severity_emoji} *{content['subject']}*",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*{content['subject']}*"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": content['body']
                        }
                    }
                ]
            }
            
            # Send to Slack
            response = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                logger.info(f"Slack notification sent to channel {target_channel}")
                return True
            else:
                logger.error(f"Error sending Slack notification: {response.status_code} {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
            return False
    
    def _send_webhook_notification(
        self,
        content: Dict[str, str],
        alert: Dict[str, Any]
    ) -> bool:
        """Send a webhook notification.
        
        Args:
            content: Dictionary with subject and body
            alert: Original alert data
            
        Returns:
            True if successful, False otherwise
        """
        config = self.notification_channels.get("webhook", {})
        if not config.get("enabled", False):
            logger.warning("Webhook notifications are disabled")
            return False
        
        urls = config.get("urls", [])
        if not urls:
            logger.error("No webhook URLs configured")
            return False
        
        try:
            # Create payload
            payload = {
                "alert": alert,
                "subject": content["subject"],
                "body": content["body"],
                "timestamp": datetime.now().isoformat()
            }
            
            # Get headers
            headers = config.get("headers", {})
            if not headers:
                headers = {"Content-Type": "application/json"}
            
            # Send to all configured webhooks
            success_count = 0
            for url in urls:
                try:
                    response = requests.post(url, json=payload, headers=headers)
                    if response.status_code >= 200 and response.status_code < 300:
                        success_count += 1
                    else:
                        logger.error(f"Error sending webhook to {url}: {response.status_code} {response.text}")
                except Exception as e:
                    logger.error(f"Error sending webhook to {url}: {e}")
            
            logger.info(f"Webhook notifications sent to {success_count}/{len(urls)} endpoints")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error sending webhook notifications: {e}")
            return False
    
    def _handle_send_notification(self, task: Task) -> TaskResult:
        """Handle sending a notification for a single alert.
        
        Args:
            task: Task containing alert data and notification channels
            
        Returns:
            Task result
        """
        input_data = task.input_data
        alert_data = input_data.get("alert", {})
        channels = input_data.get("channels", [])
        recipients = input_data.get("recipients", [])
        template = input_data.get("template")
        
        if not alert_data:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error="No alert data provided"
            )
        
        # Create notification content
        content = self._create_notification_content(alert_data, template)
        
        # Track results
        results = {}
        success = False
        
        # Send to each requested channel
        for channel in channels:
            if channel == "email":
                # Use provided recipients or default
                email_recipients = recipients or self.notification_channels.get("email", {}).get("default_recipients", [])
                if email_recipients:
                    results["email"] = self._send_email_notification(email_recipients, content, alert_data)
                    success = success or results["email"]
                else:
                    results["email"] = False
                    logger.warning("No email recipients specified")
            
            elif channel == "slack":
                slack_channel = input_data.get("slack_channel")
                results["slack"] = self._send_slack_notification(slack_channel, content, alert_data)
                success = success or results["slack"]
            
            elif channel == "webhook":
                results["webhook"] = self._send_webhook_notification(content, alert_data)
                success = success or results["webhook"]
            
            elif channel == "sms":
                # SMS implementation would go here
                results["sms"] = False
                logger.warning("SMS notifications not yet implemented")
            
            else:
                logger.warning(f"Unknown notification channel: {channel}")
        
        # Return result
        if success:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "success": True,
                    "channel_results": results
                }
            )
        else:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error="Failed to send notifications to any channel",
                output_data={"channel_results": results}
            )
    
    def _handle_send_batch_notifications(self, task: Task) -> TaskResult:
        """Handle sending notifications for multiple alerts.
        
        Args:
            task: Task containing multiple alerts and notification settings
            
        Returns:
            Task result
        """
        input_data = task.input_data
        alerts = input_data.get("alerts", [])
        channels = input_data.get("channels", [])
        recipients = input_data.get("recipients", [])
        template = input_data.get("template")
        
        if not alerts:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error="No alerts provided"
            )
        
        # Track results for each alert
        results = []
        success_count = 0
        
        # Process each alert
        for alert in alerts:
            # Create subtask for each alert
            subtask = Task(
                input_data={
                    "alert": alert,
                    "channels": channels,
                    "recipients": recipients,
                    "template": template,
                    "slack_channel": input_data.get("slack_channel")
                },
                metadata=task.metadata
            )
            
            # Process the subtask
            result = self._handle_send_notification(subtask)
            
            # Track results
            alert_result = {
                "alert_id": alert.get("id", "unknown"),
                "success": result.status.is_success(),
                "channel_results": result.output_data.get("channel_results", {}) if result.output_data else {}
            }
            results.append(alert_result)
            
            if result.status.is_success():
                success_count += 1
        
        # Return overall result
        if success_count > 0:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "success": True,
                    "success_count": success_count,
                    "total_count": len(alerts),
                    "results": results
                }
            )
        else:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error="Failed to send notifications for any alerts",
                output_data={
                    "success_count": 0,
                    "total_count": len(alerts),
                    "results": results
                }
            )
    
    def _handle_get_active_alerts(self, task: Task) -> TaskResult:
        """Get active alerts from the alert manager.
        
        Args:
            task: Task containing filter criteria
            
        Returns:
            Task result with active alerts
        """
        input_data = task.input_data
        severity = input_data.get("severity")
        component_id = input_data.get("component_id")
        time_window = input_data.get("time_window", "24h")
        limit = input_data.get("limit", 100)
        
        try:
            # Get alerts from alert manager
            alerts_task = Task(
                input_data={
                    "operation": "get_active_alerts",
                    "severity": severity,
                    "component_id": component_id,
                    "time_window": time_window,
                    "limit": limit
                },
                metadata=task.metadata
            )
            
            alerts_result = self.alert_manager(alerts_task)
            
            if not alerts_result.status.is_success():
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.FAILED,
                    error=f"Failed to retrieve alerts: {alerts_result.error}"
                )
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data=alerts_result.output_data
            )
            
        except Exception as e:
            logger.error(f"Error retrieving active alerts: {e}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error=f"Error retrieving active alerts: {str(e)}"
            )
    
    def _handle_notification_config(self, task: Task) -> TaskResult:
        """Handle notification configuration operations.
        
        Args:
            task: Task containing operation details
            
        Returns:
            Task result
        """
        input_data = task.input_data
        operation = input_data.get("config_operation")
        
        if operation == "get":
            # Return current configuration
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data=self.notification_channels
            )
            
        elif operation == "update":
            # Update configuration
            channel = input_data.get("channel")
            config = input_data.get("config", {})
            
            if not channel or not config:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.FAILED,
                    error="Channel and config are required for update operation"
                )
            
            try:
                # Update the specified channel
                if channel in self.notification_channels:
                    self.notification_channels[channel].update(config)
                else:
                    self.notification_channels[channel] = config
                
                # Save the updated configuration
                with open(self.config_path, "w") as f:
                    json.dump(self.notification_channels, f, indent=2)
                
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output_data={
                        "success": True,
                        "message": f"Configuration for channel '{channel}' updated",
                        "updated_config": self.notification_channels[channel]
                    }
                )
                
            except Exception as e:
                logger.error(f"Error updating notification config: {e}")
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.FAILED,
                    error=f"Error updating notification config: {str(e)}"
                )
                
        else:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error=f"Unknown config operation: {operation}"
            )
    
    def _handle_resolve(self, task: Task) -> TaskResult:
        """Main handler for the AlertNotificationResolver.
        
        Args:
            task: Task to resolve
            
        Returns:
            Task result
        """
        operation = task.input_data.get("operation", "")
        
        if operation == "send_notification":
            return self._handle_send_notification(task)
        
        elif operation == "send_batch_notifications":
            return self._handle_send_batch_notifications(task)
        
        elif operation == "get_active_alerts":
            return self._handle_get_active_alerts(task)
        
        elif operation == "notification_config":
            return self._handle_notification_config(task)
        
        else:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error=f"Unknown operation: {operation}"
            )
    
    def __call__(self, task: Task) -> TaskResult:
        """Resolve the given task by sending alert notifications.
        
        Args:
            task: Task to resolve
            
        Returns:
            Task result
        """
        try:
            return self._handle_resolve(task)
        except Exception as e:
            logger.error(f"Error in AlertNotificationResolver: {e}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error=f"Error in AlertNotificationResolver: {str(e)}"
            ) 