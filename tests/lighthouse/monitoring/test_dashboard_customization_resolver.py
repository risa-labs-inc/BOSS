"""Tests for the DashboardCustomizationResolver.

This module contains test cases for the DashboardCustomizationResolver class and its
various dashboard customization operations.
"""

import json
import os
import pytest
import shutil
from unittest.mock import MagicMock, patch
from datetime import datetime

from boss.lighthouse.monitoring.dashboard_customization_resolver import DashboardCustomizationResolver
from boss.lighthouse.monitoring.dashboard_generator import DashboardGenerator
from boss.lighthouse.monitoring.chart_generator import ChartGenerator
from boss.lighthouse.monitoring.metrics_storage import MetricsStorage
from boss.core.task_resolver_metadata import TaskResolverMetadata
from boss.core.task_models import Task, TaskResult, TaskStatus


class TestDashboardCustomizationResolver:
    """Test cases for the DashboardCustomizationResolver class."""

    @pytest.fixture
    def data_dir(self, tmp_path):
        """Create a temporary data directory for testing."""
        data_dir = os.path.join(tmp_path, "data")
        os.makedirs(data_dir, exist_ok=True)
        
        # Create subdirectories
        templates_dir = os.path.join(data_dir, "templates")
        dashboards_dir = os.path.join(data_dir, "dashboards")
        custom_dashboards_dir = os.path.join(data_dir, "custom_dashboards")
        
        os.makedirs(templates_dir, exist_ok=True)
        os.makedirs(dashboards_dir, exist_ok=True)
        os.makedirs(custom_dashboards_dir, exist_ok=True)
        
        return data_dir

    @pytest.fixture
    def metrics_storage(self):
        """Create a MetricsStorage mock for testing."""
        storage = MagicMock(spec=MetricsStorage)
        storage.return_value = TaskResult(
            task_id="test-task",
            status=TaskStatus.COMPLETED,
            output_data=[
                {
                    "timestamp": datetime.now().isoformat(),
                    "value": 42,
                    "component_id": "test-component"
                }
            ]
        )
        return storage

    @pytest.fixture
    def dashboard_generator(self):
        """Create a DashboardGenerator mock for testing."""
        generator = MagicMock(spec=DashboardGenerator)
        generator.return_value = TaskResult(
            task_id="test-task",
            status=TaskStatus.COMPLETED,
            output_data={"dashboard_file": "test-dashboard.html"}
        )
        generator.data_dir = "dashboards"
        return generator

    @pytest.fixture
    def chart_generator(self):
        """Create a ChartGenerator mock for testing."""
        generator = MagicMock(spec=ChartGenerator)
        generator.return_value = TaskResult(
            task_id="test-task",
            status=TaskStatus.COMPLETED,
            output_data={"chart_file": "test-chart.png"}
        )
        return generator

    @pytest.fixture
    def resolver(self, data_dir, metrics_storage, dashboard_generator, chart_generator):
        """Create a DashboardCustomizationResolver instance for testing."""
        metadata = TaskResolverMetadata(
            id="test-resolver",
            name="Test Resolver",
            description="Test dashboard customization resolver",
            version="1.0.0",
            properties={}
        )
        
        resolver = DashboardCustomizationResolver(
            metadata=metadata,
            metrics_storage=metrics_storage,
            dashboard_generator=dashboard_generator,
            chart_generator=chart_generator,
            data_dir=data_dir
        )
        
        return resolver

    def test_initialization(self, resolver, data_dir):
        """Test that the resolver initializes correctly."""
        assert resolver.metrics_storage is not None
        assert resolver.dashboard_generator is not None
        assert resolver.chart_generator is not None
        assert resolver.data_dir == data_dir
        assert os.path.exists(resolver.templates_dir)
        assert os.path.exists(resolver.custom_dashboards_dir)

    def test_save_load_dashboard_template(self, resolver):
        """Test saving and loading dashboard templates."""
        # Test template
        template_name = "test_template"
        template_config = {
            "title": "Test Template",
            "description": "A test template",
            "charts": [
                {
                    "title": "Test Chart",
                    "type": "line",
                    "metrics_query": {
                        "metrics_type": "system",
                        "component_id": "test-component"
                    }
                }
            ]
        }
        
        # Save template
        result = resolver._save_dashboard_template(template_name, template_config)
        assert result is True
        
        # Load template
        loaded_template = resolver._load_dashboard_template(template_name)
        assert loaded_template is not None
        assert loaded_template["title"] == template_config["title"]
        assert loaded_template["description"] == template_config["description"]
        assert len(loaded_template["charts"]) == 1
        assert loaded_template["charts"][0]["title"] == template_config["charts"][0]["title"]
        
        # Test invalid template name
        result = resolver._save_dashboard_template("invalid-name!", template_config)
        assert result is False

    def test_save_load_custom_dashboard(self, resolver):
        """Test saving and loading custom dashboards."""
        # Test dashboard
        dashboard_id = "test-dashboard"
        dashboard_config = {
            "title": "Test Dashboard",
            "description": "A test dashboard",
            "charts": [
                {
                    "title": "Test Chart",
                    "type": "line",
                    "metrics_query": {
                        "metrics_type": "system",
                        "component_id": "test-component"
                    }
                }
            ]
        }
        
        # Save dashboard
        result = resolver._save_custom_dashboard(dashboard_id, dashboard_config)
        assert result is True
        
        # Load dashboard
        loaded_dashboard = resolver._load_custom_dashboard(dashboard_id)
        assert loaded_dashboard is not None
        assert loaded_dashboard["title"] == dashboard_config["title"]
        assert loaded_dashboard["description"] == dashboard_config["description"]
        assert len(loaded_dashboard["charts"]) == 1
        assert loaded_dashboard["charts"][0]["title"] == dashboard_config["charts"][0]["title"]
        assert "created_at" in loaded_dashboard
        assert "updated_at" in loaded_dashboard
        assert "version" in loaded_dashboard
        
        # Test invalid dashboard ID
        result = resolver._save_custom_dashboard("invalid_id_with_underscore", dashboard_config)
        assert result is False

    def test_delete_custom_dashboard(self, resolver):
        """Test deleting custom dashboards."""
        # Create a test dashboard
        dashboard_id = "test-dashboard-delete"
        dashboard_config = {
            "title": "Test Dashboard",
            "description": "A test dashboard to delete",
            "charts": []
        }
        
        # Save the dashboard
        resolver._save_custom_dashboard(dashboard_id, dashboard_config)
        
        # Delete the dashboard
        result = resolver._delete_custom_dashboard(dashboard_id)
        assert result is True
        
        # Verify it's deleted
        assert resolver._load_custom_dashboard(dashboard_id) is None
        
        # Test deleting non-existent dashboard
        result = resolver._delete_custom_dashboard("non-existent-dashboard")
        assert result is False

    def test_list_dashboard_templates(self, resolver):
        """Test listing dashboard templates."""
        # Create test templates
        templates = {
            "template1": {"title": "Template 1", "description": "First template", "charts": []},
            "template2": {"title": "Template 2", "description": "Second template", "charts": [{}]}
        }
        
        # Save templates
        for name, config in templates.items():
            resolver._save_dashboard_template(name, config)
        
        # List templates
        template_list = resolver._list_dashboard_templates()
        assert len(template_list) == 2
        
        # Verify template info
        template_names = [t["name"] for t in template_list]
        assert "template1" in template_names
        assert "template2" in template_names
        
        # Verify chart count
        for template in template_list:
            if template["name"] == "template1":
                assert template["chart_count"] == 0
            elif template["name"] == "template2":
                assert template["chart_count"] == 1

    def test_list_custom_dashboards(self, resolver):
        """Test listing custom dashboards."""
        # Create test dashboards
        dashboards = {
            "dashboard1": {"title": "Dashboard 1", "description": "First dashboard", "charts": [], "is_public": True},
            "dashboard2": {"title": "Dashboard 2", "description": "Second dashboard", "charts": [{}], "is_public": False}
        }
        
        # Save dashboards
        for id, config in dashboards.items():
            resolver._save_custom_dashboard(id, config)
        
        # List dashboards
        dashboard_list = resolver._list_custom_dashboards()
        assert len(dashboard_list) == 2
        
        # Verify dashboard info
        dashboard_ids = [d["id"] for d in dashboard_list]
        assert "dashboard1" in dashboard_ids
        assert "dashboard2" in dashboard_ids
        
        # Verify chart count and public status
        for dashboard in dashboard_list:
            if dashboard["id"] == "dashboard1":
                assert dashboard["chart_count"] == 0
                assert dashboard["is_public"] is True
            elif dashboard["id"] == "dashboard2":
                assert dashboard["chart_count"] == 1
                assert dashboard["is_public"] is False

    def test_validate_dashboard_config(self, resolver):
        """Test dashboard configuration validation."""
        # Valid config
        valid_config = {
            "title": "Valid Dashboard",
            "charts": [
                {
                    "title": "Valid Chart",
                    "type": "line",
                    "metrics_query": {
                        "metrics_type": "system"
                    }
                }
            ]
        }
        
        validation = resolver._validate_dashboard_config(valid_config)
        assert validation["valid"] is True
        assert len(validation["errors"]) == 0
        
        # Invalid config - missing title
        invalid_config1 = {
            "charts": [
                {
                    "title": "Valid Chart",
                    "type": "line",
                    "metrics_query": {
                        "metrics_type": "system"
                    }
                }
            ]
        }
        
        validation = resolver._validate_dashboard_config(invalid_config1)
        assert validation["valid"] is False
        assert len(validation["errors"]) == 1
        assert "Missing required field: title" in validation["errors"]
        
        # Invalid config - missing chart title
        invalid_config2 = {
            "title": "Valid Dashboard",
            "charts": [
                {
                    "type": "line",
                    "metrics_query": {
                        "metrics_type": "system"
                    }
                }
            ]
        }
        
        validation = resolver._validate_dashboard_config(invalid_config2)
        assert validation["valid"] is False
        assert len(validation["errors"]) == 1
        assert "Chart 1 is missing required field: title" in validation["errors"]
        
        # Invalid config - invalid chart type
        invalid_config3 = {
            "title": "Valid Dashboard",
            "charts": [
                {
                    "title": "Invalid Chart",
                    "type": "invalid",
                    "metrics_query": {
                        "metrics_type": "system"
                    }
                }
            ]
        }
        
        validation = resolver._validate_dashboard_config(invalid_config3)
        assert validation["valid"] is False
        assert len(validation["errors"]) == 1
        assert "Chart 1 has invalid type: invalid" in validation["errors"]

    def test_handle_create_dashboard(self, resolver):
        """Test handling a create dashboard task."""
        # Setup
        task = Task(
            input_data={
                "operation": "create_dashboard",
                "dashboard_id": "new-dashboard",
                "config": {
                    "title": "New Dashboard",
                    "description": "A new test dashboard",
                    "charts": [
                        {
                            "title": "Test Chart",
                            "type": "line",
                            "metrics_query": {
                                "metrics_type": "system",
                                "component_id": "test-component"
                            }
                        }
                    ]
                }
            },
            metadata={}
        )
        
        # Mock methods
        resolver._save_custom_dashboard = MagicMock(return_value=True)
        resolver._generate_custom_dashboard = MagicMock(return_value="new-dashboard.html")
        
        # Test handling the task
        result = resolver._handle_create_dashboard(task)
        
        # Verify
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["dashboard_id"] == "new-dashboard"
        assert result.output_data["dashboard_path"] == "new-dashboard.html"
        assert "message" in result.output_data
        
        resolver._save_custom_dashboard.assert_called_once()
        resolver._generate_custom_dashboard.assert_called_once_with("new-dashboard")

    def test_handle_update_dashboard(self, resolver):
        """Test handling an update dashboard task."""
        # Setup - create initial dashboard
        dashboard_id = "update-dashboard"
        initial_config = {
            "title": "Initial Dashboard",
            "description": "Initial description",
            "charts": [
                {
                    "title": "Chart 1",
                    "type": "line",
                    "metrics_query": {
                        "metrics_type": "system"
                    }
                }
            ]
        }
        
        resolver._save_custom_dashboard(dashboard_id, initial_config)
        
        # Update task
        task = Task(
            input_data={
                "operation": "update_dashboard",
                "dashboard_id": dashboard_id,
                "updates": {
                    "title": "Updated Dashboard",
                    "charts": [
                        {
                            "title": "Chart 2",
                            "type": "bar",
                            "metrics_query": {
                                "metrics_type": "performance"
                            }
                        }
                    ]
                },
                "replace_charts": True
            },
            metadata={}
        )
        
        # Mock generate method
        resolver._generate_custom_dashboard = MagicMock(return_value="updated-dashboard.html")
        
        # Test handling the task
        result = resolver._handle_update_dashboard(task)
        
        # Verify
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["dashboard_id"] == dashboard_id
        assert result.output_data["dashboard_path"] == "updated-dashboard.html"
        
        # Load the updated dashboard
        updated_dashboard = resolver._load_custom_dashboard(dashboard_id)
        assert updated_dashboard["title"] == "Updated Dashboard"
        assert updated_dashboard["description"] == "Initial description"  # Unchanged
        assert len(updated_dashboard["charts"]) == 1
        assert updated_dashboard["charts"][0]["title"] == "Chart 2"
        assert updated_dashboard["charts"][0]["type"] == "bar"

    def test_handle_delete_dashboard(self, resolver):
        """Test handling a delete dashboard task."""
        # Setup - create dashboard to delete
        dashboard_id = "delete-dashboard"
        config = {
            "title": "Dashboard to Delete",
            "charts": []
        }
        
        resolver._save_custom_dashboard(dashboard_id, config)
        
        # Delete task
        task = Task(
            input_data={
                "operation": "delete_dashboard",
                "dashboard_id": dashboard_id
            },
            metadata={}
        )
        
        # Mock delete method
        original_delete = resolver._delete_custom_dashboard
        resolver._delete_custom_dashboard = MagicMock(return_value=True)
        
        # Test handling the task
        result = resolver._handle_delete_dashboard(task)
        
        # Verify
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["dashboard_id"] == dashboard_id
        assert "message" in result.output_data
        
        resolver._delete_custom_dashboard.assert_called_once_with(dashboard_id)
        
        # Restore method
        resolver._delete_custom_dashboard = original_delete

    def test_handle_get_dashboard(self, resolver):
        """Test handling a get dashboard task."""
        # Setup - create dashboard to get
        dashboard_id = "get-dashboard"
        config = {
            "title": "Dashboard to Get",
            "description": "A dashboard to retrieve",
            "charts": []
        }
        
        resolver._save_custom_dashboard(dashboard_id, config)
        
        # Get task
        task = Task(
            input_data={
                "operation": "get_dashboard",
                "dashboard_id": dashboard_id
            },
            metadata={}
        )
        
        # Test handling the task
        result = resolver._handle_get_dashboard(task)
        
        # Verify
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["dashboard_id"] == dashboard_id
        assert "config" in result.output_data
        assert result.output_data["config"]["title"] == "Dashboard to Get"
        assert result.output_data["config"]["description"] == "A dashboard to retrieve"

    def test_handle_list_dashboards(self, resolver):
        """Test handling a list dashboards task."""
        # Setup - create dashboards to list
        dashboards = {
            "list-dashboard1": {"title": "Dashboard 1", "is_public": True, "charts": []},
            "list-dashboard2": {"title": "Dashboard 2", "is_public": False, "charts": []}
        }
        
        for id, config in dashboards.items():
            resolver._save_custom_dashboard(id, config)
        
        # List task
        task = Task(
            input_data={
                "operation": "list_dashboards"
            },
            metadata={}
        )
        
        # Test handling the task
        result = resolver._handle_list_dashboards(task)
        
        # Verify
        assert result.status == TaskStatus.COMPLETED
        assert "dashboards" in result.output_data
        assert "count" in result.output_data
        assert result.output_data["count"] >= 2  # May have more from other tests
        
        # Test public_only filter
        task = Task(
            input_data={
                "operation": "list_dashboards",
                "public_only": True
            },
            metadata={}
        )
        
        result = resolver._handle_list_dashboards(task)
        public_dashboards = [d for d in result.output_data["dashboards"] 
                            if d["id"] in ["list-dashboard1", "list-dashboard2"]]
        
        assert len(public_dashboards) == 1
        assert public_dashboards[0]["id"] == "list-dashboard1"

    def test_resolver_call(self, resolver):
        """Test the resolver's __call__ method."""
        # Setup
        task = Task(
            input_data={
                "operation": "list_dashboards"
            },
            metadata={}
        )
        
        # Mock the handle_resolve method
        resolver._handle_resolve = MagicMock(return_value=TaskResult(
            task_id="test-task",
            status=TaskStatus.COMPLETED,
            output_data={"dashboards": []}
        ))
        
        # Test calling the resolver
        result = resolver(task)
        
        # Verify
        assert result.status == TaskStatus.COMPLETED
        assert "dashboards" in result.output_data
        resolver._handle_resolve.assert_called_once_with(task) 