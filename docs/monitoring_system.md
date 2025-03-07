# BOSS Monitoring System

## Overview

The BOSS Monitoring System is a comprehensive solution for collecting, analyzing, and visualizing system metrics, component health, and performance metrics. It provides a modular architecture that can be easily extended and customized for different monitoring needs.

## Components

The monitoring system consists of the following core components:

### 1. System Metrics Collector

This component is responsible for collecting system-level metrics such as:
- CPU usage
- Memory usage
- Disk usage
- Network usage

It provides real-time monitoring of system resources and stores the collected metrics for historical analysis.

### 2. Component Health Checker

This component checks the health of various system components by:
- Performing health checks
- Measuring response times
- Tracking uptime
- Storing health check results for trend analysis

### 3. Performance Metrics Tracker

This component tracks performance metrics for various operations and components:
- Measures execution time
- Records success/failure rates
- Analyzes performance trends
- Provides alerts for performance degradation

### 4. Dashboard Generator

This component generates visualizations and dashboards for monitoring data:
- Creates HTML dashboards for different monitoring aspects
- Generates charts and graphs for metrics visualization
- Supports various dashboard types (system, health, performance, alerts)
- Provides customizable dashboard layouts

### 5. Metrics Storage

This component manages the storage and retrieval of monitoring data:
- Stores system metrics, health checks, and performance metrics
- Provides query interface for metrics analysis
- Handles data retention policies
- Ensures thread-safe database operations

### 6. Chart Generator

This component generates various types of charts for metrics visualization:
- Line charts for time-series data
- Bar charts for comparative analysis
- Pie charts for distribution visualization
- Multi-line charts for trend comparison

### 7. Monitoring API

This component provides a REST API for accessing monitoring data:
- System metrics endpoints
- Health check endpoints
- Performance metrics endpoints
- Dashboard generation and viewing endpoints

## Installation

### Prerequisites

- Python 3.10 or higher
- Poetry for dependency management

### Installation Steps

1. Clone the repository
2. Install dependencies with Poetry:

```bash
cd BOSS
poetry install
```

## Usage

### Starting the Monitoring Service

You can start the monitoring service with the following command:

```bash
python -m boss.lighthouse.monitoring.start_monitoring --data-dir /path/to/data --host 0.0.0.0 --port 8080
```

Options:
- `--data-dir`: Directory where monitoring data will be stored (default: `./monitoring_data`)
- `--host`: Host to bind the API server to (default: `0.0.0.0`)
- `--port`: Port to bind the API server to (default: `8080`)

### Using the Monitoring API

Once the monitoring service is running, you can access the API at `http://localhost:8080`.

#### API Endpoints

##### System Metrics

- `GET /metrics/system`: Get system metrics
  - Query parameters:
    - `metric_type`: Type of metric (cpu, memory, disk, network)
    - `start_time`: Start time (ISO format)
    - `end_time`: End time (ISO format)
    - `limit`: Maximum number of metrics to return

- `POST /metrics/system/collect`: Trigger collection of system metrics
  - Query parameters:
    - `metrics_type`: Type of metrics to collect (all, cpu, memory, disk, network)

##### Component Health

- `GET /health/components`: Get health status of all components

- `GET /health/components/{component_id}`: Get health history for a specific component
  - Path parameters:
    - `component_id`: ID of the component
  - Query parameters:
    - `start_time`: Start time (ISO format)
    - `end_time`: End time (ISO format)
    - `limit`: Maximum number of health checks to return

- `POST /health/components/{component_id}/check`: Check health of a specific component
  - Path parameters:
    - `component_id`: ID of the component
  - Query parameters:
    - `timeout_ms`: Timeout in milliseconds (default: 5000)

##### Performance Metrics

- `GET /metrics/performance`: Get performance metrics
  - Query parameters:
    - `component_id`: ID of the component
    - `operation_name`: Name of the operation
    - `start_time`: Start time (ISO format)
    - `end_time`: End time (ISO format)
    - `limit`: Maximum number of metrics to return

- `POST /metrics/performance/record`: Record a performance metric
  - Query parameters:
    - `component_id`: ID of the component
    - `operation_name`: Name of the operation
    - `execution_time_ms`: Execution time in milliseconds
    - `success`: Whether the operation was successful (default: true)
    - `metadata`: Additional metadata as JSON string

##### Dashboards

- `GET /dashboards`: List available dashboards

- `POST /dashboards/generate`: Generate a dashboard
  - Query parameters:
    - `dashboard_type`: Type of dashboard to generate (system, health, performance, alerts)
    - `title`: Dashboard title (optional)
    - `time_window`: Time window for metrics (e.g., 1h, 24h, 7d)

- `GET /dashboards/{dashboard_id}`: Get a dashboard
  - Path parameters:
    - `dashboard_id`: ID of the dashboard

## Programmatic Usage

You can also use the monitoring components programmatically in your code:

```python
from boss.lighthouse.monitoring.system_metrics_collector import SystemMetricsCollector
from boss.lighthouse.monitoring.component_health_checker import ComponentHealthChecker
from boss.core.task_models import Task

# Initialize components
metadata = {"component_name": "my_component"}
metrics_collector = SystemMetricsCollector(metadata)
health_checker = ComponentHealthChecker(metadata)

# Collect system metrics
async def collect_metrics():
    task = Task(operation="collect_system_metrics", input_data={"metrics_type": "cpu"})
    result = await metrics_collector.resolve(task)
    print(result.output_data)

# Check component health
async def check_health():
    task = Task(operation="check_component_health", input_data={"component_id": "my_component"})
    result = await health_checker.resolve(task)
    print(result.output_data)
```

## Extending the Monitoring System

The monitoring system is designed to be easily extended with new components and metrics. 

### Adding a New Metrics Collector

1. Create a new class that extends `BaseMonitoring`
2. Implement the `resolve` method to handle specific operations
3. Add methods to collect and store the new metrics

### Adding a New Dashboard Type

1. Update the `dashboard_configs` dictionary in `DashboardGenerator`
2. Implement methods to collect and visualize the new dashboard data
3. Create templates for the new dashboard type

## Configuration

The monitoring system can be configured through the metadata passed to the components. The following configuration options are available:

- `data_dir`: Directory where monitoring data is stored
- `retention_days`: Number of days to keep monitoring data (default: 30)
- `collection_interval`: Interval in seconds between metric collections (default: 60)
- `health_check_interval`: Interval in seconds between health checks (default: 300)
- `dashboard_refresh_interval`: Interval in seconds between dashboard refreshes (default: varies by dashboard type)

## Troubleshooting

### Common Issues

#### API Server Won't Start

- Check if the port is already in use
- Ensure you have the required permissions to bind to the specified host and port

#### Metrics Not Being Collected

- Check if the system metrics collector is running
- Verify that the data directory is writable
- Look for error messages in the logs

#### Charts Not Being Generated

- Ensure matplotlib is installed
- Check if the chart directory is writable
- Verify that metrics data exists for the specified time range

## Development

### Adding New Chart Types

1. Update the `ChartGenerator` class with a new method for the chart type
2. Implement the chart generation logic using matplotlib
3. Update the `_generate_component_charts` method in `DashboardGenerator` to use the new chart type

### Adding New API Endpoints

1. Update the `_configure_routes` method in `MonitoringAPI`
2. Add route handlers for the new endpoints
3. Update the documentation to reflect the new endpoints 