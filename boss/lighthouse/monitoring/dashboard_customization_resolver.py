"""Dashboard Customization Resolver for user-defined dashboards.

This module provides a TaskResolver for creating, managing, and applying
customizations to monitoring dashboards, allowing users to define their own
dashboard layouts, metrics, and visualizations.
"""

import logging
import json
import os
import re
from typing import Any, Dict, List, Optional, Union, cast
from datetime import datetime
import shutil

from boss.core.task_models import Task, TaskResult, TaskStatus
from boss.core.task_resolver import TaskResolver
from boss.core.task_resolver_metadata import TaskResolverMetadata
from boss.lighthouse.monitoring.metrics_storage import MetricsStorage
from boss.lighthouse.monitoring.dashboard_generator import DashboardGenerator
from boss.lighthouse.monitoring.chart_generator import ChartGenerator

logger = logging.getLogger(__name__)

class DashboardCustomizationResolver(TaskResolver):
    """Resolver for customizing monitoring dashboards.
    
    This resolver enables users to create, manage, and apply custom dashboard 
    configurations, including layouts, chart types, and displayed metrics.
    
    Attributes:
        metadata: Metadata about this resolver
        metrics_storage: Storage for metrics data
        dashboard_generator: Generator for creating dashboard visualizations
        chart_generator: Generator for creating chart visualizations
        templates_dir: Directory containing dashboard templates
        custom_dashboards_dir: Directory for storing custom dashboard configurations
    """
    
    def __init__(
        self,
        metadata: TaskResolverMetadata,
        metrics_storage: MetricsStorage,
        dashboard_generator: Optional[DashboardGenerator] = None,
        chart_generator: Optional[ChartGenerator] = None,
        data_dir: Optional[str] = None
    ) -> None:
        """Initialize the DashboardCustomizationResolver.
        
        Args:
            metadata: Metadata about this resolver
            metrics_storage: Storage for metrics data
            dashboard_generator: Optional dashboard generator to use
            chart_generator: Optional chart generator to use
            data_dir: Base directory for data storage
        """
        super().__init__(metadata)
        self.metrics_storage = metrics_storage
        
        # Set up directories
        self.data_dir = data_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "data"
        )
        
        self.templates_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "templates",
            "dashboards"
        )
        
        self.custom_dashboards_dir = os.path.join(
            self.data_dir,
            "custom_dashboards"
        )
        
        # Create directories if they don't exist
        os.makedirs(self.templates_dir, exist_ok=True)
        os.makedirs(self.custom_dashboards_dir, exist_ok=True)
        
        # Initialize generators
        if dashboard_generator:
            self.dashboard_generator = dashboard_generator
        else:
            dashboards_dir = os.path.join(self.data_dir, "dashboards")
            os.makedirs(dashboards_dir, exist_ok=True)
            self.dashboard_generator = DashboardGenerator(
                data_dir=dashboards_dir,
                metrics_storage=self.metrics_storage
            )
        
        self.chart_generator = chart_generator or ChartGenerator()
        
        logger.info("DashboardCustomizationResolver initialized")
    
    def _load_dashboard_template(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Load a dashboard template.
        
        Args:
            template_name: Name of the template to load
            
        Returns:
            Template configuration or None if not found
        """
        template_path = os.path.join(self.templates_dir, f"{template_name}.json")
        if not os.path.exists(template_path):
            logger.warning(f"Template '{template_name}' not found")
            return None
        
        try:
            with open(template_path, "r") as f:
                template = json.load(f)
            return template
        except Exception as e:
            logger.error(f"Error loading template '{template_name}': {e}")
            return None
    
    def _save_dashboard_template(self, template_name: str, config: Dict[str, Any]) -> bool:
        """Save a dashboard template.
        
        Args:
            template_name: Name of the template to save
            config: Template configuration
            
        Returns:
            True if successful, False otherwise
        """
        # Ensure valid template name (alphanumeric and underscores only)
        if not re.match(r'^[a-zA-Z0-9_]+$', template_name):
            logger.error(f"Invalid template name: '{template_name}'. Use only letters, numbers, and underscores.")
            return False
        
        template_path = os.path.join(self.templates_dir, f"{template_name}.json")
        
        try:
            with open(template_path, "w") as f:
                json.dump(config, f, indent=2)
            logger.info(f"Template '{template_name}' saved")
            return True
        except Exception as e:
            logger.error(f"Error saving template '{template_name}': {e}")
            return False
    
    def _load_custom_dashboard(self, dashboard_id: str) -> Optional[Dict[str, Any]]:
        """Load a custom dashboard configuration.
        
        Args:
            dashboard_id: ID of the dashboard to load
            
        Returns:
            Dashboard configuration or None if not found
        """
        dashboard_path = os.path.join(self.custom_dashboards_dir, f"{dashboard_id}.json")
        if not os.path.exists(dashboard_path):
            logger.warning(f"Custom dashboard '{dashboard_id}' not found")
            return None
        
        try:
            with open(dashboard_path, "r") as f:
                dashboard = json.load(f)
            return dashboard
        except Exception as e:
            logger.error(f"Error loading custom dashboard '{dashboard_id}': {e}")
            return None
    
    def _save_custom_dashboard(self, dashboard_id: str, config: Dict[str, Any]) -> bool:
        """Save a custom dashboard configuration.
        
        Args:
            dashboard_id: ID of the dashboard to save
            config: Dashboard configuration
            
        Returns:
            True if successful, False otherwise
        """
        # Ensure valid dashboard ID (alphanumeric and hyphens only)
        if not re.match(r'^[a-zA-Z0-9-]+$', dashboard_id):
            logger.error(f"Invalid dashboard ID: '{dashboard_id}'. Use only letters, numbers, and hyphens.")
            return False
        
        dashboard_path = os.path.join(self.custom_dashboards_dir, f"{dashboard_id}.json")
        
        try:
            # Add timestamp and version
            config["updated_at"] = datetime.now().isoformat()
            if "created_at" not in config:
                config["created_at"] = config["updated_at"]
            config["version"] = config.get("version", 0) + 1
            
            with open(dashboard_path, "w") as f:
                json.dump(config, f, indent=2)
            logger.info(f"Custom dashboard '{dashboard_id}' saved")
            return True
        except Exception as e:
            logger.error(f"Error saving custom dashboard '{dashboard_id}': {e}")
            return False
    
    def _delete_custom_dashboard(self, dashboard_id: str) -> bool:
        """Delete a custom dashboard configuration.
        
        Args:
            dashboard_id: ID of the dashboard to delete
            
        Returns:
            True if successful, False otherwise
        """
        dashboard_path = os.path.join(self.custom_dashboards_dir, f"{dashboard_id}.json")
        if not os.path.exists(dashboard_path):
            logger.warning(f"Custom dashboard '{dashboard_id}' not found")
            return False
        
        try:
            os.remove(dashboard_path)
            logger.info(f"Custom dashboard '{dashboard_id}' deleted")
            
            # Also delete generated HTML file if it exists
            html_path = os.path.join(self.dashboard_generator.data_dir, f"{dashboard_id}.html")
            if os.path.exists(html_path):
                os.remove(html_path)
                logger.info(f"Generated dashboard file '{dashboard_id}.html' deleted")
            
            return True
        except Exception as e:
            logger.error(f"Error deleting custom dashboard '{dashboard_id}': {e}")
            return False
    
    def _list_dashboard_templates(self) -> List[Dict[str, Any]]:
        """List available dashboard templates.
        
        Returns:
            List of template metadata
        """
        templates = []
        try:
            for filename in os.listdir(self.templates_dir):
                if filename.endswith(".json"):
                    template_name = filename[:-5]  # Remove .json extension
                    template_path = os.path.join(self.templates_dir, filename)
                    
                    try:
                        with open(template_path, "r") as f:
                            template = json.load(f)
                        
                        templates.append({
                            "name": template_name,
                            "title": template.get("title", template_name),
                            "description": template.get("description", ""),
                            "chart_count": len(template.get("charts", [])),
                            "last_modified": datetime.fromtimestamp(os.path.getmtime(template_path)).isoformat()
                        })
                    except Exception as e:
                        logger.error(f"Error reading template '{template_name}': {e}")
                        
            return templates
        except Exception as e:
            logger.error(f"Error listing dashboard templates: {e}")
            return []
    
    def _list_custom_dashboards(self) -> List[Dict[str, Any]]:
        """List available custom dashboards.
        
        Returns:
            List of dashboard metadata
        """
        dashboards = []
        try:
            for filename in os.listdir(self.custom_dashboards_dir):
                if filename.endswith(".json"):
                    dashboard_id = filename[:-5]  # Remove .json extension
                    dashboard_path = os.path.join(self.custom_dashboards_dir, filename)
                    
                    try:
                        with open(dashboard_path, "r") as f:
                            dashboard = json.load(f)
                        
                        dashboards.append({
                            "id": dashboard_id,
                            "title": dashboard.get("title", dashboard_id),
                            "description": dashboard.get("description", ""),
                            "created_at": dashboard.get("created_at", ""),
                            "updated_at": dashboard.get("updated_at", ""),
                            "version": dashboard.get("version", 1),
                            "chart_count": len(dashboard.get("charts", [])),
                            "is_public": dashboard.get("is_public", False)
                        })
                    except Exception as e:
                        logger.error(f"Error reading dashboard '{dashboard_id}': {e}")
                        
            return dashboards
        except Exception as e:
            logger.error(f"Error listing custom dashboards: {e}")
            return []
    
    def _generate_custom_dashboard(self, dashboard_id: str) -> Optional[str]:
        """Generate HTML for a custom dashboard.
        
        Args:
            dashboard_id: ID of the dashboard to generate
            
        Returns:
            Path to the generated HTML file, or None if failed
        """
        # Load dashboard configuration
        dashboard_config = self._load_custom_dashboard(dashboard_id)
        if not dashboard_config:
            logger.error(f"Failed to load dashboard config for '{dashboard_id}'")
            return None
        
        try:
            # Get dashboard data
            title = dashboard_config.get("title", f"Custom Dashboard {dashboard_id}")
            description = dashboard_config.get("description", "")
            charts = dashboard_config.get("charts", [])
            layout = dashboard_config.get("layout", "grid")
            
            if not charts:
                logger.error(f"No charts defined in dashboard '{dashboard_id}'")
                return None
            
            # Generate charts
            chart_data = []
            for chart_config in charts:
                chart_type = chart_config.get("type", "line")
                chart_title = chart_config.get("title", "")
                metrics_query = chart_config.get("metrics_query", {})
                
                # Skip invalid chart configs
                if not metrics_query:
                    logger.warning(f"Skipping chart with no metrics query: {chart_title}")
                    continue
                
                # Get metrics data
                metrics_task = Task(
                    input_data={
                        "operation": "get_metrics",
                        "metrics_type": metrics_query.get("metrics_type", ""),
                        "component_id": metrics_query.get("component_id", ""),
                        "start_time": metrics_query.get("start_time", ""),
                        "end_time": metrics_query.get("end_time", ""),
                        "limit": metrics_query.get("limit", 1000)
                    },
                    metadata={"source": "dashboard_customization"}
                )
                
                metrics_result = self.metrics_storage(metrics_task)
                
                if not hasattr(metrics_result, 'status') or not metrics_result.status.is_success():
                    logger.warning(f"Failed to get metrics for chart '{chart_title}': {getattr(metrics_result, 'error', 'Unknown error')}")
                    continue
                
                metrics_data = metrics_result.output_data
                
                # Generate chart
                chart_task = Task(
                    input_data={
                        "operation": "generate_chart",
                        "chart_type": chart_type,
                        "title": chart_title,
                        "data": metrics_data,
                        "options": chart_config.get("options", {})
                    },
                    metadata={"source": "dashboard_customization"}
                )
                
                chart_result = self.chart_generator(chart_task)
                
                if not hasattr(chart_result, 'status') or not chart_result.status.is_success():
                    logger.warning(f"Failed to generate chart '{chart_title}': {getattr(chart_result, 'error', 'Unknown error')}")
                    continue
                
                chart_data.append({
                    "title": chart_title,
                    "chart_file": chart_result.output_data.get("chart_file", ""),
                    "description": chart_config.get("description", ""),
                    "width": chart_config.get("width", "100%"),
                    "height": chart_config.get("height", "400px")
                })
            
            if not chart_data:
                logger.error(f"No charts could be generated for dashboard '{dashboard_id}'")
                return None
            
            # Generate dashboard HTML
            dashboard_task = Task(
                input_data={
                    "operation": "generate_custom_dashboard",
                    "dashboard_id": dashboard_id,
                    "title": title,
                    "description": description,
                    "charts": chart_data,
                    "layout": layout,
                    "custom_css": dashboard_config.get("custom_css", ""),
                    "custom_js": dashboard_config.get("custom_js", "")
                },
                metadata={"source": "dashboard_customization"}
            )
            
            dashboard_result = self.dashboard_generator(dashboard_task)
            
            if not hasattr(dashboard_result, 'status') or not dashboard_result.status.is_success():
                logger.error(f"Failed to generate dashboard '{dashboard_id}': {getattr(dashboard_result, 'error', 'Unknown error')}")
                return None
            
            dashboard_path = dashboard_result.output_data.get("dashboard_file", "")
            logger.info(f"Generated custom dashboard at {dashboard_path}")
            return dashboard_path
            
        except Exception as e:
            logger.error(f"Error generating custom dashboard '{dashboard_id}': {e}")
            return None
    
    def _validate_dashboard_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a dashboard configuration.
        
        Args:
            config: Dashboard configuration to validate
            
        Returns:
            Dict containing validation result and errors if any
        """
        errors = []
        
        # Validate required fields
        if "title" not in config:
            errors.append("Missing required field: title")
        
        if "charts" not in config or not isinstance(config["charts"], list):
            errors.append("Missing or invalid charts array")
        else:
            # Validate each chart configuration
            for i, chart in enumerate(config["charts"]):
                if not isinstance(chart, dict):
                    errors.append(f"Chart {i+1} is not a valid object")
                    continue
                
                if "title" not in chart:
                    errors.append(f"Chart {i+1} is missing required field: title")
                
                if "type" not in chart:
                    errors.append(f"Chart {i+1} is missing required field: type")
                elif chart["type"] not in ["line", "bar", "pie", "scatter", "area", "table"]:
                    errors.append(f"Chart {i+1} has invalid type: {chart['type']}")
                
                if "metrics_query" not in chart or not isinstance(chart["metrics_query"], dict):
                    errors.append(f"Chart {i+1} is missing or has invalid metrics_query")
                else:
                    metrics_query = chart["metrics_query"]
                    if "metrics_type" not in metrics_query:
                        errors.append(f"Chart {i+1} metrics_query is missing required field: metrics_type")
        
        # Return validation result
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _handle_create_dashboard(self, task: Task) -> TaskResult:
        """Handle creating a new custom dashboard.
        
        Args:
            task: Task containing dashboard configuration
            
        Returns:
            Task result with dashboard ID
        """
        input_data = task.input_data
        config = input_data.get("config", {})
        dashboard_id = input_data.get("dashboard_id", "")
        template_name = input_data.get("template", "")
        
        # Generate a dashboard ID if not provided
        if not dashboard_id:
            dashboard_id = f"custom-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Use template if specified
        if template_name:
            template = self._load_dashboard_template(template_name)
            if template:
                # Merge template with provided config
                template_config = template.copy()
                for key, value in config.items():
                    template_config[key] = value
                config = template_config
            else:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.FAILED,
                    output_data={"error": f"Template '{template_name}' not found"}
                )
        
        # Validate configuration
        validation = self._validate_dashboard_config(config)
        if not validation["valid"]:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"errors": validation["errors"]}
            )
        
        # Save dashboard configuration
        if not self._save_custom_dashboard(dashboard_id, config):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"error": f"Failed to save dashboard '{dashboard_id}'"}
            )
        
        # Generate dashboard HTML
        dashboard_path = self._generate_custom_dashboard(dashboard_id)
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "dashboard_id": dashboard_id,
                "dashboard_path": dashboard_path,
                "title": config.get("title", ""),
                "message": f"Dashboard '{dashboard_id}' created successfully"
            }
        )
    
    def _handle_update_dashboard(self, task: Task) -> TaskResult:
        """Handle updating an existing custom dashboard.
        
        Args:
            task: Task containing dashboard updates
            
        Returns:
            Task result with updated dashboard info
        """
        input_data = task.input_data
        dashboard_id = input_data.get("dashboard_id", "")
        updates = input_data.get("updates", {})
        
        if not dashboard_id:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"error": "Dashboard ID is required"}
            )
        
        # Load existing dashboard
        existing_config = self._load_custom_dashboard(dashboard_id)
        if not existing_config:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"error": f"Dashboard '{dashboard_id}' not found"}
            )
        
        # Apply updates
        updated_config = existing_config.copy()
        for key, value in updates.items():
            if key == "charts" and isinstance(value, list) and isinstance(updated_config.get("charts"), list):
                # Handle chart updates/additions
                if input_data.get("replace_charts", False):
                    # Replace all charts
                    updated_config["charts"] = value
                else:
                    # Update or add charts by title
                    existing_charts = {chart.get("title", f"chart-{i}"): chart 
                                      for i, chart in enumerate(updated_config["charts"])}
                    
                    for new_chart in value:
                        title = new_chart.get("title", "")
                        if title in existing_charts:
                            # Update existing chart
                            existing_charts[title].update(new_chart)
                        else:
                            # Add new chart
                            updated_config["charts"].append(new_chart)
            else:
                # Regular field update
                updated_config[key] = value
        
        # Validate updated configuration
        validation = self._validate_dashboard_config(updated_config)
        if not validation["valid"]:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"errors": validation["errors"]}
            )
        
        # Save updated dashboard configuration
        if not self._save_custom_dashboard(dashboard_id, updated_config):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"error": f"Failed to save updated dashboard '{dashboard_id}'"}
            )
        
        # Generate updated dashboard HTML
        dashboard_path = self._generate_custom_dashboard(dashboard_id)
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "dashboard_id": dashboard_id,
                "dashboard_path": dashboard_path,
                "title": updated_config.get("title", ""),
                "message": f"Dashboard '{dashboard_id}' updated successfully"
            }
        )
    
    def _handle_delete_dashboard(self, task: Task) -> TaskResult:
        """Handle deleting a custom dashboard.
        
        Args:
            task: Task containing dashboard ID
            
        Returns:
            Task result with deletion status
        """
        input_data = task.input_data
        dashboard_id = input_data.get("dashboard_id", "")
        
        if not dashboard_id:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"error": "Dashboard ID is required"}
            )
        
        # Delete dashboard configuration and generated HTML
        if not self._delete_custom_dashboard(dashboard_id):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"error": f"Failed to delete dashboard '{dashboard_id}'"}
            )
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "dashboard_id": dashboard_id,
                "message": f"Dashboard '{dashboard_id}' deleted successfully"
            }
        )
    
    def _handle_get_dashboard(self, task: Task) -> TaskResult:
        """Handle getting a custom dashboard configuration.
        
        Args:
            task: Task containing dashboard ID
            
        Returns:
            Task result with dashboard configuration
        """
        input_data = task.input_data
        dashboard_id = input_data.get("dashboard_id", "")
        
        if not dashboard_id:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"error": "Dashboard ID is required"}
            )
        
        # Load dashboard configuration
        dashboard_config = self._load_custom_dashboard(dashboard_id)
        if not dashboard_config:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"error": f"Dashboard '{dashboard_id}' not found"}
            )
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "dashboard_id": dashboard_id,
                "config": dashboard_config
            }
        )
    
    def _handle_list_dashboards(self, task: Task) -> TaskResult:
        """Handle listing available custom dashboards.
        
        Args:
            task: Task with optional filters
            
        Returns:
            Task result with list of dashboards
        """
        dashboards = self._list_custom_dashboards()
        
        # Apply filters if specified
        input_data = task.input_data
        if input_data.get("public_only", False):
            dashboards = [d for d in dashboards if d.get("is_public", False)]
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "dashboards": dashboards,
                "count": len(dashboards)
            }
        )
    
    def _handle_list_templates(self, task: Task) -> TaskResult:
        """Handle listing available dashboard templates.
        
        Args:
            task: Task with optional filters
            
        Returns:
            Task result with list of templates
        """
        templates = self._list_dashboard_templates()
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "templates": templates,
                "count": len(templates)
            }
        )
    
    def _handle_create_template(self, task: Task) -> TaskResult:
        """Handle creating a new dashboard template.
        
        Args:
            task: Task containing template configuration
            
        Returns:
            Task result with template creation status
        """
        input_data = task.input_data
        template_name = input_data.get("template_name", "")
        config = input_data.get("config", {})
        dashboard_id = input_data.get("from_dashboard_id", "")
        
        if not template_name:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"error": "Template name is required"}
            )
        
        # Load config from existing dashboard if specified
        if dashboard_id:
            dashboard_config = self._load_custom_dashboard(dashboard_id)
            if dashboard_config:
                # Merge dashboard config with provided config
                merged_config = dashboard_config.copy()
                for key, value in config.items():
                    merged_config[key] = value
                config = merged_config
            else:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.FAILED,
                    output_data={"error": f"Dashboard '{dashboard_id}' not found"}
                )
        
        # Validate configuration
        validation = self._validate_dashboard_config(config)
        if not validation["valid"]:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"errors": validation["errors"]}
            )
        
        # Save template
        if not self._save_dashboard_template(template_name, config):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"error": f"Failed to save template '{template_name}'"}
            )
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "template_name": template_name,
                "message": f"Template '{template_name}' created successfully"
            }
        )
    
    def _handle_delete_template(self, task: Task) -> TaskResult:
        """Handle deleting a dashboard template.
        
        Args:
            task: Task containing template name
            
        Returns:
            Task result with deletion status
        """
        input_data = task.input_data
        template_name = input_data.get("template_name", "")
        
        if not template_name:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"error": "Template name is required"}
            )
        
        template_path = os.path.join(self.templates_dir, f"{template_name}.json")
        if not os.path.exists(template_path):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"error": f"Template '{template_name}' not found"}
            )
        
        try:
            os.remove(template_path)
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "template_name": template_name,
                    "message": f"Template '{template_name}' deleted successfully"
                }
            )
        except Exception as e:
            logger.error(f"Error deleting template '{template_name}': {e}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"error": f"Failed to delete template '{template_name}': {str(e)}"}
            )
    
    def _handle_resolve(self, task: Task) -> TaskResult:
        """Main handler for the DashboardCustomizationResolver.
        
        Args:
            task: Task to resolve
            
        Returns:
            Task result
        """
        operation = task.input_data.get("operation", "")
        
        if operation == "create_dashboard":
            return self._handle_create_dashboard(task)
        
        elif operation == "update_dashboard":
            return self._handle_update_dashboard(task)
        
        elif operation == "delete_dashboard":
            return self._handle_delete_dashboard(task)
        
        elif operation == "get_dashboard":
            return self._handle_get_dashboard(task)
        
        elif operation == "list_dashboards":
            return self._handle_list_dashboards(task)
        
        elif operation == "list_templates":
            return self._handle_list_templates(task)
        
        elif operation == "create_template":
            return self._handle_create_template(task)
        
        elif operation == "delete_template":
            return self._handle_delete_template(task)
        
        elif operation == "generate_dashboard":
            input_data = task.input_data
            dashboard_id = input_data.get("dashboard_id", "")
            
            if not dashboard_id:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.FAILED,
                    output_data={"error": "Dashboard ID is required"}
                )
            
            dashboard_path = self._generate_custom_dashboard(dashboard_id)
            if not dashboard_path:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.FAILED,
                    output_data={"error": f"Failed to generate dashboard '{dashboard_id}'"}
                )
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "dashboard_id": dashboard_id,
                    "dashboard_path": dashboard_path,
                    "message": f"Dashboard '{dashboard_id}' generated successfully"
                }
            )
        
        else:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"error": f"Unknown operation: {operation}"}
            )
    
    def __call__(self, task: Task) -> TaskResult:
        """Resolve the given task for dashboard customization.
        
        Args:
            task: Task to resolve
            
        Returns:
            Task result
        """
        try:
            return self._handle_resolve(task)
        except Exception as e:
            logger.error(f"Error in DashboardCustomizationResolver: {e}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"error": f"Error in DashboardCustomizationResolver: {str(e)}"}
            ) 