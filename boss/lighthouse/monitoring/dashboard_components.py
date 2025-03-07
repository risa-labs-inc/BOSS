"""Dashboard components for template rendering and data processing.

This module contains helper classes for the DashboardGenerator component.
"""

import logging
import jinja2
import os
import json
from typing import Any, Dict, List, Optional, Sequence
from datetime import datetime, timedelta

logger = logging.getLogger("boss.lighthouse.monitoring.dashboard_components")

class DashboardTemplateRenderer:
    """Handles the rendering of dashboard and report templates.
    
    This class provides methods for rendering Jinja2 templates for dashboards
    and reports, managing template loading and context application.
    
    Attributes:
        template_dir: Directory containing dashboard templates
        env: Jinja2 environment for template rendering
    """
    
    def __init__(self, template_dir: str) -> None:
        """Initialize the DashboardTemplateRenderer.
        
        Args:
            template_dir: Directory containing dashboard templates
        """
        self.template_dir = template_dir
        
        # Set up Jinja2 environment
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            autoescape=jinja2.select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        self.env.filters['format_timestamp'] = self._format_timestamp
        self.env.filters['format_duration'] = self._format_duration
    
    def render_dashboard(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a dashboard template.
        
        Args:
            template_name: Name of the dashboard template (without extension)
            context: Context data to pass to the template
            
        Returns:
            Rendered HTML
        """
        try:
            template = self.env.get_template(f"{template_name}.html")
            return template.render(**context)
        except jinja2.exceptions.TemplateNotFound:
            # Fallback to base template if specific one not found
            template = self.env.get_template("base_dashboard.html")
            return template.render(**context)
    
    def render_report(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a report template.
        
        Args:
            template_name: Name of the report template (without extension)
            context: Context data to pass to the template
            
        Returns:
            Rendered HTML
        """
        try:
            template = self.env.get_template(f"{template_name}.html")
            return template.render(**context)
        except jinja2.exceptions.TemplateNotFound:
            # Fallback to base template if specific one not found
            template = self.env.get_template("base_report.html")
            return template.render(**context)
    
    @staticmethod
    def _format_timestamp(timestamp: str) -> str:
        """Format a timestamp string for display.
        
        Args:
            timestamp: ISO format timestamp
            
        Returns:
            Formatted timestamp string
        """
        from datetime import datetime
        
        try:
            dt = datetime.fromisoformat(timestamp)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return timestamp
    
    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format a duration in seconds for display.
        
        Args:
            seconds: Duration in seconds
            
        Returns:
            Formatted duration string
        """
        if seconds < 0.001:  # microseconds
            return f"{seconds * 1000000:.2f} μs"
        elif seconds < 1:  # milliseconds
            return f"{seconds * 1000:.2f} ms"
        elif seconds < 60:  # seconds
            return f"{seconds:.2f} s"
        elif seconds < 3600:  # minutes
            minutes, sec = divmod(seconds, 60)
            return f"{int(minutes)}m {int(sec)}s"
        else:  # hours
            hours, remainder = divmod(seconds, 3600)
            minutes, sec = divmod(remainder, 60)
            return f"{int(hours)}h {int(minutes)}m {int(sec)}s"


class DashboardDataProcessor:
    """Static class for processing dashboard data.
    
    This class provides methods for processing raw metrics and monitoring data
    into formats suitable for dashboard display and visualization.
    """
    
    @staticmethod
    def process_system_metrics(system_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Process system metrics data for dashboard display.
        
        Args:
            system_metrics: Raw system metrics data
            
        Returns:
            Processed system metrics data
        """
        result: Dict[str, Any] = {
            "summary": {},
            "time_series": {},
            "latest": {}
        }
        
        if not system_metrics:
            return result
        
        # Extract time series data
        time_series = system_metrics.get("time_series", {})
        result["time_series"] = time_series
        
        # Calculate summary statistics
        if time_series:
            timestamps = time_series.get("timestamps", [])
            if timestamps:
                # Get latest values
                latest_index = -1
                
                # CPU
                cpu_values = time_series.get("cpu", [])
                if cpu_values and len(cpu_values) > 0:
                    result["latest"]["cpu"] = cpu_values[latest_index]
                    result["summary"]["avg_cpu"] = sum(cpu_values) / len(cpu_values)
                    result["summary"]["max_cpu"] = max(cpu_values)
                
                # Memory
                memory_values = time_series.get("memory", [])
                if memory_values and len(memory_values) > 0:
                    result["latest"]["memory"] = memory_values[latest_index]
                    result["summary"]["avg_memory"] = sum(memory_values) / len(memory_values)
                    result["summary"]["max_memory"] = max(memory_values)
                
                # Disk
                disk_values = time_series.get("disk", [])
                if disk_values and len(disk_values) > 0:
                    result["latest"]["disk"] = disk_values[latest_index]
                    result["summary"]["avg_disk"] = sum(disk_values) / len(disk_values)
                    result["summary"]["max_disk"] = max(disk_values)
        
        return result
    
    @staticmethod
    def process_health_data(health_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process component health data for dashboard display.
        
        Args:
            health_data: Raw component health data
            
        Returns:
            Processed component health data
        """
        result: Dict[str, Any] = {
            "summary": {
                "healthy": 0,
                "warning": 0,
                "critical": 0,
                "unknown": 0,
                "total": 0
            },
            "components": {}
        }
        
        if not health_data:
            return result
        
        components = health_data.get("components", {})
        result["components"] = components
        
        # Count components by status
        for component_name, component_data in components.items():
            status = component_data.get("status", "unknown").lower()
            result["summary"]["total"] += 1
            
            if status == "healthy":
                result["summary"]["healthy"] += 1
            elif status == "warning":
                result["summary"]["warning"] += 1
            elif status == "critical":
                result["summary"]["critical"] += 1
            else:
                result["summary"]["unknown"] += 1
        
        return result
    
    @staticmethod
    def process_alerts_data(alerts_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process alerts data for dashboard display.
        
        Args:
            alerts_data: Raw alerts data
            
        Returns:
            Processed alerts data
        """
        result: Dict[str, Any] = {
            "summary": {
                "critical": 0,
                "error": 0,
                "warning": 0,
                "info": 0,
                "total": 0,
                "active": 0,
                "resolved": 0
            },
            "alerts": [],
            "history": []
        }
        
        if not alerts_data:
            return result
        
        # Process active alerts
        active_alerts = alerts_data.get("active_alerts", [])
        result["alerts"] = active_alerts
        
        # Process alert history
        alert_history = alerts_data.get("alert_history", [])
        result["history"] = alert_history
        
        # Count alerts by severity and status
        for alert in active_alerts:
            severity = alert.get("severity", "info").lower()
            result["summary"]["total"] += 1
            result["summary"]["active"] += 1
            
            if severity == "critical":
                result["summary"]["critical"] += 1
            elif severity == "error":
                result["summary"]["error"] += 1
            elif severity == "warning":
                result["summary"]["warning"] += 1
            elif severity == "info":
                result["summary"]["info"] += 1
        
        # Count resolved alerts
        for alert in alert_history:
            if alert.get("status") == "resolved":
                result["summary"]["resolved"] += 1
        
        return result
    
    @staticmethod
    def process_performance_data(performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process performance metrics data for dashboard display.
        
        Args:
            performance_data: Raw performance metrics data
            
        Returns:
            Processed performance metrics data
        """
        result: Dict[str, Any] = {
            "summary": {
                "avg_execution_time": 0,
                "max_execution_time": 0,
                "throughput": 0
            },
            "component_stats": {},
            "time_series": {}
        }
        
        if not performance_data:
            return result
        
        # Extract component stats
        component_stats = performance_data.get("component_stats", {})
        result["component_stats"] = component_stats
        
        # Extract time series data
        time_series = performance_data.get("time_series", {})
        result["time_series"] = time_series
        
        # Calculate overall summary statistics
        if component_stats:
            execution_times = []
            for component, stats in component_stats.items():
                avg_time = stats.get("avg_execution_time", 0)
                if avg_time:
                    execution_times.append(avg_time)
            
            if execution_times:
                result["summary"]["avg_execution_time"] = sum(execution_times) / len(execution_times)
                result["summary"]["max_execution_time"] = max(execution_times)
        
        # Calculate throughput if available
        if time_series:
            throughput_values = time_series.get("throughput", [])
            if throughput_values:
                result["summary"]["throughput"] = sum(throughput_values) / len(throughput_values)
        
        return result 