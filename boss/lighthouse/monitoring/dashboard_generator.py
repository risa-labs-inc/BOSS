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


class DashboardGenerator(BaseMonitoring):
    """Component for generating monitoring dashboards and reports.
    
    This component retrieves data from other monitoring components and generates
    HTML dashboards, charts, and reports for visualization.
    
    Attributes:
        output_dir: Directory where dashboards are saved
        template_dir: Directory containing dashboard templates
        jinja_env: Jinja2 environment for template rendering
        chart_generator: ChartGenerator for creating charts
        metrics_storage: MetricsStorage for retrieving metrics data
        dashboard_configs: Configuration for different dashboard types
    """
    
    def __init__(self, metadata: Any) -> None:
        """Initialize the DashboardGenerator.
        
        Args:
            metadata: Resolver metadata
        """
        super().__init__(metadata, component_name="dashboard_generator")
        
        # Set up component-specific attributes
        self.logger = logging.getLogger("boss.lighthouse.monitoring.dashboard_generator")
        
        # Define output directory for dashboards
        self.output_dir = os.path.join(self.data_dir, "dashboards")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Define chart directory
        self.chart_dir = os.path.join(self.output_dir, "charts")
        os.makedirs(self.chart_dir, exist_ok=True)
        
        # Define template directory
        self.template_dir = os.path.join(os.path.dirname(__file__), "templates")
        os.makedirs(self.template_dir, exist_ok=True)
        
        # Set up Jinja2 environment
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.template_dir),
            autoescape=jinja2.select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Initialize chart generator
        self.chart_generator = ChartGenerator(self.chart_dir)
        
        # Initialize metrics storage
        self.metrics_storage = MetricsStorage(self.data_dir)
        
        # Dashboard configuration
        self.dashboard_configs = {
            "system": {
                "title": "System Performance Dashboard",
                "components": ["cpu", "memory", "disk", "network"],
                "refresh_interval": 60  # seconds
            },
            "health": {
                "title": "Component Health Dashboard",
                "components": ["health_status", "response_times", "uptime"],
                "refresh_interval": 300  # seconds
            },
            "alerts": {
                "title": "Alert Dashboard",
                "components": ["active_alerts", "alert_history", "alert_stats"],
                "refresh_interval": 120  # seconds
            },
            "performance": {
                "title": "Performance Metrics Dashboard",
                "components": ["operation_times", "success_rates", "trends"],
                "refresh_interval": 300  # seconds
            }
        }
        
    async def resolve(self, task: Task) -> TaskResult:
        """Resolve dashboard generation tasks.
        
        Args:
            task: The dashboard task to resolve
            
        Returns:
            The result of the dashboard operation
        """
        if not isinstance(task.input_data, dict):
            return self._create_error_result(task, "Input data must be a dictionary")
            
        operation = task.input_data.get("operation")
        if not operation:
            return self._create_error_result(task, "Missing 'operation' field")
            
        try:
            # Route to the appropriate handler based on the operation
            if operation == "generate_dashboard":
                return await self._handle_generate_dashboard(task)
            elif operation == "generate_report":
                return await self._handle_generate_report(task)
            elif operation == "get_dashboard_url":
                return await self._handle_get_dashboard_url(task)
            elif operation == "list_dashboards":
                return await self._handle_list_dashboards(task)
            elif operation == "health_check":
                return await self._handle_health_check(task)
            else:
                return self._create_error_result(task, f"Unsupported operation: {operation}")
                
        except Exception as e:
            self.logger.error(f"Error in DashboardGenerator: {e}")
            return self._create_error_result(task, f"Internal error: {str(e)}")
            
    async def _handle_generate_dashboard(self, task: Task) -> TaskResult:
        """Handle the generate_dashboard operation.
        
        Args:
            task: The task containing dashboard details
            
        Returns:
            A TaskResult with the generated dashboard information
        """
        # Extract required parameters
        dashboard_type = task.input_data.get("dashboard_type")
        if not dashboard_type:
            return self._create_error_result(task, "Missing 'dashboard_type' field")
            
        # Check if the dashboard type is supported
        if dashboard_type not in self.dashboard_configs:
            return self._create_error_result(
                task, 
                f"Unsupported dashboard type: {dashboard_type}. Supported types: {', '.join(self.dashboard_configs.keys())}"
            )
            
        # Extract optional parameters
        title = task.input_data.get("title", self.dashboard_configs[dashboard_type]["title"])
        time_window = task.input_data.get("time_window", "24h")
        refresh_interval = task.input_data.get(
            "refresh_interval", 
            self.dashboard_configs[dashboard_type]["refresh_interval"]
        )
        
        # Generate a unique dashboard ID if not provided
        dashboard_id = task.input_data.get("dashboard_id", f"{dashboard_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        
        try:
            # Get data for the dashboard components
            component_data = await self._get_component_data(dashboard_type, time_window)
            
            # Generate charts for the dashboard components
            charts = await self._generate_component_charts(dashboard_type, component_data)
            
            # Build the dashboard configuration
            dashboard_config = {
                "id": dashboard_id,
                "type": dashboard_type,
                "title": title,
                "time_window": time_window,
                "refresh_interval": refresh_interval,
                "components": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            # Prepare component data for the template
            components = []
            for component_name in self.dashboard_configs[dashboard_type]["components"]:
                component = {
                    "name": component_name,
                    "title": component_name.replace("_", " ").title(),
                    "loading": False
                }
                
                # Add component data and chart if available
                if component_name in component_data:
                    component["data"] = component_data[component_name]
                    
                if component_name in charts:
                    component["chart"] = charts[component_name]
                    component["content"] = f'<img src="{charts[component_name]}" alt="{component["title"]} Chart" style="max-width:100%;">'
                else:
                    component["content"] = f"<p>No data available for {component['title']}</p>"
                    
                components.append(component)
                
            dashboard_config["components"] = components
            
            # Generate the dashboard HTML
            dashboard_html = self._generate_dashboard_html(dashboard_config)
            
            # Save the dashboard
            dashboard_path = os.path.join(self.output_dir, f"{dashboard_id}.html")
            with open(dashboard_path, "w") as f:
                f.write(dashboard_html)
                
            # Save the dashboard configuration
            config_path = os.path.join(self.output_dir, f"{dashboard_id}.json")
            with open(config_path, "w") as f:
                json.dump(dashboard_config, f, indent=2)
                
            return self._create_success_result(task, {
                "message": "Dashboard generated successfully",
                "dashboard_id": dashboard_id,
                "dashboard_path": dashboard_path,
                "dashboard_url": f"/dashboards/{dashboard_id}.html",
                "config": dashboard_config
            })
        except Exception as e:
            self.logger.error(f"Error generating dashboard: {e}")
            return self._create_error_result(task, f"Error generating dashboard: {str(e)}")
            
    async def _get_component_data(self, dashboard_type: str, time_window: str) -> Dict[str, Any]:
        """Get data for dashboard components.
        
        Args:
            dashboard_type: Type of dashboard
            time_window: Time window for data
            
        Returns:
            Component data dictionary
        """
        component_data = {}
        
        try:
            # Parse the time window
            start_time = self._parse_time_window(time_window)
            end_time = datetime.now()
            
            if dashboard_type == "system":
                # Get system metrics for each component
                for metric_type in ["cpu", "memory", "disk", "network"]:
                    metrics = self.metrics_storage.get_system_metrics(
                        metric_type=metric_type,
                        start_time=start_time,
                        end_time=end_time
                    )
                    component_data[metric_type] = metrics
                    
            elif dashboard_type == "health":
                # Get health data for components
                health_history = self.metrics_storage.get_health_history(
                    start_time=start_time,
                    end_time=end_time
                )
                
                # Group by component_id
                grouped_health = {}
                for health in health_history:
                    component_id = health.get("component_id")
                    if component_id not in grouped_health:
                        grouped_health[component_id] = []
                    grouped_health[component_id].append(health)
                    
                component_data["health_status"] = health_history
                
                # Extract response times
                response_times = [
                    {
                        "component_id": h.get("component_id"),
                        "response_time_ms": h.get("response_time_ms", 0),
                        "timestamp": h.get("timestamp")
                    }
                    for h in health_history
                    if h.get("response_time_ms") is not None
                ]
                component_data["response_times"] = response_times
                
                # Calculate uptime based on health checks
                uptime_data = []
                for component_id, checks in grouped_health.items():
                    total_checks = len(checks)
                    healthy_checks = sum(1 for c in checks if c.get("status") == "healthy")
                    uptime_percent = (healthy_checks / total_checks * 100) if total_checks > 0 else 0
                    
                    uptime_data.append({
                        "component_id": component_id,
                        "uptime_percent": uptime_percent,
                        "total_checks": total_checks
                    })
                    
                component_data["uptime"] = uptime_data
                
            elif dashboard_type == "alerts":
                # Get active alerts
                active_alerts = self.metrics_storage.get_alerts(status="active")
                component_data["active_alerts"] = active_alerts
                
                # Get alert history
                alert_history = self.metrics_storage.get_alerts(
                    status="resolved",
                    start_time=start_time,
                    end_time=end_time
                )
                component_data["alert_history"] = alert_history
                
                # Calculate alert statistics
                severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
                component_counts = {}
                
                for alert in active_alerts + alert_history:
                    # Count by severity
                    severity = alert.get("severity", "medium")
                    if severity in severity_counts:
                        severity_counts[severity] += 1
                        
                    # Count by component
                    component_id = alert.get("component_id")
                    if component_id:
                        if component_id not in component_counts:
                            component_counts[component_id] = 0
                        component_counts[component_id] += 1
                        
                component_data["alert_stats"] = {
                    "severity_counts": [
                        {"severity": severity, "count": count}
                        for severity, count in severity_counts.items()
                    ],
                    "component_counts": [
                        {"component_id": component_id, "count": count}
                        for component_id, count in component_counts.items()
                    ],
                    "total_alerts": len(active_alerts) + len(alert_history),
                    "active_alerts": len(active_alerts),
                    "resolved_alerts": len(alert_history)
                }
                
            elif dashboard_type == "performance":
                # Get performance metrics
                performance_metrics = self.metrics_storage.get_performance_metrics(
                    start_time=start_time,
                    end_time=end_time
                )
                
                # Group by operation_name
                grouped_operations = {}
                for metric in performance_metrics:
                    operation_name = metric.get("operation_name")
                    if operation_name not in grouped_operations:
                        grouped_operations[operation_name] = []
                    grouped_operations[operation_name].append(metric)
                    
                # Calculate operation times
                operation_times = []
                for operation_name, metrics in grouped_operations.items():
                    avg_time = sum(m.get("execution_time_ms", 0) for m in metrics) / len(metrics) if metrics else 0
                    operation_times.append({
                        "operation_name": operation_name,
                        "avg_execution_time_ms": avg_time,
                        "count": len(metrics)
                    })
                    
                component_data["operation_times"] = operation_times
                
                # Calculate success rates
                success_rates = []
                for operation_name, metrics in grouped_operations.items():
                    success_count = sum(1 for m in metrics if m.get("success"))
                    total_count = len(metrics)
                    success_rate = (success_count / total_count * 100) if total_count > 0 else 0
                    
                    success_rates.append({
                        "operation_name": operation_name,
                        "success_rate": success_rate,
                        "total_count": total_count
                    })
                    
                component_data["success_rates"] = success_rates
                
                # Keep the raw metrics for trend analysis
                component_data["trends"] = performance_metrics
                
        except Exception as e:
            self.logger.error(f"Error getting component data: {e}")
            
        return component_data
        
    async def _generate_component_charts(self, dashboard_type: str, component_data: Dict[str, Any]) -> Dict[str, str]:
        """Generate charts for dashboard components.
        
        Args:
            dashboard_type: Type of dashboard
            component_data: Component data dictionary
            
        Returns:
            Dictionary mapping component names to chart URLs
        """
        charts = {}
        
        try:
            if dashboard_type == "system":
                # CPU usage chart
                if "cpu" in component_data and component_data["cpu"]:
                    cpu_chart = self.chart_generator.generate_line_chart(
                        data=component_data["cpu"],
                        x_key="timestamp",
                        y_key="usage_percent",
                        title="CPU Usage",
                        x_label="Time",
                        y_label="Usage (%)",
                        color="blue",
                        as_base64=True
                    )
                    charts["cpu"] = cpu_chart
                    
                # Memory usage chart
                if "memory" in component_data and component_data["memory"]:
                    memory_chart = self.chart_generator.generate_line_chart(
                        data=component_data["memory"],
                        x_key="timestamp",
                        y_key="usage_percent",
                        title="Memory Usage",
                        x_label="Time",
                        y_label="Usage (%)",
                        color="green",
                        as_base64=True
                    )
                    charts["memory"] = memory_chart
                    
                # Disk usage chart
                if "disk" in component_data and component_data["disk"]:
                    disk_chart = self.chart_generator.generate_line_chart(
                        data=component_data["disk"],
                        x_key="timestamp",
                        y_key="usage_percent",
                        title="Disk Usage",
                        x_label="Time",
                        y_label="Usage (%)",
                        color="red",
                        as_base64=True
                    )
                    charts["disk"] = disk_chart
                    
                # Network usage chart
                if "network" in component_data and component_data["network"]:
                    network_chart = self.chart_generator.generate_multi_line_chart(
                        data_series=[
                            (component_data["network"], "bytes_sent_mb", "Sent"),
                            (component_data["network"], "bytes_received_mb", "Received")
                        ],
                        x_key="timestamp",
                        title="Network Usage",
                        x_label="Time",
                        y_label="MB",
                        as_base64=True
                    )
                    charts["network"] = network_chart
                    
            elif dashboard_type == "health":
                # Health status chart
                if "health_status" in component_data and component_data["health_status"]:
                    # Group health status by component
                    grouped_status = {}
                    for health in component_data["health_status"]:
                        component_id = health.get("component_id")
                        status = health.get("status")
                        if component_id not in grouped_status:
                            grouped_status[component_id] = {"healthy": 0, "unhealthy": 0}
                        grouped_status[component_id][status] += 1
                        
                    # Prepare data for chart
                    health_data = [
                        {
                            "component_id": component_id,
                            "healthy_count": counts["healthy"],
                            "unhealthy_count": counts["unhealthy"]
                        }
                        for component_id, counts in grouped_status.items()
                    ]
                    
                    health_chart = self.chart_generator.generate_bar_chart(
                        data=health_data,
                        category_key="component_id",
                        value_key="healthy_count",
                        title="Component Health Status",
                        x_label="Component",
                        y_label="Healthy Checks",
                        color="green",
                        as_base64=True
                    )
                    charts["health_status"] = health_chart
                    
                # Response times chart
                if "response_times" in component_data and component_data["response_times"]:
                    response_chart = self.chart_generator.generate_line_chart(
                        data=component_data["response_times"],
                        x_key="timestamp",
                        y_key="response_time_ms",
                        title="Component Response Times",
                        x_label="Time",
                        y_label="Response Time (ms)",
                        color="blue",
                        as_base64=True
                    )
                    charts["response_times"] = response_chart
                    
                # Uptime chart
                if "uptime" in component_data and component_data["uptime"]:
                    uptime_chart = self.chart_generator.generate_bar_chart(
                        data=component_data["uptime"],
                        category_key="component_id",
                        value_key="uptime_percent",
                        title="Component Uptime",
                        x_label="Component",
                        y_label="Uptime (%)",
                        color="blue",
                        as_base64=True
                    )
                    charts["uptime"] = uptime_chart
                    
            elif dashboard_type == "alerts":
                # Active alerts chart
                if "active_alerts" in component_data and component_data["active_alerts"]:
                    alerts_by_severity = component_data["alert_stats"]["severity_counts"]
                    
                    severity_chart = self.chart_generator.generate_pie_chart(
                        data=alerts_by_severity,
                        label_key="severity",
                        value_key="count",
                        title="Alerts by Severity",
                        as_base64=True
                    )
                    charts["active_alerts"] = severity_chart
                    
                # Alert history chart
                if "alert_history" in component_data and component_data["alert_history"]:
                    # Group alerts by day
                    from collections import defaultdict
                    alerts_by_day = defaultdict(int)
                    
                    for alert in component_data["alert_history"]:
                        date_str = alert.get("created_at", "").split("T")[0]
                        alerts_by_day[date_str] += 1
                        
                    # Prepare data for chart
                    history_data = [
                        {"date": date, "count": count}
                        for date, count in alerts_by_day.items()
                    ]
                    
                    # Sort by date
                    history_data.sort(key=lambda x: x["date"])
                    
                    history_chart = self.chart_generator.generate_line_chart(
                        data=history_data,
                        x_key="date",
                        y_key="count",
                        title="Alert History",
                        x_label="Date",
                        y_label="Number of Alerts",
                        color="red",
                        parse_dates=False,
                        as_base64=True
                    )
                    charts["alert_history"] = history_chart
                    
                # Alert statistics chart
                if "alert_stats" in component_data:
                    component_counts = component_data["alert_stats"]["component_counts"]
                    
                    if component_counts:
                        stats_chart = self.chart_generator.generate_bar_chart(
                            data=component_counts,
                            category_key="component_id",
                            value_key="count",
                            title="Alerts by Component",
                            x_label="Component",
                            y_label="Number of Alerts",
                            color="orange",
                            as_base64=True
                        )
                        charts["alert_stats"] = stats_chart
                        
            elif dashboard_type == "performance":
                # Operation times chart
                if "operation_times" in component_data and component_data["operation_times"]:
                    times_chart = self.chart_generator.generate_bar_chart(
                        data=component_data["operation_times"],
                        category_key="operation_name",
                        value_key="avg_execution_time_ms",
                        title="Average Operation Times",
                        x_label="Operation",
                        y_label="Execution Time (ms)",
                        color="blue",
                        as_base64=True
                    )
                    charts["operation_times"] = times_chart
                    
                # Success rates chart
                if "success_rates" in component_data and component_data["success_rates"]:
                    success_chart = self.chart_generator.generate_bar_chart(
                        data=component_data["success_rates"],
                        category_key="operation_name",
                        value_key="success_rate",
                        title="Operation Success Rates",
                        x_label="Operation",
                        y_label="Success Rate (%)",
                        color="green",
                        as_base64=True
                    )
                    charts["success_rates"] = success_chart
                    
                # Performance trends chart
                if "trends" in component_data and component_data["trends"]:
                    # Group by operation_name
                    grouped_trends = {}
                    for metric in component_data["trends"]:
                        operation_name = metric.get("operation_name")
                        if operation_name not in grouped_trends:
                            grouped_trends[operation_name] = []
                        grouped_trends[operation_name].append(metric)
                        
                    # Create data series for multi-line chart
                    data_series = [
                        (metrics, "execution_time_ms", operation)
                        for operation, metrics in grouped_trends.items()
                    ]
                    
                    if data_series:
                        trends_chart = self.chart_generator.generate_multi_line_chart(
                            data_series=data_series,
                            x_key="timestamp",
                            title="Performance Trends",
                            x_label="Time",
                            y_label="Execution Time (ms)",
                            as_base64=True
                        )
                        charts["trends"] = trends_chart
                        
        except Exception as e:
            self.logger.error(f"Error generating component charts: {e}")
            
        return charts
        
    async def _handle_generate_report(self, task: Task) -> TaskResult:
        """Handle the generate_report operation.
        
        Args:
            task: The task containing report details
            
        Returns:
            A TaskResult with the generated report information
        """
        # Extract required parameters
        report_type = task.input_data.get("report_type")
        if not report_type:
            return self._create_error_result(task, "Missing 'report_type' field")
            
        # Check if the report type is supported
        supported_report_types = ["system", "health", "alerts", "performance", "summary"]
        if report_type not in supported_report_types:
            return self._create_error_result(
                task, 
                f"Unsupported report type: {report_type}. Supported types: {', '.join(supported_report_types)}"
            )
            
        # Extract optional parameters
        title = task.input_data.get("title", f"{report_type.capitalize()} Report")
        time_window = task.input_data.get("time_window", "7d")
        
        # Generate a unique report ID if not provided
        report_id = task.input_data.get("report_id", f"{report_type}_report_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        
        # Build the report configuration
        report_config = {
            "id": report_id,
            "type": report_type,
            "title": title,
            "time_window": time_window,
            "created_at": datetime.now().isoformat()
        }
        
        # Generate the report
        report_html = await self._generate_report_html(report_config)
        
        # Save the report
        report_path = os.path.join(self.output_dir, f"{report_id}.html")
        with open(report_path, "w") as f:
            f.write(report_html)
            
        # Save the report configuration
        config_path = os.path.join(self.output_dir, f"{report_id}.json")
        with open(config_path, "w") as f:
            json.dump(report_config, f, indent=2)
            
        return self._create_success_result(task, {
            "message": "Report generated successfully",
            "report_id": report_id,
            "report_path": report_path,
            "report_url": f"/dashboards/{report_id}.html",
            "config": report_config
        })
        
    async def _handle_get_dashboard_url(self, task: Task) -> TaskResult:
        """Handle the get_dashboard_url operation.
        
        Args:
            task: The task containing dashboard ID
            
        Returns:
            A TaskResult with the dashboard URL
        """
        # Extract required parameters
        dashboard_id = task.input_data.get("dashboard_id")
        if not dashboard_id:
            return self._create_error_result(task, "Missing 'dashboard_id' field")
            
        # Check if the dashboard exists
        dashboard_path = os.path.join(self.output_dir, f"{dashboard_id}.html")
        if not os.path.exists(dashboard_path):
            return self._create_error_result(task, f"Dashboard not found: {dashboard_id}")
            
        # Get the dashboard configuration
        config_path = os.path.join(self.output_dir, f"{dashboard_id}.json")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                dashboard_config = json.load(f)
        else:
            dashboard_config = {
                "id": dashboard_id,
                "url": f"/dashboards/{dashboard_id}.html"
            }
            
        return self._create_success_result(task, {
            "dashboard_id": dashboard_id,
            "dashboard_url": f"/dashboards/{dashboard_id}.html",
            "config": dashboard_config
        })
        
    async def _handle_list_dashboards(self, task: Task) -> TaskResult:
        """Handle the list_dashboards operation.
        
        Args:
            task: The task with optional filter parameters
            
        Returns:
            A TaskResult with a list of available dashboards
        """
        # Extract optional parameters
        dashboard_type = task.input_data.get("dashboard_type")
        
        # Get all dashboard configuration files
        dashboards = []
        for filename in os.listdir(self.output_dir):
            if filename.endswith(".json") and "report" not in filename:
                config_path = os.path.join(self.output_dir, filename)
                try:
                    with open(config_path, "r") as f:
                        dashboard_config = json.load(f)
                        
                    # Apply dashboard type filter if specified
                    if dashboard_type and dashboard_config.get("type") != dashboard_type:
                        continue
                        
                    dashboards.append({
                        "id": dashboard_config.get("id"),
                        "type": dashboard_config.get("type"),
                        "title": dashboard_config.get("title"),
                        "url": f"/dashboards/{dashboard_config.get('id')}.html",
                        "created_at": dashboard_config.get("created_at"),
                        "updated_at": dashboard_config.get("updated_at")
                    })
                except Exception as e:
                    self.logger.error(f"Error loading dashboard config {filename}: {e}")
                    
        # Sort dashboards by created_at (newest first)
        dashboards.sort(key=lambda d: d.get("created_at", ""), reverse=True)
        
        return self._create_success_result(task, {
            "dashboards": dashboards,
            "count": len(dashboards)
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
                "dashboard_count": len([f for f in os.listdir(self.output_dir) if f.endswith(".html")])
            })
        else:
            return self._create_error_result(task, "DashboardGenerator health check failed")
            
    async def health_check(self) -> bool:
        """Perform a health check on the DashboardGenerator.
        
        Returns:
            True if healthy, False otherwise
        """
        # Check if output directory is accessible
        try:
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir, exist_ok=True)
                
            # Write a test file to ensure we have write permissions
            test_file = os.path.join(self.output_dir, "health_check.txt")
            with open(test_file, "w") as f:
                f.write("Health check passed")
                
            # Remove the test file
            os.remove(test_file)
            
            return True
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
            
    async def _generate_dashboard_html(self, config: Dict[str, Any]) -> str:
        """Generate HTML for a dashboard using Jinja2 templates.
        
        Args:
            config: Dashboard configuration
            
        Returns:
            HTML content for the dashboard
        """
        try:
            # Load the base dashboard template
            template = self.jinja_env.get_template('base_dashboard.html')
            
            # Prepare component data
            components = []
            for component_name in config.get("components", []):
                components.append({
                    "name": component_name,
                    "title": component_name.replace("_", " ").title(),
                    "loading": True,  # Initially set to loading
                    "content": f"Loading {component_name} data..."
                })
            
            # Render the template with configuration
            return template.render(
                title=config.get("title", "Monitoring Dashboard"),
                refresh_interval=config.get("refresh_interval", 60),
                components=components,
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        except Exception as e:
            self.logger.error(f"Error generating dashboard HTML: {e}")
            # Fall back to a simple HTML template if there's an error
            return f"""<!DOCTYPE html>
<html>
<head><title>Error</title></head>
<body>
    <h1>Error Generating Dashboard</h1>
    <p>An error occurred while generating the dashboard: {str(e)}</p>
</body>
</html>"""
        
    async def _generate_report_html(self, config: Dict[str, Any]) -> str:
        """Generate HTML for a report using Jinja2 templates.
        
        Args:
            config: Report configuration
            
        Returns:
            HTML content for the report
        """
        try:
            # Load the base report template
            template = self.jinja_env.get_template('base_report.html')
            
            # Prepare dummy sections for demo
            report_type = config.get("type", "summary")
            sections = []
            
            if report_type == "system":
                sections = [
                    {
                        "title": "System Overview",
                        "content": "<p>This section provides an overview of system resource utilization.</p>",
                        "chart": True
                    },
                    {
                        "title": "CPU Utilization",
                        "content": "<p>CPU utilization details would be shown here.</p>",
                        "chart": True,
                        "table": {
                            "headers": ["Time", "Usage (%)", "Processes", "Status"],
                            "rows": [
                                ["2023-01-01 12:00", "45%", "120", "Normal"],
                                ["2023-01-01 13:00", "50%", "125", "Normal"],
                                ["2023-01-01 14:00", "75%", "130", "Warning"]
                            ]
                        }
                    }
                ]
            elif report_type == "health":
                sections = [
                    {
                        "title": "Component Health Summary",
                        "content": "<p>Overall health status of all components.</p>",
                        "chart": True
                    }
                ]
            elif report_type == "alerts":
                sections = [
                    {
                        "title": "Alert Distribution",
                        "content": "<p>Distribution of alerts by severity and component.</p>",
                        "chart": True
                    }
                ]
            elif report_type == "performance":
                sections = [
                    {
                        "title": "Performance Trends",
                        "content": "<p>Performance trends over time.</p>",
                        "chart": True
                    }
                ]
            else:  # summary
                sections = [
                    {
                        "title": "System Health",
                        "content": "<p>Overall system health status.</p>"
                    },
                    {
                        "title": "Recent Alerts",
                        "content": "<p>Recent alerts would be listed here.</p>"
                    }
                ]
            
            # Generate a summary based on the report type
            summary = f"This report provides an overview of {report_type} metrics for the specified time period."
            
            # Render the template with configuration
            return template.render(
                title=config.get("title", f"{report_type.capitalize()} Report"),
                time_window=config.get("time_window", "7d"),
                summary=summary,
                sections=sections,
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                report_id=config.get("id", "unknown")
            )
        except Exception as e:
            self.logger.error(f"Error generating report HTML: {e}")
            # Fall back to a simple HTML template if there's an error
            return f"""<!DOCTYPE html>
<html>
<head><title>Error</title></head>
<body>
    <h1>Error Generating Report</h1>
    <p>An error occurred while generating the report: {str(e)}</p>
</body>
</html>""" 