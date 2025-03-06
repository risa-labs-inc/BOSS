"""
Example demonstrating a DatabaseTaskResolver.

This example shows how to implement a TaskResolver that interacts with a database.
It uses SQLite for simplicity, but the concepts would apply to any database.
"""
import asyncio
import logging
import os
import sqlite3
from typing import Dict, Any, List, Optional, Tuple, Union
import json

from boss.core.task_models import Task, TaskResult, TaskError
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_status import TaskStatus


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class DatabaseTaskResolver(TaskResolver):
    """
    A TaskResolver that interacts with a database.
    
    This resolver can execute SQL queries against a SQLite database,
    with support for different operation types like SELECT, INSERT, UPDATE, etc.
    """
    
    def __init__(
        self, 
        metadata: TaskResolverMetadata,
        db_path: str,
        max_results: int = 100,
        allow_write_operations: bool = False
    ):
        """
        Initialize a new DatabaseTaskResolver.
        
        Args:
            metadata: Metadata about this resolver.
            db_path: Path to the SQLite database file.
            max_results: Maximum number of results to return from SELECT queries.
            allow_write_operations: Whether to allow operations that modify the database.
        """
        super().__init__(metadata)
        self.db_path = db_path
        self.max_results = max_results
        self.allow_write_operations = allow_write_operations
        
        # Check if the database file exists
        self._initialize_db()
    
    def _initialize_db(self) -> None:
        """Initialize the database if it doesn't exist."""
        if not os.path.exists(self.db_path):
            self.logger.info(f"Creating new database at {self.db_path}")
            
            # Create the database and some example tables
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create a users table
                cursor.execute('''
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    age INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # Create a posts table
                cursor.execute('''
                CREATE TABLE posts (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    title TEXT NOT NULL,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
                ''')
                
                # Insert some example data
                cursor.execute(
                    "INSERT INTO users (name, email, age) VALUES (?, ?, ?)",
                    ("Alice Smith", "alice@example.com", 32)
                )
                cursor.execute(
                    "INSERT INTO users (name, email, age) VALUES (?, ?, ?)",
                    ("Bob Johnson", "bob@example.com", 45)
                )
                cursor.execute(
                    "INSERT INTO users (name, email, age) VALUES (?, ?, ?)",
                    ("Charlie Brown", "charlie@example.com", 28)
                )
                
                cursor.execute(
                    "INSERT INTO posts (user_id, title, content) VALUES (?, ?, ?)",
                    (1, "First Post", "This is Alice's first post.")
                )
                cursor.execute(
                    "INSERT INTO posts (user_id, title, content) VALUES (?, ?, ?)",
                    (1, "Second Post", "Alice writes about databases.")
                )
                cursor.execute(
                    "INSERT INTO posts (user_id, title, content) VALUES (?, ?, ?)",
                    (2, "Hello World", "Bob's introduction to the blog.")
                )
                
                conn.commit()
    
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
            # Raise a runtime error instead of TaskError
            raise RuntimeError(f"Database connection error: {e}")
    
    def _execute_select_query(
        self, 
        query: str, 
        params: Tuple = ()
    ) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query against the database.
        
        Args:
            query: The SQL query to execute.
            params: Parameters to pass to the query.
            
        Returns:
            List of rows as dictionaries.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(query, params)
                rows = cursor.fetchmany(self.max_results)
                # Convert rows to dictionaries
                return [dict(row) for row in rows]
            except sqlite3.Error as e:
                self.logger.error(f"Error executing SELECT query: {e}")
                # Raise a runtime error instead of TaskError
                raise RuntimeError(f"Database query error: {e}")
    
    def _execute_write_query(
        self, 
        query: str, 
        params: Tuple = ()
    ) -> Dict[str, Any]:
        """
        Execute a query that modifies the database (INSERT, UPDATE, DELETE).
        
        Args:
            query: The SQL query to execute.
            params: Parameters to pass to the query.
            
        Returns:
            Dictionary with result information.
        """
        if not self.allow_write_operations:
            # Raise a runtime error instead of TaskError
            raise RuntimeError("Write operations are not allowed by this resolver")
        
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
                # Raise a runtime error instead of TaskError
                raise RuntimeError(f"Database write error: {e}")
    
    async def health_check(self) -> bool:
        """
        Check if the database is accessible and the required tables exist.
        
        Returns:
            True if the database is healthy, False otherwise.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Check if the users table exists and has at least one row
                cursor.execute("SELECT COUNT(*) as count FROM users")
                user_count = cursor.fetchone()["count"]
                
                # Log health check results but return bool as required by interface
                self.logger.info(f"Database connected successfully. Found {user_count} users.")
                return True
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return False
    
    # Helper method to get detailed health check results
    async def get_health_details(self) -> Dict[str, Any]:
        """
        Get detailed health check results.
        
        Returns:
            Dictionary with health check results.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Check if the users table exists and has at least one row
                cursor.execute("SELECT COUNT(*) as count FROM users")
                user_count = cursor.fetchone()["count"]
                
                return {
                    "healthy": True,
                    "message": f"Database connected successfully. Found {user_count} users.",
                    "db_path": self.db_path
                }
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {
                "healthy": False,
                "message": f"Database health check failed: {e}",
                "db_path": self.db_path
            }
    
    async def resolve(self, task: Task) -> Dict[str, Any]:
        """
        Resolve a database task by executing the specified query.
        
        The task input_data should contain:
            - operation: The type of operation (select, insert, update, delete, schema)
            - query: The SQL query to execute
            - params: Optional parameters for the query
        
        Args:
            task: The task to resolve.
                
        Returns:
            A dictionary containing the results of the database operation.
        """
        # Extract task parameters
        operation = task.input_data.get("operation", "").lower()
        query = task.input_data.get("query", "")
        params = task.input_data.get("params", [])
        
        # Validate parameters
        if not operation:
            task.add_error("validation_error", "Missing 'operation' in task input")
            return {}
            
        if not query:
            task.add_error("validation_error", "Missing 'query' in task input")
            return {}
        
        self.logger.info(f"Executing {operation} operation: {query}")
        
        # Convert params to tuple if it's a list
        if isinstance(params, list):
            params = tuple(params)
        
        try:
            # Execute the appropriate operation
            if operation == "select":
                results = self._execute_select_query(query, params)
                return {
                    "operation": "select",
                    "count": len(results),
                    "results": results
                }
            
            elif operation == "schema":
                # Get database schema information
                schema_info = {}
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Get list of tables
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row["name"] for row in cursor.fetchall()]
                    
                    # For each table, get its columns
                    for table in tables:
                        cursor.execute(f"PRAGMA table_info({table})")
                        columns = [
                            {
                                "name": row["name"],
                                "type": row["type"],
                                "notnull": bool(row["notnull"]),
                                "pk": bool(row["pk"])
                            }
                            for row in cursor.fetchall()
                        ]
                        schema_info[table] = columns
                
                return {
                    "operation": "schema",
                    "tables": tables,
                    "schema": schema_info
                }
            
            elif operation in ["insert", "update", "delete"] and self.allow_write_operations:
                result = self._execute_write_query(query, params)
                return result
            
            else:
                task.add_error("unsupported_operation", f"Unsupported or disallowed operation: {operation}")
                return {}
                
        except Exception as e:
            task.add_error("execution_error", str(e))
            return {}


async def main() -> None:
    """Run the example."""
    # Define the path for our example database
    db_path = "example.db"
    
    # Create metadata for our resolver
    metadata = TaskResolverMetadata(
        name="DatabaseQueryResolver",
        version="1.0.0",
        description="Resolver for database operations"
    )
    
    # Create the resolver, allowing write operations for this example
    resolver = DatabaseTaskResolver(
        metadata=metadata,
        db_path=db_path,
        max_results=10,
        allow_write_operations=True
    )
    
    # Run a health check to make sure everything is configured correctly
    print("\n--- Running Health Check ---")
    is_healthy = await resolver.health_check()
    health_details = await resolver.get_health_details()
    print(f"Health check result: {is_healthy}")
    print(f"Health details: {health_details}")
    
    if not is_healthy:
        print(f"Health check failed: {health_details.get('message', 'Unknown error')}")
        return
    
    # Create a list of example tasks
    tasks = [
        Task(
            name="get_all_users",
            description="Get a list of all users",
            input_data={
                "operation": "select",
                "query": "SELECT * FROM users"
            }
        ),
        
        Task(
            name="count_users_by_age",
            description="Count users grouped by age",
            input_data={
                "operation": "select",
                "query": "SELECT age, COUNT(*) as count FROM users GROUP BY age"
            }
        ),
        
        Task(
            name="get_user_posts",
            description="Get posts for a specific user",
            input_data={
                "operation": "select",
                "query": """
                SELECT posts.*, users.name as author 
                FROM posts 
                JOIN users ON posts.user_id = users.id 
                WHERE users.name = ?
                """,
                "params": ["Alice Smith"]
            }
        ),
        
        Task(
            name="add_new_user",
            description="Add a new user to the database",
            input_data={
                "operation": "insert",
                "query": "INSERT INTO users (name, email, age) VALUES (?, ?, ?)",
                "params": ["David Wilson", "david@example.com", 37]
            }
        ),
        
        Task(
            name="update_user",
            description="Update a user's information",
            input_data={
                "operation": "update",
                "query": "UPDATE users SET age = ? WHERE email = ?",
                "params": [33, "alice@example.com"]
            }
        ),
        
        Task(
            name="get_database_schema",
            description="Get the database schema",
            input_data={
                "operation": "schema",
                "query": "SCHEMA"
            }
        )
    ]
    
    # Process each task
    for task in tasks:
        print(f"\n\n--- Processing Task: {task.name} ---")
        print(f"Description: {task.description}")
        print(f"Input: {task.input_data}")
        
        # Process the task
        result = await resolver(task)
        
        # Display the results
        print(f"\nTask status: {result.status}")
        print(f"Execution time: {result.execution_time_ms} ms")
        
        if result.output_data:
            # For readability, format the output data as JSON
            formatted_output = json.dumps(result.output_data, indent=2)
            print(f"\nOutput:\n{formatted_output}")
        
        if task.errors:
            print("\nErrors:")
            for error in task.errors:
                print(f"- {error}")


if __name__ == "__main__":
    asyncio.run(main()) 