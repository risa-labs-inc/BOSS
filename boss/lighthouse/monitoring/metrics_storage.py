"""MetricsStorage component for persisting monitoring metrics.

This module provides a storage mechanism for persisting system metrics,
health checks, performance data, and alerts using SQLite.
"""

import os
import sqlite3
import json
import logging
import contextlib
from typing import Any, Dict, List, Optional, Union, Tuple, cast, Iterator, ContextManager
from datetime import datetime, timedelta


class MetricsStorage:
    """Storage component for persisting monitoring metrics.
    
    This class provides methods for storing and retrieving metrics data
    from a SQLite database, with support for querying by time windows,
    filtering, and aggregation.
    
    Attributes:
        db_path: Path to the SQLite database file
        logger: Logger instance for the component
    """
    
    def __init__(self, data_dir: str, db_name: str = "monitoring.db"):
        """Initialize the MetricsStorage.
        
        Args:
            data_dir: Directory where the database file will be stored
            db_name: Name of the database file
        """
        self.logger = logging.getLogger("boss.lighthouse.monitoring.metrics_storage")
        
        # Ensure the data directory exists
        os.makedirs(data_dir, exist_ok=True)
        
        # Set the database path
        self.db_path = os.path.join(data_dir, db_name)
        self.logger.info(f"Using metrics database at: {self.db_path}")
        
        # Initialize the database schema
        self._initialize_db()
        
    def _initialize_db(self) -> None:
        """Initialize the database schema if it doesn't exist."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Create system metrics table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    data TEXT NOT NULL
                )
                ''')
                
                # Create component health table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS component_health (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    component_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    response_time_ms REAL,
                    timestamp TEXT NOT NULL,
                    details TEXT
                )
                ''')
                
                # Create performance metrics table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    component_id TEXT NOT NULL,
                    operation_name TEXT NOT NULL,
                    execution_time_ms REAL NOT NULL,
                    success INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    details TEXT
                )
                ''')
                
                # Create alerts table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id TEXT PRIMARY KEY,
                    component_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    acknowledged_at TEXT,
                    resolved_at TEXT,
                    details TEXT
                )
                ''')
                
                # Create indices for faster queries
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_system_metrics_type ON system_metrics (type)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_system_metrics_timestamp ON system_metrics (timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_component_health_component_id ON component_health (component_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_component_health_timestamp ON component_health (timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_performance_metrics_component_id ON performance_metrics (component_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_performance_metrics_operation ON performance_metrics (operation_name)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_performance_metrics_timestamp ON performance_metrics (timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_component_id ON alerts (component_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts (status)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts (severity)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts (created_at)')
                
                self.logger.info("Database schema initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}")
            raise
            
    @contextlib.contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """Get a database connection with automatic commit/rollback.
        
        This context manager ensures that the connection is properly closed
        and that transactions are committed or rolled back as appropriate.
        
        Yields:
            A SQLite connection object
            
        Raises:
            Exception: If there's an error with the database operation
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            yield conn
            # If we get here without an exception, commit the transaction
        except Exception as e:
            # If there was an exception, roll back any changes
            if conn:
                conn.rollback()
            raise
        finally:
            # Always close the connection when we're done
            if conn:
                conn.close()
    
    #
    # System Metrics Methods
    #
        
    def store_system_metric(self, metric_type: str, data: Dict[str, Any]) -> int:
        """Store a system metric in the database.
        
        Args:
            metric_type: Type of metric (e.g., 'cpu', 'memory', 'disk', 'network')
            data: Metric data as a dictionary
            
        Returns:
            The ID of the newly inserted record
        """
        try:
            # Add timestamp if not present
            if 'timestamp' not in data:
                data['timestamp'] = datetime.now().isoformat()
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO system_metrics (type, timestamp, data) VALUES (?, ?, ?)',
                    (metric_type, data.get('timestamp'), json.dumps(data))
                )
                conn.commit()
                return cast(int, cursor.lastrowid)
        except Exception as e:
            self.logger.error(f"Error storing system metric: {e}")
            raise
            
    def get_system_metrics(
        self, 
        metric_type: Optional[str] = None, 
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Retrieve system metrics from the database.
        
        Args:
            metric_type: Optional filter for metric type
            start_time: Optional start time filter
            end_time: Optional end time filter
            limit: Maximum number of records to return
            
        Returns:
            A list of metric records
        """
        try:
            query = 'SELECT type, timestamp, data FROM system_metrics'
            params: List[Any] = []
            conditions = []
            
            if metric_type:
                conditions.append('type = ?')
                params.append(metric_type)
                
            if start_time:
                conditions.append('timestamp >= ?')
                params.append(start_time.isoformat())
                
            if end_time:
                conditions.append('timestamp <= ?')
                params.append(end_time.isoformat())
                
            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)
                
            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                result = []
                for row in cursor.fetchall():
                    metric_type, timestamp, data_json = row
                    data = json.loads(data_json)
                    data['type'] = metric_type
                    data['timestamp'] = timestamp
                    result.append(data)
                    
                return result
        except Exception as e:
            self.logger.error(f"Error retrieving system metrics: {e}")
            raise
            
    def clear_old_system_metrics(self, retention_days: int) -> int:
        """Delete system metrics older than the specified retention period.
        
        Args:
            retention_days: Number of days to retain data
            
        Returns:
            Number of records deleted
        """
        try:
            cutoff_date = (datetime.now() - timedelta(days=retention_days)).isoformat()
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM system_metrics WHERE timestamp < ?', (cutoff_date,))
                deleted_count = cursor.rowcount
                conn.commit()
                
                self.logger.info(f"Cleared {deleted_count} old system metrics records")
                return deleted_count
        except Exception as e:
            self.logger.error(f"Error clearing old system metrics: {e}")
            raise
            
    #
    # Component Health Methods
    #
        
    def store_health_check(self, component_id: str, status: str, 
                          response_time_ms: Optional[float] = None,
                          details: Optional[Dict[str, Any]] = None) -> int:
        """Store a component health check result.
        
        Args:
            component_id: ID of the component
            status: Health status ('healthy' or 'unhealthy')
            response_time_ms: Optional response time in milliseconds
            details: Optional details about the health check
            
        Returns:
            The ID of the newly inserted record
        """
        try:
            timestamp = datetime.now().isoformat()
            details_json = json.dumps(details) if details else None
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''INSERT INTO component_health 
                       (component_id, status, response_time_ms, timestamp, details) 
                       VALUES (?, ?, ?, ?, ?)''',
                    (component_id, status, response_time_ms, timestamp, details_json)
                )
                conn.commit()
                return cast(int, cursor.lastrowid)
        except Exception as e:
            self.logger.error(f"Error storing health check: {e}")
            raise
            
    def get_health_history(
        self, 
        component_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        status: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Retrieve component health history.
        
        Args:
            component_id: Optional filter for component ID
            start_time: Optional start time filter
            end_time: Optional end time filter
            status: Optional filter for health status
            limit: Maximum number of records to return
            
        Returns:
            A list of health check records
        """
        try:
            query = '''SELECT component_id, status, response_time_ms, timestamp, details 
                    FROM component_health'''
            params: List[Any] = []
            conditions = []
            
            if component_id:
                conditions.append('component_id = ?')
                params.append(component_id)
                
            if start_time:
                conditions.append('timestamp >= ?')
                params.append(start_time.isoformat())
                
            if end_time:
                conditions.append('timestamp <= ?')
                params.append(end_time.isoformat())
                
            if status:
                conditions.append('status = ?')
                params.append(status)
                
            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)
                
            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                result = []
                for row in cursor.fetchall():
                    component_id, status, response_time_ms, timestamp, details_json = row
                    record = {
                        'component_id': component_id,
                        'status': status,
                        'timestamp': timestamp
                    }
                    
                    if response_time_ms is not None:
                        record['response_time_ms'] = response_time_ms
                        
                    if details_json:
                        record['details'] = json.loads(details_json)
                        
                    result.append(record)
                    
                return result
        except Exception as e:
            self.logger.error(f"Error retrieving health history: {e}")
            raise
            
    def clear_old_health_checks(self, retention_days: int) -> int:
        """Delete health checks older than the specified retention period.
        
        Args:
            retention_days: Number of days to retain data
            
        Returns:
            Number of records deleted
        """
        try:
            cutoff_date = (datetime.now() - timedelta(days=retention_days)).isoformat()
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM component_health WHERE timestamp < ?', (cutoff_date,))
                deleted_count = cursor.rowcount
                conn.commit()
                
                self.logger.info(f"Cleared {deleted_count} old health check records")
                return deleted_count
        except Exception as e:
            self.logger.error(f"Error clearing old health checks: {e}")
            raise
            
    #
    # Performance Metrics Methods
    #
        
    def store_performance_metric(
        self,
        component_id: str,
        operation_name: str,
        execution_time_ms: float,
        success: bool,
        details: Optional[Dict[str, Any]] = None
    ) -> int:
        """Store a performance metric.
        
        Args:
            component_id: ID of the component
            operation_name: Name of the operation
            execution_time_ms: Execution time in milliseconds
            success: Whether the operation was successful
            details: Optional details about the operation
            
        Returns:
            The ID of the newly inserted record
        """
        try:
            timestamp = datetime.now().isoformat()
            details_json = json.dumps(details) if details else None
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''INSERT INTO performance_metrics 
                       (component_id, operation_name, execution_time_ms, success, timestamp, details) 
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (component_id, operation_name, execution_time_ms, 1 if success else 0, timestamp, details_json)
                )
                conn.commit()
                return cast(int, cursor.lastrowid)
        except Exception as e:
            self.logger.error(f"Error storing performance metric: {e}")
            raise
            
    def get_performance_metrics(
        self,
        component_id: Optional[str] = None,
        operation_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        success: Optional[bool] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Retrieve performance metrics.
        
        Args:
            component_id: Optional filter for component ID
            operation_name: Optional filter for operation name
            start_time: Optional start time filter
            end_time: Optional end time filter
            success: Optional filter for success status
            limit: Maximum number of records to return
            
        Returns:
            A list of performance metric records
        """
        try:
            query = '''SELECT component_id, operation_name, execution_time_ms, success, timestamp, details 
                    FROM performance_metrics'''
            params: List[Any] = []
            conditions = []
            
            if component_id:
                conditions.append('component_id = ?')
                params.append(component_id)
                
            if operation_name:
                conditions.append('operation_name = ?')
                params.append(operation_name)
                
            if start_time:
                conditions.append('timestamp >= ?')
                params.append(start_time.isoformat())
                
            if end_time:
                conditions.append('timestamp <= ?')
                params.append(end_time.isoformat())
                
            if success is not None:
                conditions.append('success = ?')
                params.append(1 if success else 0)
                
            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)
                
            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                result = []
                for row in cursor.fetchall():
                    component_id, operation_name, execution_time_ms, success, timestamp, details_json = row
                    record = {
                        'component_id': component_id,
                        'operation_name': operation_name,
                        'execution_time_ms': execution_time_ms,
                        'success': bool(success),
                        'timestamp': timestamp
                    }
                    
                    if details_json:
                        record['details'] = json.loads(details_json)
                        
                    result.append(record)
                    
                return result
        except Exception as e:
            self.logger.error(f"Error retrieving performance metrics: {e}")
            raise
            
    def clear_old_performance_metrics(self, retention_days: int) -> int:
        """Delete performance metrics older than the specified retention period.
        
        Args:
            retention_days: Number of days to retain data
            
        Returns:
            Number of records deleted
        """
        try:
            cutoff_date = (datetime.now() - timedelta(days=retention_days)).isoformat()
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM performance_metrics WHERE timestamp < ?', (cutoff_date,))
                deleted_count = cursor.rowcount
                conn.commit()
                
                self.logger.info(f"Cleared {deleted_count} old performance metric records")
                return deleted_count
        except Exception as e:
            self.logger.error(f"Error clearing old performance metrics: {e}")
            raise
            
    #
    # Alert Methods
    #
        
    def store_alert(self, alert: Dict[str, Any]) -> str:
        """Store an alert.
        
        Args:
            alert: Alert data
            
        Returns:
            The ID of the alert
        """
        try:
            alert_id = alert.get('id')
            if not alert_id:
                raise ValueError("Alert must have an ID")
                
            # Extract required fields
            component_id = alert.get('component_id')
            alert_type = alert.get('alert_type')
            message = alert.get('message')
            severity = alert.get('severity')
            status = alert.get('status', 'active')
            created_at = alert.get('created_at', datetime.now().isoformat())
            updated_at = alert.get('updated_at', created_at)
            
            # Extract optional fields
            acknowledged_at = alert.get('acknowledged_at')
            resolved_at = alert.get('resolved_at')
            
            # Extract details (everything else)
            details = {k: v for k, v in alert.items() if k not in [
                'id', 'component_id', 'alert_type', 'message', 'severity', 'status',
                'created_at', 'updated_at', 'acknowledged_at', 'resolved_at'
            ]}
            details_json = json.dumps(details) if details else None
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if the alert already exists
                cursor.execute('SELECT id FROM alerts WHERE id = ?', (alert_id,))
                if cursor.fetchone():
                    # Update existing alert
                    cursor.execute(
                        '''UPDATE alerts SET 
                           component_id = ?, alert_type = ?, message = ?, severity = ?,
                           status = ?, updated_at = ?, acknowledged_at = ?, resolved_at = ?,
                           details = ?
                           WHERE id = ?''',
                        (component_id, alert_type, message, severity, status, updated_at,
                         acknowledged_at, resolved_at, details_json, alert_id)
                    )
                else:
                    # Insert new alert
                    cursor.execute(
                        '''INSERT INTO alerts 
                           (id, component_id, alert_type, message, severity, status,
                            created_at, updated_at, acknowledged_at, resolved_at, details)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (alert_id, component_id, alert_type, message, severity, status,
                         created_at, updated_at, acknowledged_at, resolved_at, details_json)
                    )
                
                conn.commit()
                return alert_id
        except Exception as e:
            self.logger.error(f"Error storing alert: {e}")
            raise
            
    def get_alerts(
        self,
        status: Optional[str] = None,
        component_id: Optional[str] = None,
        severity: Optional[str] = None,
        alert_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve alerts.
        
        Args:
            status: Optional filter for alert status
            component_id: Optional filter for component ID
            severity: Optional filter for severity
            alert_type: Optional filter for alert type
            start_time: Optional start time filter (for created_at)
            end_time: Optional end time filter (for created_at)
            limit: Maximum number of records to return
            
        Returns:
            A list of alert records
        """
        try:
            query = 'SELECT * FROM alerts'
            params: List[Any] = []
            conditions = []
            
            if status:
                conditions.append('status = ?')
                params.append(status)
                
            if component_id:
                conditions.append('component_id = ?')
                params.append(component_id)
                
            if severity:
                conditions.append('severity = ?')
                params.append(severity)
                
            if alert_type:
                conditions.append('alert_type = ?')
                params.append(alert_type)
                
            if start_time:
                conditions.append('created_at >= ?')
                params.append(start_time.isoformat())
                
            if end_time:
                conditions.append('created_at <= ?')
                params.append(end_time.isoformat())
                
            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)
                
            # Order by created_at for active alerts, resolved_at for resolved alerts
            if status == 'resolved':
                query += ' ORDER BY resolved_at DESC LIMIT ?'
            else:
                query += ' ORDER BY created_at DESC LIMIT ?'
                
            params.append(limit)
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                columns = [col[0] for col in cursor.description]
                result = []
                
                for row in cursor.fetchall():
                    record = dict(zip(columns, row))
                    
                    # Parse details JSON if present
                    if record.get('details'):
                        record['details'] = json.loads(record['details'])
                        
                    result.append(record)
                    
                return result
        except Exception as e:
            self.logger.error(f"Error retrieving alerts: {e}")
            raise
            
    def clear_old_alerts(self, retention_days: int) -> int:
        """Delete alerts older than the specified retention period.
        
        Args:
            retention_days: Number of days to retain data
            
        Returns:
            Number of records deleted
        """
        try:
            cutoff_date = (datetime.now() - timedelta(days=retention_days)).isoformat()
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Only delete resolved alerts
                cursor.execute(
                    'DELETE FROM alerts WHERE status = ? AND resolved_at < ?', 
                    ('resolved', cutoff_date)
                )
                deleted_count = cursor.rowcount
                conn.commit()
                
                self.logger.info(f"Cleared {deleted_count} old alert records")
                return deleted_count
        except Exception as e:
            self.logger.error(f"Error clearing old alerts: {e}")
            raise 