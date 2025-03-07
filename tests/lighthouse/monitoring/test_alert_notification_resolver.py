"""Tests for the AlertNotificationResolver.

This module contains test cases for the AlertNotificationResolver class and its
various notification methods.
"""

import json
import os
import pytest
from unittest.mock import MagicMock, patch, mock_open
from datetime import datetime

from boss.lighthouse.monitoring.alert_notification_resolver import AlertNotificationResolver
from boss.lighthouse.monitoring.alert_manager import AlertManager
from boss.lighthouse.monitoring.metrics_storage import MetricsStorage
from boss.core.task_resolver_metadata import TaskResolverMetadata
from boss.core.task_models import Task, TaskResult, TaskStatus


class TestAlertNotificationResolver:
    """Test cases for the AlertNotificationResolver class."""

    @pytest.fixture
    def metrics_storage(self):
        """Create a MetricsStorage mock for testing."""
        return MagicMock(spec=MetricsStorage)

    @pytest.fixture
    def alert_manager(self, metrics_storage):
        """Create an AlertManager mock for testing."""
        manager = MagicMock(spec=AlertManager)
        manager.return_value = TaskResult(
            task_id="test-task",
            status=TaskStatus.COMPLETED,
            output_data={"alerts": [
                {
                    "id": "alert-1",
                    "component_id": "test-component",
                    "severity": "warning",
                    "message": "Test alert",
                    "timestamp": datetime.now().isoformat(),
                    "details": {"key": "value"}
                }
            ]}
        )
        return manager

    @pytest.fixture
    def resolver(self, metrics_storage, alert_manager, tmp_path):
        """Create an AlertNotificationResolver instance for testing."""
        metadata = TaskResolverMetadata(
            id="test-resolver",
            name="Test Resolver",
            description="Test alert notification resolver",
            version="1.0.0",
            properties={}
        )
        
        # Create a temporary config file
        config_path = os.path.join(tmp_path, "notification_config.json")
        test_config = {
            "email": {
                "enabled": True,
                "smtp_server": "smtp.example.com",
                "smtp_port": 587,
                "smtp_username": "test",
                "smtp_password": "test",
                "from_address": "test@example.com",
                "default_recipients": ["recipient@example.com"]
            },
            "slack": {
                "enabled": True,
                "webhook_url": "https://hooks.slack.com/test",
                "default_channel": "alerts"
            },
            "webhook": {
                "enabled": True,
                "urls": ["https://example.com/webhook"],
                "headers": {"Content-Type": "application/json"}
            }
        }
        
        with open(config_path, 'w') as f:
            json.dump(test_config, f)
        
        resolver = AlertNotificationResolver(
            metadata=metadata,
            metrics_storage=metrics_storage,
            alert_manager=alert_manager,
            config_path=config_path
        )
        
        return resolver

    def test_initialization(self, resolver):
        """Test that the resolver initializes correctly."""
        assert resolver.metrics_storage is not None
        assert resolver.alert_manager is not None
        assert resolver.notification_channels is not None
        assert "email" in resolver.notification_channels
        assert "slack" in resolver.notification_channels
        assert "webhook" in resolver.notification_channels

    def test_load_notification_config(self, resolver, tmp_path):
        """Test loading notification configuration."""
        # Create a test config file
        config_path = os.path.join(tmp_path, "test_config.json")
        test_config = {
            "email": {
                "enabled": True,
                "smtp_server": "test.example.com"
            }
        }
        
        with open(config_path, 'w') as f:
            json.dump(test_config, f)
        
        # Test loading the config
        resolver.config_path = config_path
        config = resolver._load_notification_config()
        
        assert config is not None
        assert "email" in config
        assert config["email"]["enabled"] is True
        assert config["email"]["smtp_server"] == "test.example.com"

    def test_parse_time_window(self, resolver):
        """Test parsing time window strings."""
        assert resolver._parse_time_window("10s") == 10
        assert resolver._parse_time_window("5m") == 300
        assert resolver._parse_time_window("2h") == 7200
        assert resolver._parse_time_window("1d") == 86400
        
        with pytest.raises(ValueError):
            resolver._parse_time_window("invalid")

    @patch("boss.lighthouse.monitoring.alert_notification_resolver.smtplib.SMTP")
    def test_send_email_notification(self, mock_smtp, resolver):
        """Test sending email notifications."""
        # Setup
        recipients = ["test@example.com"]
        content = {
            "subject": "Test Alert",
            "body": "This is a test alert."
        }
        alert = {
            "id": "alert-1",
            "component_id": "test-component",
            "severity": "warning",
            "message": "Test alert"
        }
        
        # Mock SMTP server
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        
        # Test sending email
        result = resolver._send_email_notification(recipients, content, alert)
        
        # Verify
        assert result is True
        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()

    @patch("boss.lighthouse.monitoring.alert_notification_resolver.requests.post")
    def test_send_slack_notification(self, mock_post, resolver):
        """Test sending Slack notifications."""
        # Setup
        channel = "test-channel"
        content = {
            "subject": "Test Alert",
            "body": "This is a test alert."
        }
        alert = {
            "id": "alert-1",
            "component_id": "test-component",
            "severity": "warning",
            "message": "Test alert"
        }
        
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Test sending Slack notification
        result = resolver._send_slack_notification(channel, content, alert)
        
        # Verify
        assert result is True
        mock_post.assert_called_once()
        assert mock_post.call_args[0][0] == "https://hooks.slack.com/test"
        assert "json" in mock_post.call_args[1]
        assert "headers" in mock_post.call_args[1]

    @patch("boss.lighthouse.monitoring.alert_notification_resolver.requests.post")
    def test_send_webhook_notification(self, mock_post, resolver):
        """Test sending webhook notifications."""
        # Setup
        content = {
            "subject": "Test Alert",
            "body": "This is a test alert."
        }
        alert = {
            "id": "alert-1",
            "component_id": "test-component",
            "severity": "warning",
            "message": "Test alert"
        }
        
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Test sending webhook notification
        result = resolver._send_webhook_notification(content, alert)
        
        # Verify
        assert result is True
        mock_post.assert_called_once()
        assert mock_post.call_args[0][0] == "https://example.com/webhook"
        assert "json" in mock_post.call_args[1]
        assert "headers" in mock_post.call_args[1]

    def test_handle_send_notification(self, resolver):
        """Test handling a send notification task."""
        # Setup
        task = Task(
            input_data={
                "operation": "send_notification",
                "alert": {
                    "id": "alert-1",
                    "component_id": "test-component",
                    "severity": "warning",
                    "message": "Test alert",
                    "timestamp": datetime.now().isoformat(),
                    "details": {"key": "value"}
                },
                "channels": ["email", "slack", "webhook"],
                "recipients": ["test@example.com"],
                "template": None,
                "slack_channel": "test-channel"
            },
            metadata={}
        )
        
        # Mock the notification methods
        resolver._send_email_notification = MagicMock(return_value=True)
        resolver._send_slack_notification = MagicMock(return_value=True)
        resolver._send_webhook_notification = MagicMock(return_value=True)
        
        # Test handling the task
        result = resolver._handle_send_notification(task)
        
        # Verify
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["success"] is True
        assert "channel_results" in result.output_data
        assert result.output_data["channel_results"]["email"] is True
        assert result.output_data["channel_results"]["slack"] is True
        assert result.output_data["channel_results"]["webhook"] is True
        
        resolver._send_email_notification.assert_called_once()
        resolver._send_slack_notification.assert_called_once()
        resolver._send_webhook_notification.assert_called_once()

    def test_handle_send_batch_notifications(self, resolver):
        """Test handling a send batch notifications task."""
        # Setup
        task = Task(
            input_data={
                "operation": "send_batch_notifications",
                "alerts": [
                    {
                        "id": "alert-1",
                        "component_id": "test-component",
                        "severity": "warning",
                        "message": "Test alert 1",
                        "timestamp": datetime.now().isoformat(),
                        "details": {"key": "value1"}
                    },
                    {
                        "id": "alert-2",
                        "component_id": "test-component",
                        "severity": "error",
                        "message": "Test alert 2",
                        "timestamp": datetime.now().isoformat(),
                        "details": {"key": "value2"}
                    }
                ],
                "channels": ["email"],
                "recipients": ["test@example.com"],
                "template": None
            },
            metadata={}
        )
        
        # Mock the handle_send_notification method
        resolver._handle_send_notification = MagicMock(return_value=TaskResult(
            task_id="test-task",
            status=TaskStatus.COMPLETED,
            output_data={"success": True, "channel_results": {"email": True}}
        ))
        
        # Test handling the task
        result = resolver._handle_send_batch_notifications(task)
        
        # Verify
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["success"] is True
        assert result.output_data["success_count"] == 2
        assert result.output_data["total_count"] == 2
        assert len(result.output_data["results"]) == 2
        
        assert resolver._handle_send_notification.call_count == 2

    def test_handle_get_active_alerts(self, resolver, alert_manager):
        """Test handling a get active alerts task."""
        # Setup
        task = Task(
            input_data={
                "operation": "get_active_alerts",
                "severity": "warning",
                "component_id": "test-component",
                "time_window": "1h",
                "limit": 10
            },
            metadata={}
        )
        
        # Test handling the task
        result = resolver._handle_get_active_alerts(task)
        
        # Verify
        assert result.status == TaskStatus.COMPLETED
        assert "alerts" in result.output_data
        assert len(result.output_data["alerts"]) == 1
        assert result.output_data["alerts"][0]["id"] == "alert-1"

    def test_resolver_call(self, resolver):
        """Test the resolver's __call__ method."""
        # Setup
        task = Task(
            input_data={
                "operation": "send_notification",
                "alert": {
                    "id": "alert-1",
                    "component_id": "test-component",
                    "severity": "warning",
                    "message": "Test alert"
                },
                "channels": ["email"],
                "recipients": ["test@example.com"]
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
        result = resolver(task)
        
        # Verify
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["success"] is True
        resolver._handle_resolve.assert_called_once_with(task) 