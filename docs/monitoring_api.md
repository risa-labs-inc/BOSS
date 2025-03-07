# BOSS Monitoring API Documentation

## Overview

The BOSS Monitoring System provides a comprehensive set of components for monitoring system health, performance, and generating alerts. This document provides detailed API documentation for the monitoring components.

## Table of Contents

1. [MonitoringResolver](#monitoringresolver)
2. [SystemMetricsCollector](#systemmetricscollector)
3. [ComponentHealthChecker](#componenthealthchecker)
4. [PerformanceMetricsTracker](#performancemetricstracker)
5. [AlertManager](#alertmanager)
6. [DashboardGenerator](#dashboardgenerator)
7. [MetricsStorage](#metricsstorage)

---

## MonitoringResolver

The `MonitoringResolver` serves as a bridge to the specialized monitoring components. It routes operations to the appropriate component and provides backward compatibility with legacy implementations.

### Operations

| Operation | Description |
|-----------|-------------|
| `collect_system_metrics` | Collect metrics about system resources (CPU, memory, disk, network) |
| `get_system_metrics` | Retrieve system metrics for a specified time window |
| `clear_old_metrics` | Delete old metrics data beyond the retention period |
| `check_component_health` | Check the health of a specific component |
| `get_health_history` | Retrieve health check history for a component |
| `check_all_components` | Check the health of all registered components |
| `clear_old_health_checks` | Delete old health check data beyond the retention period |
| `record_performance_metric` | Record a performance metric for an operation |
| `get_performance_metrics` | Retrieve performance metrics for a component or operation |
| `analyze_performance_trend` | Analyze performance trends over time |
| `generate_alert` | Generate a new alert |
| `update_alert` | Update an existing alert |
| `get_active_alerts` | Get a list of active alerts with optional filtering |
| `get_alert_history` | Get a list of historical alerts with optional filtering |
| `acknowledge_alert` | Acknowledge an alert |
| `resolve_alert` | Resolve an alert |
| `clear_old_alerts` | Delete old resolved alerts beyond the retention period |
| `update_notification_channels` | Update alert notification channels |
| `generate_dashboard` | Generate a monitoring dashboard |
| `generate_report` | Generate a monitoring report |
| `get_dashboard_url` | Get the URL for a specific dashboard |
| `list_dashboards` | List available dashboards |
| `health_check` | Check the health of all monitoring components |

### Example Usage

```python
from boss.core.task import Task
from boss.lighthouse.monitoring_resolver import MonitoringResolver

# Initialize the resolver
resolver = MonitoringResolver(metadata)

# Create a task to collect system metrics
task = Task(
    id="task_id",
    resolver_name="MonitoringResolver",
    input_data={
        "operation": "collect_system_metrics",
        "metrics_type": "cpu"
    }
)

# Resolve the task
result = await resolver.resolve(task)
```

---

## SystemMetricsCollector

The `SystemMetricsCollector` component collects and manages system resource metrics, such as CPU, memory, disk, and network usage.

### Operations

| Operation | Description |
|-----------|-------------|
| `collect_system_metrics` | Collect metrics about system resources |
| `get_system_metrics` | Retrieve system metrics for a specified time window |
| `clear_old_metrics` | Delete old metrics data beyond the retention period |
| `get_system_info` | Get general system information |
| `health_check` | Check the health of the SystemMetricsCollector |

### Input Data for Operations

#### `collect_system_metrics`

```json
{
  "operation": "collect_system_metrics",
  "metrics_type": "cpu" // Optional: "cpu", "memory", "disk", "network", or omit for all
}
```

#### `get_system_metrics`

```json
{
  "operation": "get_system_metrics",
  "metrics_type": "cpu", // Optional: "cpu", "memory", "disk", "network", or omit for all
  "time_window": "24h", // Optional: time window in format "Xh", "Xd", "Xw"
  "aggregation": "hourly" // Optional: "hourly", "daily", or omit for no aggregation
}
```

#### `clear_old_metrics`

```json
{
  "operation": "clear_old_metrics",
  "retention_days": 30 // Optional: number of days to retain data
}
```

#### `get_system_info`

```json
{
  "operation": "get_system_info"
}
```

#### `health_check`

```json
{
  "operation": "health_check"
}
```

---

## ComponentHealthChecker

The `ComponentHealthChecker` component monitors the health of system components and tracks their response times.

### Operations

| Operation | Description |
|-----------|-------------|
| `check_component_health` | Check the health of a specific component |
| `get_health_history` | Retrieve health check history for a component |
| `check_all_components` | Check the health of all registered components |
| `clear_old_health_checks` | Delete old health check data beyond the retention period |
| `health_check` | Check the health of the ComponentHealthChecker |

### Input Data for Operations

#### `check_component_health`

```json
{
  "operation": "check_component_health",
  "component_id": "component-name",
  "timeout": 5.0 // Optional: timeout in seconds
}
```

#### `get_health_history`

```json
{
  "operation": "get_health_history",
  "component_id": "component-name",
  "time_window": "24h" // Optional: time window in format "Xh", "Xd", "Xw"
}
```

#### `check_all_components`

```json
{
  "operation": "check_all_components",
  "timeout": 5.0 // Optional: timeout in seconds
}
```

#### `clear_old_health_checks`

```json
{
  "operation": "clear_old_health_checks",
  "retention_days": 30 // Optional: number of days to retain data
}
```

#### `health_check`

```json
{
  "operation": "health_check"
}
```

---

## PerformanceMetricsTracker

The `PerformanceMetricsTracker` component tracks the performance of operations and analyzes performance trends over time.

### Operations

| Operation | Description |
|-----------|-------------|
| `record_performance_metric` | Record a performance metric for an operation |
| `get_performance_metrics` | Retrieve performance metrics for a component or operation |
| `analyze_performance_trend` | Analyze performance trends over time |
| `clear_old_metrics` | Delete old metrics data beyond the retention period |
| `health_check` | Check the health of the PerformanceMetricsTracker |

### Input Data for Operations

#### `record_performance_metric`

```json
{
  "operation": "record_performance_metric",
  "component_id": "component-name",
  "operation_name": "operation-name",
  "execution_time_ms": 150,
  "success": true,
  "details": {} // Optional: additional details
}
```

#### `get_performance_metrics`

```json
{
  "operation": "get_performance_metrics",
  "component_id": "component-name", // Optional: filter by component
  "operation_name": "operation-name", // Optional: filter by operation
  "time_window": "24h", // Optional: time window in format "Xh", "Xd", "Xw"
  "success": true // Optional: filter by success status
}
```

#### `analyze_performance_trend`

```json
{
  "operation": "analyze_performance_trend",
  "component_id": "component-name",
  "operation_name": "operation-name",
  "time_window": "7d" // Optional: time window in format "Xh", "Xd", "Xw"
}
```

#### `clear_old_metrics`

```json
{
  "operation": "clear_old_metrics",
  "retention_days": 30 // Optional: number of days to retain data
}
```

#### `health_check`

```json
{
  "operation": "health_check"
}
```

---

## AlertManager

The `AlertManager` component handles the generation, management, and notification of system alerts.

### Operations

| Operation | Description |
|-----------|-------------|
| `generate_alert` | Generate a new alert |
| `update_alert` | Update an existing alert |
| `get_active_alerts` | Get a list of active alerts with optional filtering |
| `get_alert_history` | Get a list of historical alerts with optional filtering |
| `acknowledge_alert` | Acknowledge an alert |
| `resolve_alert` | Resolve an alert |
| `clear_old_alerts` | Delete old resolved alerts beyond the retention period |
| `update_notification_channels` | Update alert notification channels |
| `health_check` | Check the health of the AlertManager |

### Input Data for Operations

#### `generate_alert`

```json
{
  "operation": "generate_alert",
  "component_id": "component-name",
  "alert_type": "performance",
  "message": "High CPU usage detected",
  "severity": "high", // "critical", "high", "medium", "low", "info"
  "details": {
    "metric": "cpu_usage",
    "value": 95.5,
    "threshold": 90.0
  }
}
```

#### `update_alert`

```json
{
  "operation": "update_alert",
  "alert_id": "alert-uuid",
  "message": "Updated alert message", // Optional
  "severity": "critical", // Optional
  "details": {}, // Optional
  "status": "acknowledged" // Optional: "active", "acknowledged", "resolved"
}
```

#### `get_active_alerts`

```json
{
  "operation": "get_active_alerts",
  "component_id": "component-name", // Optional: filter by component
  "severity": "high", // Optional: filter by severity
  "alert_type": "performance" // Optional: filter by alert type
}
```

#### `get_alert_history`

```json
{
  "operation": "get_alert_history",
  "component_id": "component-name", // Optional: filter by component
  "severity": "high", // Optional: filter by severity
  "alert_type": "performance", // Optional: filter by alert type
  "time_window": "7d" // Optional: time window in format "Xh", "Xd", "Xw"
}
```

#### `acknowledge_alert`

```json
{
  "operation": "acknowledge_alert",
  "alert_id": "alert-uuid",
  "message": "Investigating the issue" // Optional: acknowledgement message
}
```

#### `resolve_alert`

```json
{
  "operation": "resolve_alert",
  "alert_id": "alert-uuid",
  "message": "Issue has been fixed" // Optional: resolution message
}
```

#### `clear_old_alerts`

```json
{
  "operation": "clear_old_alerts",
  "retention_days": 30 // Optional: number of days to retain data
}
```

#### `update_notification_channels`

```json
{
  "operation": "update_notification_channels",
  "channels": ["log", "email", "webhook"] // List of channels to enable
}
```

#### `health_check`

```json
{
  "operation": "health_check"
}
```

---

## DashboardGenerator

The `DashboardGenerator` component generates HTML dashboards and reports based on monitoring data from other components.

### Operations

| Operation | Description |
|-----------|-------------|
| `generate_dashboard` | Generate a monitoring dashboard |
| `generate_report` | Generate a monitoring report |
| `get_dashboard_url` | Get the URL for a specific dashboard |
| `list_dashboards` | List available dashboards |
| `health_check` | Check the health of the DashboardGenerator |

### Input Data for Operations

#### `generate_dashboard`

```json
{
  "operation": "generate_dashboard",
  "dashboard_type": "system", // "system", "health", "alerts", "performance"
  "title": "Custom Dashboard Title", // Optional
  "time_window": "24h", // Optional: time window in format "Xh", "Xd", "Xw"
  "refresh_interval": 60 // Optional: refresh interval in seconds
}
```

#### `generate_report`

```json
{
  "operation": "generate_report",
  "report_type": "system", // "system", "health", "alerts", "performance", "summary"
  "title": "Custom Report Title", // Optional
  "time_window": "7d" // Optional: time window in format "Xh", "Xd", "Xw"
}
```

#### `get_dashboard_url`

```json
{
  "operation": "get_dashboard_url",
  "dashboard_id": "dashboard-id"
}
```

#### `list_dashboards`

```json
{
  "operation": "list_dashboards",
  "dashboard_type": "system" // Optional: filter by dashboard type
}
```

#### `health_check`

```json
{
  "operation": "health_check"
}
```

---

## MetricsStorage

The `MetricsStorage` component provides a storage mechanism for persisting monitoring metrics using SQLite.

### Methods

| Method | Description |
|--------|-------------|
| `store_system_metric` | Store a system metric in the database |
| `get_system_metrics` | Retrieve system metrics from the database |
| `clear_old_system_metrics` | Delete system metrics older than the specified retention period |
| `store_health_check` | Store a component health check result |
| `get_health_history` | Retrieve component health history |
| `clear_old_health_checks` | Delete health checks older than the specified retention period |
| `store_performance_metric` | Store a performance metric |
| `get_performance_metrics` | Retrieve performance metrics |
| `clear_old_performance_metrics` | Delete performance metrics older than the specified retention period |
| `store_alert` | Store an alert |
| `get_alerts` | Retrieve alerts |
| `clear_old_alerts` | Delete alerts older than the specified retention period |

### Example Usage

```python
from boss.lighthouse.monitoring.metrics_storage import MetricsStorage

# Initialize the storage
storage = MetricsStorage(data_dir="/path/to/data")

# Store a system metric
storage.store_system_metric("cpu", {
    "usage_percent": 42.5,
    "timestamp": "2023-01-01T12:00:00"
})

# Retrieve system metrics
metrics = storage.get_system_metrics(
    metric_type="cpu",
    start_time=datetime(2023, 1, 1),
    end_time=datetime(2023, 1, 2)
)

# Clean up old data
storage.clear_old_system_metrics(retention_days=30)
``` 