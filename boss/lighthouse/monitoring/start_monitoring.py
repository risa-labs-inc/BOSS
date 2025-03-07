#!/usr/bin/env python
"""Script to start the BOSS monitoring service with the API.

This script initializes and starts the monitoring service, which includes:
1. The system metrics collector
2. The component health checker
3. The performance metrics tracker
4. The dashboard generator
5. The monitoring API server

It can be run as a standalone service or imported and used programmatically.
"""

import os
import sys
import logging
import argparse
import asyncio
import signal
from typing import Any, Dict, Optional, cast

# Add the parent directory to the path so we can import the boss package
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from boss.lighthouse.monitoring.api import MonitoringAPI
from boss.lighthouse.monitoring.system_metrics_collector import SystemMetricsCollector
from boss.lighthouse.monitoring.component_health_checker import ComponentHealthChecker
from boss.lighthouse.monitoring.performance_metrics_tracker import PerformanceMetricsTracker
from boss.lighthouse.monitoring.dashboard_generator import DashboardGenerator
from boss.lighthouse.monitoring.metrics_storage import MetricsStorage
from boss.core.task_models import Task, TaskResult
from boss.core.task_resolver_metadata import TaskResolverMetadata


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("monitoring.log")
    ]
)

logger = logging.getLogger("boss.monitoring")


