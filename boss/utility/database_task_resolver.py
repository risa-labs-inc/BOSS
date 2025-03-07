"""
DatabaseTaskResolver implementation for interacting with databases.

This module provides a TaskResolver that can execute SQL queries against
databases using SQLite, with support for different operation types
like SELECT, INSERT, UPDATE, DELETE, and schema operations.
"""
import logging
import os
import json
from typing import Dict, Any, List, Optional, Tuple, Union, cast
from enum import Enum
import asyncio
import sqlite3
import traceback

from ..core.task_models import Task, TaskResult, TaskError
from ..core.task_resolver import TaskResolver, TaskResolverMetadata
from ..core.task_status import TaskStatus


class DatabaseOperation(str, Enum):
    """Enum for supported database operations."""
    SELECT = "SELECT"
    INSERT = "INSERT" 
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    SCHEMA = "SCHEMA"
    EXECUTE = "EXECUTE"


class DatabaseTaskResolver(TaskResolver):
    """
    A TaskResolver that interacts with a database.
    
    This resolver can execute SQL queries against a SQLite database,
    with support for different operation types like SELECT, INSERT, UPDATE, etc.
    """
    
    def __init__(
        self, 
        connection_string: str,
        max_results: int = 100,
        read_only: bool = True,
        metadata: Optional[TaskResolverMetadata] = None
    ):
        """
        Initialize a new DatabaseTaskResolver.
        
        Args:
            connection_string: Connection string to the database (supports SQLite for now).
            max_results: Maximum number of results to return from SELECT queries.
            read_only: Whether to allow operations that modify the database.
            metadata: Metadata about this resolver.
        """
        if metadata is None:
            metadata = TaskResolverMetadata(
                name="DatabaseTaskResolver",
                version="1.0.0",
                description="Resolver for database operations",
                max_retries=3,
                evolution_threshold=3,
            )
            
        super().__init__(metadata)
        self.connection_string = connection_string
        self.max_results = max_results
        self.read_only = read_only
        
        # Extract the database path for SQLite connections
        if connection_string.startswith("sqlite:///"):
            self.db_path = connection_string[10:]
        else:
            self.db_path = connection_string
        
        # Initialize logger
        self.logger = logging.getLogger(__name__)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a connection to the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            # Enable foreign key constraints
            conn.execute("PRAGMA foreign_keys = ON")
            # Make SQLite return rows as dictionaries
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            self.logger.error(f"Error connecting to database: {e}")
            # We can't raise TaskError here because we don't have a task
            # Instead, raise a RuntimeError that will be caught by the resolve method
            raise RuntimeError(f"Database connection error: {e}")
    
    def _execute_select_query(
        self, 
        query: str, 
        params: Tuple = (),
        task: Optional[Task] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query against the database.
        
        Args:
            query: The SQL query to execute.
            params: Parameters to pass to the query.
            task: The task that requested this query (for error reporting).
            
        Returns:
            List of rows as dictionaries.
            
        Raises:
            RuntimeError: If there's an error executing the query.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(query, params)
                rows = cursor.fetchmany(self.max_results)
                # Convert rows to dictionaries
                result_rows = [dict(row) for row in rows]
                return result_rows
            except sqlite3.Error as e:
                self.logger.error(f"Error executing SELECT query: {e}")
                # We can't raise TaskError here because we might not have a task
                # Instead, raise a RuntimeError that will be caught by the resolve method
                raise RuntimeError(f"Database query error: {e}")
    
    def _execute_write_query(
        self, 
        query: str, 
        params: Tuple = (),
        task: Optional[Task] = None
    ) -> Dict[str, Any]:
        """
        Execute a query that modifies the database (INSERT, UPDATE, DELETE).
        
        Args:
            query: The SQL query to execute.
            params: Parameters to pass to the query.
            task: The task that requested this query (for error reporting).
            
        Returns:
            Dictionary with result information.
            
        Raises:
            RuntimeError: If there's an error executing the query or if write operations are not allowed.
        """
        if self.read_only:
            raise RuntimeError("Write operations are not allowed in read-only mode")
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(query, params)
                conn.commit()
                return {
                    "operation": "write",
                    "rowcount": cursor.rowcount,
                    "lastrowid": cursor.lastrowid
                }
            except sqlite3.Error as e:
                conn.rollback()
                self.logger.error(f"Error executing write query: {e}")
                # We can't raise TaskError here because we might not have a task
                # Instead, raise a RuntimeError that will be caught by the resolve method
                raise RuntimeError(f"Database write error: {e}")
    
    async def health_check(self) -> bool:
        """
        Check if the database is accessible.
        
        Returns:
            True if the database is healthy, False otherwise.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Simple query to check connection
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                return result is not None
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return False
    
    async def get_health_details(self) -> Dict[str, Any]:
        """
        Get detailed health check results.
        
        Returns:
            Dictionary with health check results.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Simple query to check connection
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                
                # Get database statistics
                cursor.execute("PRAGMA database_list")
                db_info = cursor.fetchall()
                
                cursor.execute("PRAGMA table_list")
                tables = cursor.fetchall()
                
                return {
                    "healthy": True,
                    "connection": self.connection_string,
                    "read_only": self.read_only,
                    "database_info": [dict(db) for db in db_info],
                    "tables": [dict(table) for table in tables],
                    "max_results": self.max_results
                }
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {
                "healthy": False,
                "message": f"Database health check failed: {e}",
                "connection": self.connection_string
            }
    
    async def resolve(self, task: Task) -> TaskResult:
        """
        Resolve a database task by executing the specified operation.
        
        The task input_data should be a dictionary containing:
            - operation: The type of operation (SELECT, INSERT, UPDATE, DELETE, SCHEMA, EXECUTE)
            - query: SQL query or statement to execute (required for EXECUTE, optional for other operations)
            - table: Table name (for operations other than EXECUTE)
            - columns: Columns to SELECT or INSERT (for SELECT and INSERT operations)
            - where: WHERE clause conditions (for SELECT, UPDATE, DELETE operations)
            - data: Data to INSERT or UPDATE (for INSERT and UPDATE operations)
            - schema: Schema definition (for SCHEMA operations)
            - params: Query parameters (for EXECUTE operation)
        
        Returns:
            TaskResult with the query results or operation status.
        """
        try:
            input_data = task.input_data
            if not isinstance(input_data, dict):
                raise TaskError(
                    task=task,
                    error_type="INVALID_INPUT",
                    message="Input data must be a dictionary",
                    details={"input_data": str(input_data)}
                )
            
            # Extract the operation type
            operation = input_data.get("operation", "").upper()
            if not operation:
                raise TaskError(
                    task=task,
                    error_type="MISSING_OPERATION",
                    message="Operation type is required",
                    details={"input_data": input_data}
                )
            
            # Try to parse as DatabaseOperation enum
            try:
                operation = DatabaseOperation(operation)
            except ValueError:
                raise TaskError(
                    task=task,
                    error_type="INVALID_OPERATION",
                    message=f"Invalid operation type: {operation}",
                    details={"input_data": input_data, "valid_operations": [op.value for op in DatabaseOperation]}
                )
            
            # Handle different operation types
            if operation == DatabaseOperation.EXECUTE:
                # Direct query execution
                query = input_data.get("query")
                if not query:
                    raise TaskError(
                        task=task,
                        error_type="MISSING_QUERY",
                        message="Query is required for EXECUTE operation",
                        details={"input_data": input_data}
                    )
                
                params = input_data.get("params", ())
                
                # Determine if this is a SELECT query or a write operation
                query_upper = query.strip().upper()
                if query_upper.startswith("SELECT"):
                    rows_result = self._execute_select_query(query, params, task)
                    return TaskResult.success(
                        task=task,
                        output_data={"rows": rows_result, "count": len(rows_result)}
                    )
                else:
                    if self.read_only:
                        raise TaskError(
                            task=task,
                            error_type="DB_READONLY_ERROR",
                            message="Write operations are not allowed in read-only mode",
                            details={"input_data": input_data}
                        )
                    result = self._execute_write_query(query, params, task)
                    return TaskResult.success(
                        task=task,
                        output_data=result
                    )
            
            # For other operations, build the query based on input
            elif operation == DatabaseOperation.SELECT:
                table = input_data.get("table")
                if not table:
                    raise TaskError(
                        task=task,
                        error_type="MISSING_TABLE",
                        message="Table name is required for SELECT operation",
                        details={"input_data": input_data}
                    )
                
                # Build SELECT query
                columns = input_data.get("columns", ["*"])
                if isinstance(columns, list):
                    columns_str = ", ".join(columns)
                else:
                    columns_str = str(columns)
                
                query = f"SELECT {columns_str} FROM {table}"
                
                # Add WHERE clause if specified
                where = input_data.get("where")
                params = []
                if where:
                    where_clause, where_params = self._build_where_clause(where, task)
                    query += f" WHERE {where_clause}"
                    params.extend(where_params)
                
                # Add LIMIT clause
                limit = input_data.get("limit", self.max_results)
                query += f" LIMIT {limit}"
                
                # Execute the query
                rows_result = self._execute_select_query(query, tuple(params), task)
                return TaskResult.success(
                    task=task,
                    output_data={"rows": rows_result, "count": len(rows_result)}
                )
            
            elif operation == DatabaseOperation.INSERT:
                if self.read_only:
                    raise TaskError(
                        task=task,
                        error_type="DB_READONLY_ERROR",
                        message="INSERT operations are not allowed in read-only mode",
                        details={"input_data": input_data}
                    )
                
                table = input_data.get("table")
                if not table:
                    raise TaskError(
                        task=task,
                        error_type="MISSING_TABLE",
                        message="Table name is required for INSERT operation",
                        details={"input_data": input_data}
                    )
                
                data = input_data.get("data")
                if not data:
                    raise TaskError(
                        task=task,
                        error_type="MISSING_DATA",
                        message="Data is required for INSERT operation",
                        details={"input_data": input_data}
                    )
                
                # Handle single row or multiple rows
                if isinstance(data, dict):
                    # Single row insert
                    columns = data.keys()
                    placeholders = ", ".join(["?" for _ in columns])
                    columns_str = ", ".join(columns)
                    query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"
                    params = tuple(data.values())
                    
                    result = self._execute_write_query(query, params, task)
                    return TaskResult.success(
                        task=task,
                        output_data=result
                    )
                elif isinstance(data, list) and all(isinstance(item, dict) for item in data):
                    # Multiple row insert - not implemented yet
                    raise TaskError(
                        task=task,
                        error_type="NOT_IMPLEMENTED",
                        message="Multiple row INSERT not yet implemented",
                        details={"input_data": input_data}
                    )
                else:
                    raise TaskError(
                        task=task,
                        error_type="INVALID_DATA_FORMAT",
                        message="Invalid data format for INSERT operation",
                        details={"input_data": input_data, "data_type": type(data).__name__}
                    )
            
            # Other operations (UPDATE, DELETE, SCHEMA) would be implemented similarly
            else:
                raise TaskError(
                    task=task,
                    error_type="NOT_IMPLEMENTED",
                    message=f"Operation {operation} not yet implemented",
                    details={"input_data": input_data}
                )
                
        except TaskError as e:
            # Re-raise TaskError
            task.update_status(TaskStatus.ERROR)
            task.error = e.to_dict()
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message=str(e)
            )
        except Exception as e:
            # Convert other exceptions to TaskError
            self.logger.error(f"Unexpected error in DatabaseTaskResolver: {e}", exc_info=True)
            error = TaskError(
                task=task,
                error_type="UNEXPECTED_ERROR",
                message=f"Unexpected error: {str(e)}",
                details={"exception": str(e), "traceback": traceback.format_exc()}
            )
            task.update_status(TaskStatus.ERROR)
            task.error = error.to_dict()
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message=str(e)
            )
    
    def _build_where_clause(self, where_conditions: Dict[str, Any], task: Optional[Task] = None) -> Tuple[str, List[Any]]:
        """
        Build a WHERE clause from a dictionary of conditions.
        
        Args:
            where_conditions: Dictionary of column names to values or conditions.
            task: The task that requested this query (for error reporting).
            
        Returns:
            Tuple of (where_clause, params) where where_clause is the SQL WHERE clause
            and params is the list of parameter values.
        """
        clauses = []
        params = []
        
        for column, condition in where_conditions.items():
            if isinstance(condition, dict):
                # Complex condition like {"gt": 5}
                for op, value in condition.items():
                    if op == "eq" or op == "equals":
                        clauses.append(f"{column} = ?")
                        params.append(value)
                    elif op == "gt":
                        clauses.append(f"{column} > ?")
                        params.append(value)
                    elif op == "lt":
                        clauses.append(f"{column} < ?")
                        params.append(value)
                    elif op == "gte":
                        clauses.append(f"{column} >= ?")
                        params.append(value)
                    elif op == "lte":
                        clauses.append(f"{column} <= ?")
                        params.append(value)
                    elif op == "ne" or op == "not":
                        clauses.append(f"{column} != ?")
                        params.append(value)
                    elif op == "like":
                        clauses.append(f"{column} LIKE ?")
                        params.append(value)
                    elif op == "in":
                        if isinstance(value, (list, tuple)):
                            placeholders = ", ".join(["?" for _ in value])
                            clauses.append(f"{column} IN ({placeholders})")
                            params.extend(value)
                        else:
                            clauses.append(f"{column} = ?")
                            params.append(value)
                    else:
                        if task:
                            raise TaskError(
                                task=task,
                                error_type="INVALID_OPERATOR",
                                message=f"Unknown operator: {op}",
                                details={"column": column, "operator": op, "value": value}
                            )
                        else:
                            raise RuntimeError(f"Unknown operator: {op}")
            else:
                # Simple equality condition
                clauses.append(f"{column} = ?")
                params.append(condition)
        
        # Combine with AND
        where_clause = " AND ".join(clauses)
        return where_clause, params 