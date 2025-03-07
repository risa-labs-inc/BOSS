"""DashboardGenerator component for creating monitoring dashboards and reports.

This component generates HTML dashboards and reports based on monitoring data
from various monitoring components.
"""

import logging
import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import os
import jinja2

from boss.core.task_models import Task, TaskResult, TaskStatus
from boss.lighthouse.monitoring.base_monitoring import BaseMonitoring
from boss.lighthouse.monitoring.chart_generator import ChartGenerator
from boss.lighthouse.monitoring.metrics_storage import MetricsStorage
from boss.lighthouse.monitoring.dashboard_components import DashboardTemplateRenderer, DashboardDataProcessor


class DashboardGenerator(BaseMonitoring):
    """Component for generating monitoring dashboards and reports.
    
    This component retrieves data from other monitoring components and generates
    HTML dashboards, charts, and reports for visualization.
    
    Attributes:
        data_dir: Directory where dashboards are saved
        template_dir: Directory containing dashboard templates
        template_renderer: Renderer for dashboard templates
        chart_generator: ChartGenerator for creating charts
        metrics_storage: MetricsStorage for retrieving metrics data
        dashboard_configs: Configuration for different dashboard types
    """
    
    def __init__(
        self,
        data_dir: str,
        metrics_storage: Optional[MetricsStorage] = None,
        chart_generator: Optional[ChartGenerator] = None
    ) -> None:
        """Initialize the DashboardGenerator.
        
        Args:
            data_dir: Directory for storing dashboard files
            metrics_storage: Optional MetricsStorage instance for retrieving metrics
            chart_generator: Optional ChartGenerator instance for creating charts
        """
        # Initialize without typical resolver metadata since we're not using it
        super().__init__(None, component_name="dashboard_generator")
        
        # Set up component-specific attributes
        self.logger = logging.getLogger("boss.lighthouse.monitoring.dashboard_generator")
        
        # Override data_dir since we're using a custom initialization
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Set up template directory
        self.template_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "templates",
            "dashboards"
        )
        os.makedirs(self.template_dir, exist_ok=True)
        
        # Initialize template renderer
        self.template_renderer = DashboardTemplateRenderer(self.template_dir)
        
        # Initialize or use provided chart generator
        if chart_generator:
            self.chart_generator = chart_generator
        else:
            chart_dir = os.path.join(self.data_dir, "charts")
            os.makedirs(chart_dir, exist_ok=True)
            self.chart_generator = ChartGenerator(output_dir=chart_dir)
        
        # Initialize or use provided metrics storage
        self.metrics_storage = metrics_storage or MetricsStorage(data_dir=os.path.join(self.data_dir, "metrics"))
        
        # Define dashboard configurations
        self.dashboard_configs = {
            "system": {
                "title": "System Monitoring Dashboard",
                "description": "System metrics and resource usage",
                "template": "system_dashboard",
                "components": ["system_metrics"]
            },
            "health": {
                "title": "Component Health Dashboard",
                "description": "Health status of system components",
                "template": "health_dashboard",
                "components": ["component_health"]
            },
            "alerts": {
                "title": "Alerts Dashboard",
                "description": "Active alerts and recent alert history",
                "template": "alerts_dashboard",
                "components": ["alerts"]
            },
            "performance": {
                "title": "Performance Dashboard",
                "description": "Performance metrics for system components",
                "template": "performance_dashboard",
                "components": ["performance_metrics"]
            }
        }
        
        self.logger.info("DashboardGenerator initialized")
    
    def __call__(self, task: Task) -> TaskResult:
        """Generate dashboards and reports.
        
        Args:
            task: Task to perform
            
        Returns:
            TaskResult with the result of the operation
        """
        operation = task.input_data.get("operation", "")
        
        try:
            if operation == "generate_dashboard":
                return self._handle_generate_dashboard(task)
            elif operation == "generate_report":
                return self._handle_generate_report(task)
            elif operation == "get_dashboard_url":
                return self._handle_get_dashboard_url(task)
            elif operation == "list_dashboards":
                return self._handle_list_dashboards(task)
            elif operation == "health_check":
                return self._handle_health_check(task)
            elif operation == "generate_custom_dashboard":
                return self._handle_generate_custom_dashboard(task)
            else:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.FAILED,
                    output_data={"error": f"Unknown operation: {operation}"}
                )
        except Exception as e:
            self.logger.error(f"Error in DashboardGenerator: {str(e)}", exc_info=True)
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"error": str(e)}
            )
    
    def _handle_generate_dashboard(self, task: Task) -> TaskResult:
        """Handle generating a dashboard.
        
        Args:
            task: Task containing dashboard generation parameters
            
        Returns:
            TaskResult with the generated dashboard information
        """
        dashboard_type = task.input_data.get("dashboard_type", "system")
        title = task.input_data.get("title", "")
        time_window = task.input_data.get("time_window", "24h")
        
        # Validate dashboard type
        if dashboard_type not in self.dashboard_configs:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"error": f"Unknown dashboard type: {dashboard_type}"}
            )
        
        # Get dashboard config
        config = self.dashboard_configs[dashboard_type].copy()
        
        # Override title if provided
        if title:
            config["title"] = title
        
        # Get component data
        component_data = self._get_component_data(dashboard_type, time_window)
        
        # Generate charts
        charts = self._generate_component_charts(dashboard_type, component_data)
        
        # Generate dashboard HTML
        dashboard_id = f"{dashboard_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        dashboard_file = f"{dashboard_id}.html"
        
        # Create dashboard context
        context = {
            "dashboard_id": dashboard_id,
            "dashboard_type": dashboard_type,
            "title": config["title"],
            "description": config["description"],
            "time_window": time_window,
            "generated_at": datetime.now().isoformat(),
            "data": component_data,
            "charts": charts
        }
        
        # Generate HTML
        html = self.template_renderer.render_dashboard(config["template"], context)
        
        # Write HTML to file
        dashboard_path = os.path.join(self.data_dir, dashboard_file)
        with open(dashboard_path, "w") as f:
            f.write(html)
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "dashboard_id": dashboard_id,
                "dashboard_file": dashboard_file,
                "dashboard_path": dashboard_path
            }
        )
    
    def _handle_generate_custom_dashboard(self, task: Task) -> TaskResult:
        """Handle generating a custom dashboard.
        
        Args:
            task: Task containing custom dashboard configuration
            
        Returns:
            TaskResult with the generated dashboard information
        """
        dashboard_id = task.input_data.get("dashboard_id", f"custom_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        title = task.input_data.get("title", "Custom Dashboard")
        description = task.input_data.get("description", "")
        charts = task.input_data.get("charts", [])
        layout = task.input_data.get("layout", "grid")
        custom_css = task.input_data.get("custom_css", "")
        custom_js = task.input_data.get("custom_js", "")
        
        # Generate dashboard HTML
        dashboard_file = f"{dashboard_id}.html"
        
        # Create dashboard context
        context = {
            "dashboard_id": dashboard_id,
            "dashboard_type": "custom",
            "title": title,
            "description": description,
            "layout": layout,
            "generated_at": datetime.now().isoformat(),
            "charts": charts,
            "custom_css": custom_css,
            "custom_js": custom_js
        }
        
        # Generate HTML
        html = self.template_renderer.render_dashboard("custom_dashboard", context)
        
        # Write HTML to file
        dashboard_path = os.path.join(self.data_dir, dashboard_file)
        with open(dashboard_path, "w") as f:
            f.write(html)
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "dashboard_id": dashboard_id,
                "dashboard_file": dashboard_file,
                "dashboard_path": dashboard_path
            }
        )
    
    def _get_component_data(self, dashboard_type: str, time_window: str) -> Dict[str, Any]:
        """Get data for dashboard components.
        
        Args:
            dashboard_type: Type of dashboard to generate
            time_window: Time window for metrics
            
        Returns:
            Data for dashboard components
        """
        # Parse time window
        end_time = datetime.now()
        start_time = self._parse_time_window(end_time, time_window)
        
        # Get data based on dashboard type
        if dashboard_type == "system":
            return self._get_system_data(start_time, end_time)
        elif dashboard_type == "health":
            return self._get_health_data()
        elif dashboard_type == "alerts":
            return self._get_alerts_data(start_time, end_time)
        elif dashboard_type == "performance":
            return self._get_performance_data(start_time, end_time)
        else:
            return {}
    
    def _generate_component_charts(self, dashboard_type: str, component_data: Dict[str, Any]) -> Dict[str, str]:
        """Generate charts for dashboard components.
        
        Args:
            dashboard_type: Type of dashboard to generate
            component_data: Data for dashboard components
            
        Returns:
            Dictionary of chart IDs to file paths
        """
        charts = {}
        
        # Generate charts based on dashboard type
        if dashboard_type == "system":
            charts.update(self._generate_system_charts(component_data))
        elif dashboard_type == "health":
            charts.update(self._generate_health_charts(component_data))
        elif dashboard_type == "alerts":
            charts.update(self._generate_alerts_charts(component_data))
        elif dashboard_type == "performance":
            charts.update(self._generate_performance_charts(component_data))
        
        return charts
    
    def _handle_generate_report(self, task: Task) -> TaskResult:
        """Handle generating a report.
        
        Args:
            task: Task containing report generation parameters
            
        Returns:
            TaskResult with the generated report information
        """
        report_type = task.input_data.get("report_type", "system")
        title = task.input_data.get("title", "")
        time_window = task.input_data.get("time_window", "7d")
        
        # Validate report type
        if report_type not in self.dashboard_configs:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"error": f"Unknown report type: {report_type}"}
            )
        
        # Get dashboard config
        config = self.dashboard_configs[report_type].copy()
        
        # Override title if provided
        if title:
            config["title"] = title
        
        # Get component data
        component_data = self._get_component_data(report_type, time_window)
        
        # Generate charts
        charts = self._generate_component_charts(report_type, component_data)
        
        # Generate report HTML
        report_id = f"{report_type}_report_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        report_file = f"{report_id}.html"
        
        # Create report context
        context = {
            "report_id": report_id,
            "report_type": report_type,
            "title": f"{config['title']} Report",
            "description": config["description"],
            "time_window": time_window,
            "generated_at": datetime.now().isoformat(),
            "data": component_data,
            "charts": charts
        }
        
        # Generate HTML
        html = self.template_renderer.render_report(f"{report_type}_report", context)
        
        # Write HTML to file
        report_path = os.path.join(self.data_dir, report_file)
        with open(report_path, "w") as f:
            f.write(html)
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "report_id": report_id,
                "report_file": report_file,
                "report_path": report_path
            }
        )
    
    def _handle_get_dashboard_url(self, task: Task) -> TaskResult:
        """Handle getting a dashboard URL.
        
        Args:
            task: Task containing dashboard ID
            
        Returns:
            TaskResult with the dashboard URL
        """
        dashboard_id = task.input_data.get("dashboard_id", "")
        
        if not dashboard_id:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"error": "Dashboard ID is required"}
            )
        
        # Check if dashboard exists
        dashboard_file = f"{dashboard_id}.html"
        dashboard_path = os.path.join(self.data_dir, dashboard_file)
        
        if not os.path.exists(dashboard_path):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                output_data={"error": f"Dashboard {dashboard_id} not found"}
            )
        
        # Get server base URL from task or default
        server_base_url = task.input_data.get("server_base_url", "")
        
        if server_base_url:
            dashboard_url = f"{server_base_url}/dashboards/{dashboard_id}"
        else:
            dashboard_url = f"file://{os.path.abspath(dashboard_path)}"
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "dashboard_id": dashboard_id,
                "dashboard_url": dashboard_url,
                "dashboard_path": dashboard_path
            }
        )
    
    def _handle_list_dashboards(self, task: Task) -> TaskResult:
        """Handle listing available dashboards.
        
        Args:
            task: Task containing filter parameters
            
        Returns:
            TaskResult with a list of available dashboards
        """
        dashboard_type = task.input_data.get("dashboard_type", "")
        
        dashboards = []
        
        # List all HTML files in the dashboard directory
        for filename in os.listdir(self.data_dir):
            if filename.endswith(".html"):
                # Parse dashboard ID from filename
                dashboard_id = filename[:-5]  # Remove .html extension
                
                # Skip if doesn't match the requested type
                if dashboard_type and not dashboard_id.startswith(f"{dashboard_type}_"):
                    continue
                
                # Get file stats
                file_path = os.path.join(self.data_dir, filename)
                stats = os.stat(file_path)
                
                # Parse dashboard type from ID
                parts = dashboard_id.split("_")
                db_type = parts[0] if parts else "unknown"
                
                dashboards.append({
                    "id": dashboard_id,
                    "type": db_type,
                    "title": self.dashboard_configs.get(db_type, {}).get("title", "Custom Dashboard"),
                    "file": filename,
                    "created_at": datetime.fromtimestamp(stats.st_ctime).isoformat(),
                    "size": stats.st_size
                })
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data=dashboards
        )
    
    def _handle_health_check(self, task: Task) -> TaskResult:
        """Handle health check task.
        
        Args:
            task: Health check task
            
        Returns:
            TaskResult with health check status
        """
        is_healthy = self.health_check()
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED if is_healthy else TaskStatus.FAILED,
            output_data={"healthy": is_healthy}
        )
    
    def health_check(self) -> bool:
        """Perform a health check.
        
        Returns:
            True if healthy, False otherwise
        """
        # Check if template directory exists
        if not os.path.exists(self.template_dir):
            self.logger.error("Template directory not found")
            return False
        
        # Check if data directory exists and is writable
        if not os.path.exists(self.data_dir):
            self.logger.error("Data directory not found")
            return False
        
        # Check if we can write to the data directory
        try:
            test_file = os.path.join(self.data_dir, "health_check.txt")
            with open(test_file, "w") as f:
                f.write("health check")
            os.remove(test_file)
        except Exception as e:
            self.logger.error(f"Failed to write to data directory: {str(e)}")
            return False
        
        # Check if templates are available
        for dashboard_type in self.dashboard_configs:
            template_name = self.dashboard_configs[dashboard_type]["template"]
            template_path = os.path.join(self.template_dir, f"{template_name}.html")
            if not os.path.exists(template_path):
                self.logger.error(f"Template {template_name} not found")
                return False
        
        return True
    
    # Helper methods for data retrieval
    
    def _parse_time_window(self, end_time: datetime, time_window: str) -> datetime:
        """Parse a time window string into a start time.
        
        Args:
            end_time: End time
            time_window: Time window string (e.g. "1h", "7d")
            
        Returns:
            Start time
        """
        # Parse time window string
        unit = time_window[-1]
        value = int(time_window[:-1])
        
        if unit == "m":
            return end_time - timedelta(minutes=value)
        elif unit == "h":
            return end_time - timedelta(hours=value)
        elif unit == "d":
            return end_time - timedelta(days=value)
        elif unit == "w":
            return end_time - timedelta(weeks=value)
        else:
            raise ValueError(f"Invalid time window unit: {unit}")
    
    def _get_system_data(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get system metrics data.
        
        Args:
            start_time: Start time for metrics
            end_time: End time for metrics
            
        Returns:
            System metrics data
        """
        # Get system metrics
        metrics_task = Task(
            input_data={
                "operation": "get_metrics",
                "metrics_type": "system",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            },
            metadata={"source": "dashboard_generator"}
        )
        
        metrics_result = self.metrics_storage(metrics_task)
        
        if not hasattr(metrics_result, "status") or metrics_result.status != TaskStatus.COMPLETED:
            error_msg = getattr(metrics_result, "error", "Unknown error")
            self.logger.error(f"Failed to get system metrics: {error_msg}")
            return {}
        
        system_metrics = metrics_result.output_data
        
        # Process metrics data
        return DashboardDataProcessor.process_system_metrics(system_metrics)
    
    def _get_health_data(self) -> Dict[str, Any]:
        """Get component health data.
        
        Returns:
            Component health data
        """
        # Get component health
        health_task = Task(
            input_data={"operation": "get_component_health"},
            metadata={"source": "dashboard_generator"}
        )
        
        health_result = self.metrics_storage(health_task)
        
        if not hasattr(health_result, "status") or health_result.status != TaskStatus.COMPLETED:
            error_msg = getattr(health_result, "error", "Unknown error")
            self.logger.error(f"Failed to get component health: {error_msg}")
            return {}
        
        # Process health data
        return DashboardDataProcessor.process_health_data(health_result.output_data)
    
    def _get_alerts_data(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get alerts data.
        
        Args:
            start_time: Start time for alerts
            end_time: End time for alerts
            
        Returns:
            Alerts data
        """
        # Get alerts
        alerts_task = Task(
            input_data={
                "operation": "get_alerts",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            },
            metadata={"source": "dashboard_generator"}
        )
        
        alerts_result = self.metrics_storage(alerts_task)
        
        if not hasattr(alerts_result, "status") or alerts_result.status != TaskStatus.COMPLETED:
            error_msg = getattr(alerts_result, "error", "Unknown error")
            self.logger.error(f"Failed to get alerts: {error_msg}")
            return {}
        
        # Process alerts data
        return DashboardDataProcessor.process_alerts_data(alerts_result.output_data)
    
    def _get_performance_data(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get performance metrics data.
        
        Args:
            start_time: Start time for metrics
            end_time: End time for metrics
            
        Returns:
            Performance metrics data
        """
        # Get performance metrics
        metrics_task = Task(
            input_data={
                "operation": "get_performance_metrics",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            },
            metadata={"source": "dashboard_generator"}
        )
        
        metrics_result = self.metrics_storage(metrics_task)
        
        if not hasattr(metrics_result, "status") or metrics_result.status != TaskStatus.COMPLETED:
            error_msg = getattr(metrics_result, "error", "Unknown error")
            self.logger.error(f"Failed to get performance metrics: {error_msg}")
            return {}
        
        # Process performance data
        return DashboardDataProcessor.process_performance_data(metrics_result.output_data)
    
    # Helper methods for chart generation
    
    def _generate_system_charts(self, component_data: Dict[str, Any]) -> Dict[str, str]:
        """Generate charts for system metrics.
        
        Args:
            component_data: System metrics data
            
        Returns:
            Dictionary of chart IDs to file paths
        """
        charts = {}
        
        time_series = component_data.get("time_series", {})
        timestamps = time_series.get("timestamps", [])
        
        if not timestamps:
            return charts
        
        # Generate CPU usage chart
        cpu_values = time_series.get("cpu", [])
        if cpu_values:
            cpu_chart_task = Task(
                input_data={
                    "operation": "generate_chart",
                    "chart_type": "line",
                    "title": "CPU Usage",
                    "data": {
                        "x": timestamps,
                        "y": cpu_values,
                        "name": "CPU Usage (%)"
                    },
                    "options": {
                        "xaxis_title": "Time",
                        "yaxis_title": "Usage (%)",
                        "yaxis_min": 0,
                        "yaxis_max": 100
                    }
                },
                metadata={"source": "dashboard_generator"}
            )
            
            cpu_chart_result = self.chart_generator(cpu_chart_task)
            
            if hasattr(cpu_chart_result, "status") and cpu_chart_result.status == TaskStatus.COMPLETED:
                charts["cpu_usage"] = cpu_chart_result.output_data.get("chart_file", "")
        
        # Generate memory usage chart
        memory_values = time_series.get("memory", [])
        if memory_values:
            memory_chart_task = Task(
                input_data={
                    "operation": "generate_chart",
                    "chart_type": "line",
                    "title": "Memory Usage",
                    "data": {
                        "x": timestamps,
                        "y": memory_values,
                        "name": "Memory Usage (%)"
                    },
                    "options": {
                        "xaxis_title": "Time",
                        "yaxis_title": "Usage (%)",
                        "yaxis_min": 0,
                        "yaxis_max": 100
                    }
                },
                metadata={"source": "dashboard_generator"}
            )
            
            memory_chart_result = self.chart_generator(memory_chart_task)
            
            if hasattr(memory_chart_result, "status") and memory_chart_result.status == TaskStatus.COMPLETED:
                charts["memory_usage"] = memory_chart_result.output_data.get("chart_file", "")
        
        return charts
    
    def _generate_health_charts(self, component_data: Dict[str, Any]) -> Dict[str, str]:
        """Generate charts for component health.
        
        Args:
            component_data: Component health data
            
        Returns:
            Dictionary of chart IDs to file paths
        """
        charts = {}
        
        summary = component_data.get("summary", {})
        if not summary:
            return charts
        
        # Generate health status summary pie chart
        health_status = [
            summary.get("healthy", 0),
            summary.get("warning", 0),
            summary.get("critical", 0)
        ]
        
        if sum(health_status) > 0:
            health_chart_task = Task(
                input_data={
                    "operation": "generate_chart",
                    "chart_type": "pie",
                    "title": "Component Health Status",
                    "data": {
                        "labels": ["Healthy", "Warning", "Critical"],
                        "values": health_status
                    },
                    "options": {
                        "colors": ["#4CAF50", "#FFC107", "#F44336"]
                    }
                },
                metadata={"source": "dashboard_generator"}
            )
            
            health_chart_result = self.chart_generator(health_chart_task)
            
            if hasattr(health_chart_result, "status") and health_chart_result.status == TaskStatus.COMPLETED:
                charts["health_status"] = health_chart_result.output_data.get("chart_file", "")
        
        return charts
    
    def _generate_alerts_charts(self, component_data: Dict[str, Any]) -> Dict[str, str]:
        """Generate charts for alerts.
        
        Args:
            component_data: Alerts data
            
        Returns:
            Dictionary of chart IDs to file paths
        """
        charts = {}
        
        summary = component_data.get("summary", {})
        if not summary:
            return charts
        
        # Generate alerts by severity pie chart
        alert_counts = [
            summary.get("critical", 0),
            summary.get("error", 0),
            summary.get("warning", 0),
            summary.get("info", 0)
        ]
        
        if sum(alert_counts) > 0:
            severity_chart_task = Task(
                input_data={
                    "operation": "generate_chart",
                    "chart_type": "pie",
                    "title": "Alerts by Severity",
                    "data": {
                        "labels": ["Critical", "Error", "Warning", "Info"],
                        "values": alert_counts
                    },
                    "options": {
                        "colors": ["#F44336", "#FF5722", "#FFC107", "#2196F3"]
                    }
                },
                metadata={"source": "dashboard_generator"}
            )
            
            severity_chart_result = self.chart_generator(severity_chart_task)
            
            if hasattr(severity_chart_result, "status") and severity_chart_result.status == TaskStatus.COMPLETED:
                charts["alerts_by_severity"] = severity_chart_result.output_data.get("chart_file", "")
        
        return charts
    
    def _generate_performance_charts(self, component_data: Dict[str, Any]) -> Dict[str, str]:
        """Generate charts for performance metrics.
        
        Args:
            component_data: Performance metrics data
            
        Returns:
            Dictionary of chart IDs to file paths
        """
        charts = {}
        
        component_stats = component_data.get("component_stats", {})
        if not component_stats:
            return charts
        
        # Generate average execution time bar chart
        components = list(component_stats.keys())
        avg_execution_times = [stats.get("avg_execution_time", 0) for stats in component_stats.values()]
        
        if components and avg_execution_times:
            execution_chart_task = Task(
                input_data={
                    "operation": "generate_chart",
                    "chart_type": "bar",
                    "title": "Average Execution Time by Component",
                    "data": {
                        "x": components,
                        "y": avg_execution_times,
                        "name": "Execution Time (ms)"
                    },
                    "options": {
                        "xaxis_title": "Component",
                        "yaxis_title": "Execution Time (ms)"
                    }
                },
                metadata={"source": "dashboard_generator"}
            )
            
            execution_chart_result = self.chart_generator(execution_chart_task)
            
            if hasattr(execution_chart_result, "status") and execution_chart_result.status == TaskStatus.COMPLETED:
                charts["avg_execution_time"] = execution_chart_result.output_data.get("chart_file", "")
        
        return charts 