class MonitoringService:
    """Service that runs all monitoring components and the API server.
    
    This class initializes and manages all monitoring components and the API server.
    It provides methods to start and stop the service gracefully.
    
    Attributes:
        data_dir: Directory where monitoring data is stored
        api_host: Host to bind the API server to
        api_port: Port to bind the API server to
        metadata: Metadata for components
        api: The MonitoringAPI instance
        system_metrics_collector: The SystemMetricsCollector instance
        component_health_checker: The ComponentHealthChecker instance
        performance_metrics_tracker: The PerformanceMetricsTracker instance
        dashboard_generator: The DashboardGenerator instance
        running: Whether the service is running
    """
    
    def __init__(self,
                 data_dir: str,
                 api_host: str = "0.0.0.0",
                 api_port: int = 8080,
                 metadata: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the monitoring service.
        
        Args:
            data_dir: Directory for storing data
            api_host: Host to bind the API server to
            api_port: Port to bind the API server to
            metadata: Additional metadata to pass to the components
        """
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        # Use metadata or empty dict if None
        self.metadata = metadata or {}
        
        # API server configuration
        self.api_host = api_host
        self.api_port = api_port
        
        # Create TaskResolverMetadata from dict for compatibility
        resolver_metadata = TaskResolverMetadata(
            id="monitoring_service",
            name="Monitoring Service",
            description="Manages monitoring components and the API server",
            version="1.0.0",
            properties=self.metadata
        )
        
        # Initialize storage first since other components need it
        metrics_dir = os.path.join(data_dir, "metrics")
        os.makedirs(metrics_dir, exist_ok=True)
        self.metrics_storage = MetricsStorage(data_dir=metrics_dir)
        
        # Initialize components with proper metadata and storage
        self.system_metrics_collector = SystemMetricsCollector(
            metadata=resolver_metadata,
            metrics_storage=self.metrics_storage
        )
        
        self.component_health_checker = ComponentHealthChecker(
            metadata=resolver_metadata,
            metrics_storage=self.metrics_storage
        )
        
        self.performance_metrics_tracker = PerformanceMetricsTracker(
            metadata=resolver_metadata,
            metrics_storage=self.metrics_storage
        )
        
        # Initialize dashboard generator
        dashboard_dir = os.path.join(data_dir, "dashboards")
        os.makedirs(dashboard_dir, exist_ok=True)
        self.dashboard_generator = DashboardGenerator(
            data_dir=dashboard_dir,
            metrics_storage=self.metrics_storage
        )
        
        # Initialize API server
        self.api = MonitoringAPI(
            data_dir=self.data_dir,
            metadata=resolver_metadata,
            host=self.api_host,
            port=self.api_port
        )
        
        self.running = False
        self._setup_signal_handlers()
        logger.info("Monitoring service initialized")
        
    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, sig: int, frame: Any) -> None:
        """Handle signals for graceful shutdown.
        
        Args:
            sig: Signal number
            frame: Current stack frame
        """
        logger.info(f"Received signal {sig}, shutting down...")
        self.stop()
        
    async def schedule_metrics_collection(self) -> None:
        """Schedule periodic collection of system metrics."""
        while self.running:
            try:
                # Create a task for collecting all system metrics
                task = Task(
                    operation="collect_system_metrics",
                    input_data={"metrics_type": "all"}
                )
                
                # Collect metrics
                await self.system_metrics_collector.resolve(task)
                
                # Wait for the next collection interval
                await asyncio.sleep(60)  # Collect every minute
            except Exception as e:
                logger.error(f"Error collecting system metrics: {e}")
                await asyncio.sleep(10)  # Wait a bit before retrying
                
    async def schedule_health_checks(self) -> None:
        """Schedule periodic health checks for components."""
        while self.running:
            try:
                # Create a task for checking all components
                task = Task(
                    operation="check_all_components",
                    input_data={}
                )
                
                # Check component health
                await self.component_health_checker.resolve(task)
                
                # Wait for the next check interval
                await asyncio.sleep(300)  # Check every 5 minutes
            except Exception as e:
                logger.error(f"Error checking component health: {e}")
                await asyncio.sleep(30)  # Wait a bit before retrying
                
    async def schedule_dashboard_generation(self) -> None:
        """Schedule periodic generation of dashboards."""
        while self.running:
            try:
                # Generate system dashboard
                system_task = Task(
                    operation="generate_dashboard",
                    input_data={
                        "dashboard_type": "system",
                        "time_window": "1h"
                    }
                )
                await self.dashboard_generator.resolve(system_task)
                
                # Generate health dashboard
                health_task = Task(
                    operation="generate_dashboard",
                    input_data={
                        "dashboard_type": "health",
                        "time_window": "24h"
                    }
                )
                await self.dashboard_generator.resolve(health_task)
                
                # Generate performance dashboard
                performance_task = Task(
                    operation="generate_dashboard",
                    input_data={
                        "dashboard_type": "performance",
                        "time_window": "7d"
                    }
                )
                await self.dashboard_generator.resolve(performance_task)
                
                # Wait for the next generation interval
                await asyncio.sleep(3600)  # Generate dashboards every hour
            except Exception as e:
                logger.error(f"Error generating dashboards: {e}")
                await asyncio.sleep(300)  # Wait a bit before retrying
                
    async def schedule_maintenance(self) -> None:
        """Schedule periodic maintenance tasks."""
        while self.running:
            try:
                # Clear old health checks
                health_task = Task(
                    operation="clear_old_health_checks",
                    input_data={}
                )
                await self.component_health_checker.resolve(health_task)
                
                # Clear old performance metrics
                performance_task = Task(
                    operation="clear_old_metrics",
                    input_data={}
                )
                await self.performance_metrics_tracker.resolve(performance_task)
                
                # Wait for the next maintenance interval
                await asyncio.sleep(86400)  # Run maintenance once a day
            except Exception as e:
                logger.error(f"Error running maintenance tasks: {e}")
                await asyncio.sleep(3600)  # Wait a bit before retrying
                
    async def run(self) -> None:
        """Run the monitoring service."""
        self.running = True
        logger.info("Starting BOSS monitoring service...")
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self.schedule_metrics_collection()),
            asyncio.create_task(self.schedule_health_checks()),
            asyncio.create_task(self.schedule_dashboard_generation()),
            asyncio.create_task(self.schedule_maintenance())
        ]
        
        try:
            # Start the API server
            logger.info(f"Starting API server on {self.api_host}:{self.api_port}")
            server_task = asyncio.create_task(self.api.start_async())
            
            # Wait for all tasks to complete
            await asyncio.gather(server_task, *tasks)
        except asyncio.CancelledError:
            logger.info("Service tasks cancelled, shutting down...")
        finally:
            # Cancel all tasks
            for task in tasks:
                task.cancel()
            
            # Wait for tasks to be cancelled
            await asyncio.gather(*tasks, return_exceptions=True)
            self.running = False
            logger.info("BOSS monitoring service stopped")
            
    def start(self) -> None:
        """Start the monitoring service."""
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, shutting down...")
        
    def stop(self) -> None:
        """Stop the monitoring service."""
        self.running = False


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Start the BOSS monitoring service")
    
    parser.add_argument(
        "--data-dir",
        type=str,
        default=os.path.join(os.getcwd(), "monitoring_data"),
        help="Directory where monitoring data is stored"
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind the API server to"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind the API server to"
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    logger.info(f"Initializing monitoring service with data directory: {args.data_dir}")
    
    # Create and start the monitoring service
    service = MonitoringService(
        data_dir=args.data_dir,
        api_host=args.host,
        api_port=args.port
    )
    
    service.start() 