"""Monitoring API module for exposing monitoring data through REST endpoints.

This module provides REST API endpoints for accessing system metrics, health data,
performance metrics, and alert information. It also allows triggering certain
monitoring operations via API calls.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Union, cast
from datetime import datetime, timedelta
import asyncio
import json

try:
    from fastapi import FastAPI, HTTPException, Query, Path, Depends, BackgroundTasks
    from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
except ImportError:
    # Type stubs for mypy to avoid import errors
    class FastAPI: pass
    class HTTPException: pass
    class Query: pass
    class Path: pass
    class Depends: pass
    class BackgroundTasks: pass
    class JSONResponse: pass
    class HTMLResponse: pass
    class FileResponse: pass
    class StaticFiles: pass
    class CORSMiddleware: pass
    uvicorn = None

from boss.lighthouse.monitoring.metrics_storage import MetricsStorage
from boss.lighthouse.monitoring.system_metrics_collector import SystemMetricsCollector
from boss.lighthouse.monitoring.component_health_checker import ComponentHealthChecker
from boss.lighthouse.monitoring.performance_metrics_tracker import PerformanceMetricsTracker
from boss.lighthouse.monitoring.dashboard_generator import DashboardGenerator
from boss.core.task_models import Task, TaskResult


class MonitoringAPI:
    """API server for the monitoring system.
    
    This class sets up a FastAPI server that exposes monitoring data and operations
    via REST endpoints.
    
    Attributes:
        app: The FastAPI application
        metrics_storage: Storage for metrics data
        system_metrics_collector: Component for collecting system metrics
        component_health_checker: Component for checking component health
        performance_metrics_tracker: Component for tracking performance metrics
        dashboard_generator: Component for generating dashboards
        data_dir: Directory for storing data
        static_dir: Directory for static files
    """
    
    def __init__(self, 
                 data_dir: str,
                 metadata: Any,
                 host: str = "0.0.0.0",
                 port: int = 8080) -> None:
        """Initialize the API server.
        
        Args:
            data_dir: Directory for storing data
            metadata: Metadata for components
            host: Host to bind the server to
            port: Port to bind the server to
        """
        self.app = FastAPI(
            title="BOSS Monitoring API",
            description="API for accessing monitoring data from the BOSS system",
            version="1.0.0"
        )
        
        self.logger = logging.getLogger("boss.lighthouse.monitoring.api")
        self.data_dir = data_dir
        self.host = host
        self.port = port
        
        # Set up static directory for dashboard files
        self.static_dir = os.path.join(data_dir, "dashboards")
        os.makedirs(self.static_dir, exist_ok=True)
        
        # Initialize components
        self.metrics_storage = MetricsStorage(data_dir)
        self.system_metrics_collector = SystemMetricsCollector(metadata)
        self.component_health_checker = ComponentHealthChecker(metadata)
        self.performance_metrics_tracker = PerformanceMetricsTracker(metadata)
        self.dashboard_generator = DashboardGenerator(metadata)
        
        # Configure CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Mount static files
        self.app.mount("/dashboards", StaticFiles(directory=self.static_dir), name="dashboards")
        
        # Configure routes
        self._configure_routes()
        
    def _configure_routes(self) -> None:
        """Configure API routes."""
        
        # Health check endpoint
        @self.app.get("/health", tags=["Health"])
        async def health_check() -> Dict[str, str]:
            """Check if the monitoring API is healthy."""
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}
        
        # System metrics endpoints
        @self.app.get("/metrics/system", tags=["System Metrics"])
        async def get_system_metrics(
            metric_type: Optional[str] = Query(None, description="Type of metric (cpu, memory, disk, network)"),
            start_time: Optional[str] = Query(None, description="Start time (ISO format)"),
            end_time: Optional[str] = Query(None, description="End time (ISO format)"),
            limit: int = Query(100, description="Maximum number of metrics to return")
        ) -> List[Dict[str, Any]]:
            """Get system metrics."""
            try:
                # Parse time parameters
                start_dt = datetime.fromisoformat(start_time) if start_time else datetime.now() - timedelta(hours=24)
                end_dt = datetime.fromisoformat(end_time) if end_time else datetime.now()
                
                # Get metrics from storage
                metrics = self.metrics_storage.get_system_metrics(
                    metric_type=metric_type,
                    start_time=start_dt,
                    end_time=end_dt,
                    limit=limit
                )
                
                return metrics
            except Exception as e:
                self.logger.error(f"Error getting system metrics: {e}")
                raise HTTPException(status_code=500, detail=f"Error getting system metrics: {str(e)}")
                
        @self.app.post("/metrics/system/collect", tags=["System Metrics"])
        async def collect_system_metrics(
            background_tasks: BackgroundTasks,
            metrics_type: str = Query("all", description="Type of metrics to collect (all, cpu, memory, disk, network)")
        ) -> Dict[str, Any]:
            """Trigger collection of system metrics."""
            try:
                # Create a task for collecting metrics
                task = Task(
                    task_id="collect_system_metrics",
                    operation="collect_system_metrics",
                    input_data={"metrics_type": metrics_type}
                )
                
                # Run in background
                background_tasks.add_task(self._run_task, self.system_metrics_collector, task)
                
                return {
                    "message": f"System metrics collection for {metrics_type} started",
                    "task_id": task.task_id
                }
            except Exception as e:
                self.logger.error(f"Error triggering system metrics collection: {e}")
                raise HTTPException(status_code=500, detail=f"Error triggering metrics collection: {str(e)}")
                
        # Health check endpoints
        @self.app.get("/health/components", tags=["Component Health"])
        async def get_component_health() -> List[Dict[str, Any]]:
            """Get health status of all components."""
            try:
                # Create a task for checking all components
                task = Task(
                    task_id="check_all_components",
                    operation="check_all_components",
                    input_data={}
                )
                
                # Execute the task
                result = await self.component_health_checker.resolve(task)
                
                if result.status != "success":
                    raise Exception(result.message)
                    
                return result.output_data.get("health_results", [])
            except Exception as e:
                self.logger.error(f"Error getting component health: {e}")
                raise HTTPException(status_code=500, detail=f"Error getting component health: {str(e)}")
                
        @self.app.get("/health/components/{component_id}", tags=["Component Health"])
        async def get_component_health_history(
            component_id: str = Path(..., description="ID of the component"),
            start_time: Optional[str] = Query(None, description="Start time (ISO format)"),
            end_time: Optional[str] = Query(None, description="End time (ISO format)"),
            limit: int = Query(100, description="Maximum number of health checks to return")
        ) -> Dict[str, Any]:
            """Get health history for a specific component."""
            try:
                # Parse time parameters
                start_dt = datetime.fromisoformat(start_time) if start_time else datetime.now() - timedelta(days=7)
                end_dt = datetime.fromisoformat(end_time) if end_time else datetime.now()
                
                # Create a task for getting health history
                task = Task(
                    task_id=f"get_health_history_{component_id}",
                    operation="get_health_history",
                    input_data={
                        "component_id": component_id,
                        "start_time": start_dt.isoformat(),
                        "end_time": end_dt.isoformat(),
                        "limit": limit
                    }
                )
                
                # Execute the task
                result = await self.component_health_checker.resolve(task)
                
                if result.status != "success":
                    raise Exception(result.message)
                    
                return result.output_data
            except Exception as e:
                self.logger.error(f"Error getting component health history: {e}")
                raise HTTPException(status_code=500, detail=f"Error getting health history: {str(e)}")
                
        @self.app.post("/health/components/{component_id}/check", tags=["Component Health"])
        async def check_component_health(
            component_id: str = Path(..., description="ID of the component"),
            timeout_ms: Optional[int] = Query(5000, description="Timeout in milliseconds")
        ) -> Dict[str, Any]:
            """Check health of a specific component."""
            try:
                # Create a task for checking component health
                task = Task(
                    task_id=f"check_component_health_{component_id}",
                    operation="check_component_health",
                    input_data={
                        "component_id": component_id,
                        "timeout_ms": timeout_ms
                    }
                )
                
                # Execute the task
                result = await self.component_health_checker.resolve(task)
                
                if result.status != "success":
                    raise Exception(result.message)
                    
                return result.output_data
            except Exception as e:
                self.logger.error(f"Error checking component health: {e}")
                raise HTTPException(status_code=500, detail=f"Error checking component health: {str(e)}")
                
        # Performance metrics endpoints
        @self.app.get("/metrics/performance", tags=["Performance Metrics"])
        async def get_performance_metrics(
            component_id: Optional[str] = Query(None, description="ID of the component"),
            operation_name: Optional[str] = Query(None, description="Name of the operation"),
            start_time: Optional[str] = Query(None, description="Start time (ISO format)"),
            end_time: Optional[str] = Query(None, description="End time (ISO format)"),
            limit: int = Query(100, description="Maximum number of metrics to return")
        ) -> List[Dict[str, Any]]:
            """Get performance metrics."""
            try:
                # Parse time parameters
                start_dt = datetime.fromisoformat(start_time) if start_time else datetime.now() - timedelta(days=7)
                end_dt = datetime.fromisoformat(end_time) if end_time else datetime.now()
                
                # Get metrics from storage
                metrics = self.metrics_storage.get_performance_metrics(
                    component_id=component_id,
                    operation_name=operation_name,
                    start_time=start_dt,
                    end_time=end_dt,
                    limit=limit
                )
                
                return metrics
            except Exception as e:
                self.logger.error(f"Error getting performance metrics: {e}")
                raise HTTPException(status_code=500, detail=f"Error getting performance metrics: {str(e)}")
                
        @self.app.post("/metrics/performance/record", tags=["Performance Metrics"])
        async def record_performance_metric(
            background_tasks: BackgroundTasks,
            component_id: str = Query(..., description="ID of the component"),
            operation_name: str = Query(..., description="Name of the operation"),
            execution_time_ms: float = Query(..., description="Execution time in milliseconds"),
            success: bool = Query(True, description="Whether the operation was successful"),
            metadata: Optional[str] = Query(None, description="Additional metadata as JSON string")
        ) -> Dict[str, Any]:
            """Record a performance metric."""
            try:
                parsed_metadata = json.loads(metadata) if metadata else {}
                
                # Create a task for recording a performance metric
                task = Task(
                    task_id=f"record_performance_metric_{component_id}_{operation_name}",
                    operation="record_performance_metric",
                    input_data={
                        "component_id": component_id,
                        "operation_name": operation_name,
                        "execution_time_ms": execution_time_ms,
                        "success": success,
                        "metadata": parsed_metadata
                    }
                )
                
                # Run in background
                background_tasks.add_task(self._run_task, self.performance_metrics_tracker, task)
                
                return {
                    "message": "Performance metric recording started",
                    "task_id": task.task_id
                }
            except Exception as e:
                self.logger.error(f"Error recording performance metric: {e}")
                raise HTTPException(status_code=500, detail=f"Error recording performance metric: {str(e)}")
                
        # Dashboard endpoints
        @self.app.get("/dashboards", tags=["Dashboards"])
        async def list_dashboards() -> List[Dict[str, Any]]:
            """List available dashboards."""
            try:
                dashboards = []
                
                # List dashboard JSON files
                for filename in os.listdir(self.static_dir):
                    if filename.endswith(".json"):
                        file_path = os.path.join(self.static_dir, filename)
                        
                        try:
                            with open(file_path, "r") as f:
                                dashboard_config = json.load(f)
                                dashboards.append({
                                    "id": dashboard_config.get("id"),
                                    "type": dashboard_config.get("type"),
                                    "title": dashboard_config.get("title"),
                                    "created_at": dashboard_config.get("created_at"),
                                    "updated_at": dashboard_config.get("updated_at"),
                                    "url": f"/dashboards/{dashboard_config.get('id')}.html"
                                })
                        except Exception as e:
                            self.logger.error(f"Error reading dashboard config {filename}: {e}")
                
                return dashboards
            except Exception as e:
                self.logger.error(f"Error listing dashboards: {e}")
                raise HTTPException(status_code=500, detail=f"Error listing dashboards: {str(e)}")
                
        @self.app.post("/dashboards/generate", tags=["Dashboards"])
        async def generate_dashboard(
            dashboard_type: str = Query(..., description="Type of dashboard to generate"),
            title: Optional[str] = Query(None, description="Dashboard title"),
            time_window: str = Query("24h", description="Time window for metrics (e.g., 1h, 24h, 7d)")
        ) -> Dict[str, Any]:
            """Generate a dashboard."""
            try:
                # Create a task for generating a dashboard
                task = Task(
                    task_id=f"generate_dashboard_{dashboard_type}",
                    operation="generate_dashboard",
                    input_data={
                        "dashboard_type": dashboard_type,
                        "title": title,
                        "time_window": time_window
                    }
                )
                
                # Execute the task
                result = await self.dashboard_generator.resolve(task)
                
                if result.status != "success":
                    raise Exception(result.message)
                    
                return result.output_data
            except Exception as e:
                self.logger.error(f"Error generating dashboard: {e}")
                raise HTTPException(status_code=500, detail=f"Error generating dashboard: {str(e)}")
                
        @self.app.get("/dashboards/{dashboard_id}", tags=["Dashboards"])
        async def get_dashboard(dashboard_id: str = Path(..., description="ID of the dashboard")) -> HTMLResponse:
            """Get a dashboard."""
            try:
                # Check if dashboard HTML exists
                dashboard_path = os.path.join(self.static_dir, f"{dashboard_id}.html")
                
                if not os.path.exists(dashboard_path):
                    raise HTTPException(status_code=404, detail=f"Dashboard with ID {dashboard_id} not found")
                    
                # Return the dashboard HTML
                with open(dashboard_path, "r") as f:
                    content = f.read()
                    
                return HTMLResponse(content=content)
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error getting dashboard: {e}")
                raise HTTPException(status_code=500, detail=f"Error getting dashboard: {str(e)}")
                
    async def _run_task(self, component: Any, task: Task) -> None:
        """Run a task asynchronously.
        
        Args:
            component: The component to run the task on
            task: The task to run
        """
        try:
            # Create a task with correct parameters
            # Note: Changed task_id to id and removed operation parameter
            actual_task = Task(
                id=str(task.id) if hasattr(task, 'id') else None,
                input_data=task.input_data,
                metadata=task.metadata
            )
            result = await asyncio.to_thread(component, actual_task)
            logging.info(f"Task {task.id if hasattr(task, 'id') else 'unknown'} completed: {result.status}")
        except Exception as e:
            logging.error(f"Error running task: {e}")
            raise
            
    def start(self) -> None:
        """Start the API server."""
        self.logger.info(f"Starting monitoring API server on {self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port)
        
    async def start_async(self) -> None:
        """Start the API server asynchronously."""
        config = uvicorn.Config(self.app, host=self.host, port=self.port)
        server = uvicorn.Server(config)
        await server.serve()


def create_api_server(data_dir: str, metadata: Any, host: str = "0.0.0.0", port: int = 8080) -> MonitoringAPI:
    """Create and return a MonitoringAPI instance.
    
    Args:
        data_dir: Directory for storing data
        metadata: Metadata for components
        host: Host to bind the server to
        port: Port to bind the server to
        
    Returns:
        A configured MonitoringAPI instance
    """
    return MonitoringAPI(data_dir=data_dir, metadata=metadata, host=host, port=port) 