# BOSS Monitoring System

This directory contains the monitoring system components for the BOSS platform.

## Components

### Core Components

- **BaseMonitoring**: Base class for all monitoring components (`base_monitoring.py`)
- **MetricsStorage**: Handles storage and retrieval of monitoring metrics (`metrics_storage.py`)
- **ChartGenerator**: Generates visualization charts for metrics data (`chart_generator.py`)
- **DashboardGenerator**: Creates monitoring dashboards and reports (`dashboard_generator.py`)
- **DashboardComponents**: Helper classes for dashboard generation (`dashboard_components.py`)
- **MonitoringAPI**: REST API for the monitoring system (`api.py`)
- **MonitoringService**: Service to start and manage the monitoring system (`start_monitoring.py`)

### Metric Collection

- **SystemMetricsCollector**: Collects system metrics (CPU, memory, disk usage)
- **ComponentHealthChecker**: Checks the health of system components
- **PerformanceMetricsTracker**: Tracks performance metrics of system components

### Alerting and Notification

- **AlertManager**: Manages alert rules and alert generation
- **NotificationManager**: Manages notification channels and delivery

## Recent Refactoring

The monitoring system has undergone significant refactoring to improve maintainability and reduce code complexity:

1. **DashboardGenerator Refactoring** (Completed March 7, 2025)
   - Split into multiple files to reduce complexity and improve maintainability:
     - `dashboard_generator.py` (Main component) - Handles core functionality and dashboard generation
     - `dashboard_components.py` (New file) - Contains specialized helper classes:
       - `DashboardTemplateRenderer` - Handles template rendering with Jinja2
       - `DashboardDataProcessor` - Processes raw data into dashboard-ready formats
   - Made all methods asynchronous for better performance and concurrency
   - Added proper type annotations and improved error handling
   - Added comprehensive unit tests for all components

   **Benefits of this refactoring:**
   - Reduced file size from 971 lines to about 400-500 lines per file
   - Improved separation of concerns between components
   - Enhanced testability with more focused components
   - Better reusability of dashboard-related functionality

2. **Visualization Improvements**
   - Enhanced chart generation capabilities with more chart types
   - Improved dashboard templates with better UI/UX
   - Added support for custom dashboards and report generation

3. **API Integration**
   - Added REST API for accessing monitoring data and dashboards
   - Integrated API with the monitoring service for a unified experience

## Dashboard Components Structure

### DashboardGenerator
The main component that orchestrates dashboard creation:
- Handles dashboard and report requests
- Manages component data retrieval
- Controls chart generation
- Produces final HTML output

### DashboardTemplateRenderer
Specialized component for template rendering:
- Manages Jinja2 template environment
- Renders dashboard and report templates
- Provides utility methods for formatting data in templates

### DashboardDataProcessor
Specialized component for data processing:
- Transforms raw metric data into dashboard-friendly formats
- Calculates summaries and aggregations
- Prepares data for visualization

## Usage

### Starting the Monitoring Service

```python
from boss.lighthouse.monitoring.start_monitoring import MonitoringService

# Start the monitoring service
service = MonitoringService(data_dir="/path/to/data")
service.start()
```

### Accessing Dashboards

Dashboards can be accessed through the API:

- System Dashboard: `http://localhost:8080/dashboards/system`
- Health Dashboard: `http://localhost:8080/dashboards/health`
- Alerts Dashboard: `http://localhost:8080/dashboards/alerts`
- Performance Dashboard: `http://localhost:8080/dashboards/performance`

### API Documentation

The monitoring API provides endpoints for:

- Retrieving system metrics
- Checking component health
- Managing alerts and notifications
- Generating dashboards and reports

For more details, see the API documentation in `docs/api/monitoring_api.md`. 