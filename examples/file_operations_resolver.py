"""
Example demonstrating a FileOperationsResolver.

This example shows how to implement a TaskResolver that handles file operations
like reading, writing, and processing files.
"""
import asyncio
import logging
import os
import json
import csv
from collections.abc import Collection
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional, Union, BinaryIO
from pathlib import Path

from boss.core.task_models import Task, TaskResult, TaskError
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_status import TaskStatus


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class FileOperationsResolver(TaskResolver):
    """
    A TaskResolver that handles file operations.
    
    This resolver can read, write, and process files in various formats,
    with support for operations like copying, moving, and deleting files.
    """
    
    def __init__(
        self, 
        metadata: TaskResolverMetadata,
        base_dir: str,
        allowed_extensions: Optional[List[str]] = None,
        max_file_size_mb: float = 10.0,
        allow_writes: bool = False,
        allow_deletes: bool = False
    ):
        """
        Initialize a new FileOperationsResolver.
        
        Args:
            metadata: Metadata about this resolver.
            base_dir: Base directory for file operations.
            allowed_extensions: List of allowed file extensions (None means all).
            max_file_size_mb: Maximum file size in megabytes.
            allow_writes: Whether to allow write operations.
            allow_deletes: Whether to allow delete operations.
        """
        super().__init__(metadata)
        self.base_dir = os.path.abspath(base_dir)
        self.allowed_extensions = allowed_extensions
        self.max_file_size_mb = max_file_size_mb
        self.allow_writes = allow_writes
        self.allow_deletes = allow_deletes
        
        # Create the base directory if it doesn't exist
        os.makedirs(self.base_dir, exist_ok=True)
        
        self.logger.info(f"Initialized FileOperationsResolver with base directory: {self.base_dir}")
        if allowed_extensions:
            self.logger.info(f"Allowed extensions: {', '.join(allowed_extensions)}")
    
    def _validate_path(self, file_path: str) -> Path:
        """
        Validate that a file path is within the base directory and has an allowed extension.
        
        Args:
            file_path: Relative path to validate.
            
        Returns:
            Absolute path to the file.
            
        Raises:
            RuntimeError: If the path is invalid.
        """
        # Convert to absolute path and normalize
        abs_path = os.path.abspath(os.path.join(self.base_dir, file_path))
        
        # Check that the path is within the base directory
        if not abs_path.startswith(self.base_dir):
            raise RuntimeError(f"Path {file_path} is outside the base directory")
        
        # Check the file extension
        if self.allowed_extensions:
            ext = os.path.splitext(abs_path)[1].lower()
            if ext and ext[1:] not in self.allowed_extensions:
                raise RuntimeError(f"File extension {ext} is not allowed")
        
        return Path(abs_path)
    
    def _check_file_size(self, file_path: Path) -> None:
        """
        Check that a file doesn't exceed the maximum file size.
        
        Args:
            file_path: Path to the file.
            
        Raises:
            RuntimeError: If the file is too large.
        """
        if file_path.exists():
            size_mb = file_path.stat().st_size / (1024 * 1024)
            if size_mb > self.max_file_size_mb:
                raise RuntimeError(
                    f"File size {size_mb:.2f} MB exceeds the maximum of {self.max_file_size_mb} MB"
                )
    
    async def _read_text_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Read a text file.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            Dictionary with the file contents.
        """
        try:
            self._check_file_size(file_path)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            return {
                "content": content,
                "size_bytes": file_path.stat().st_size,
                "format": "text"
            }
        except UnicodeDecodeError:
            self.logger.warning(f"File {file_path} is not a text file")
            return await self._read_binary_file(file_path)
    
    async def _read_binary_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Read a binary file.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            Dictionary with information about the file.
        """
        self._check_file_size(file_path)
        
        return {
            "content": "(binary data)",
            "size_bytes": file_path.stat().st_size,
            "format": "binary"
        }
    
    async def _read_json_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Read a JSON file.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            Dictionary with the parsed JSON content.
        """
        self._check_file_size(file_path)
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            return {
                "content": data,
                "size_bytes": file_path.stat().st_size,
                "format": "json"
            }
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON file: {e}")
    
    async def _read_csv_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Read a CSV file.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            Dictionary with the parsed CSV content.
        """
        self._check_file_size(file_path)
        
        try:
            rows = []
            with open(file_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(dict(row))
            
            return {
                "content": rows,
                "headers": reader.fieldnames if rows else [],
                "row_count": len(rows),
                "size_bytes": file_path.stat().st_size,
                "format": "csv"
            }
        except csv.Error as e:
            raise RuntimeError(f"CSV parsing error: {e}")
    
    async def _write_text_file(self, file_path: Path, content: str) -> Dict[str, Any]:
        """
        Write content to a text file.
        
        Args:
            file_path: Path to the file.
            content: Content to write.
            
        Returns:
            Dictionary with information about the operation.
        """
        if not self.allow_writes:
            raise RuntimeError("Write operations are not allowed")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return {
            "size_bytes": file_path.stat().st_size,
            "path": str(file_path),
            "operation": "write_text"
        }
    
    async def _write_json_file(self, file_path: Path, content: Any) -> Dict[str, Any]:
        """
        Write content to a JSON file.
        
        Args:
            file_path: Path to the file.
            content: Content to write (must be serializable to JSON).
            
        Returns:
            Dictionary with information about the operation.
        """
        if not self.allow_writes:
            raise RuntimeError("Write operations are not allowed")
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2)
        
        return {
            "size_bytes": file_path.stat().st_size,
            "path": str(file_path),
            "operation": "write_json"
        }
    
    async def _write_csv_file(
        self, file_path: Path, rows: List[Dict[str, Any]], headers: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Write rows to a CSV file.
        
        Args:
            file_path: Path to the file.
            rows: List of dictionaries to write as CSV rows.
            headers: Optional list of column headers (uses dictionary keys if not provided).
            
        Returns:
            Dictionary with information about the operation.
        """
        if not self.allow_writes:
            raise RuntimeError("Write operations are not allowed")
        
        # Get headers from the first row if not provided
        if headers is None and rows:
            headers = list(rows[0].keys())
        
        # Ensure headers is not None for DictWriter
        fieldnames: Collection[str] = headers if headers is not None else []
        
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        return {
            "size_bytes": file_path.stat().st_size,
            "path": str(file_path),
            "row_count": len(rows),
            "operation": "write_csv"
        }
    
    async def _list_directory(self, dir_path: Path) -> Dict[str, Any]:
        """
        List the contents of a directory.
        
        Args:
            dir_path: Path to the directory.
            
        Returns:
            Dictionary with directory contents.
        """
        if not dir_path.is_dir():
            raise RuntimeError(f"{dir_path} is not a directory")
        
        files = []
        directories = []
        
        for item in dir_path.iterdir():
            # Base info for all items
            info: Dict[str, Any] = {
                "name": item.name,
                "path": str(item.relative_to(self.base_dir)),
                "last_modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat()
            }
            
            if item.is_file():
                # Add file-specific info
                info["size_bytes"] = item.stat().st_size
                files.append(info)
            elif item.is_dir():
                directories.append(info)
        
        # Calculate relative path string, or empty string for base directory
        try:
            rel_path = str(dir_path.relative_to(self.base_dir))
            # If we're at the base directory itself, use empty string
            if rel_path == '.':
                rel_path = ""
        except ValueError:
            # Handle case where dir_path is not relative to base_dir
            rel_path = ""
        
        return {
            "path": rel_path,
            "files": files,
            "directories": directories,
            "operation": "list_directory"
        }
    
    async def _delete_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Delete a file.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            Dictionary with information about the operation.
        """
        if not self.allow_deletes:
            raise RuntimeError("Delete operations are not allowed")
        
        if not file_path.exists():
            raise RuntimeError(f"File {file_path} does not exist")
        
        if file_path.is_dir():
            raise RuntimeError(f"{file_path} is a directory, not a file")
        
        # Store file info before deletion
        file_info = {
            "path": str(file_path.relative_to(self.base_dir)),
            "size_bytes": file_path.stat().st_size,
            "operation": "delete_file"
        }
        
        # Delete the file
        file_path.unlink()
        
        return file_info
    
    async def _copy_file(self, source_path: Path, dest_path: Path) -> Dict[str, Any]:
        """
        Copy a file.
        
        Args:
            source_path: Path to the source file.
            dest_path: Path to the destination file.
            
        Returns:
            Dictionary with information about the operation.
        """
        if not self.allow_writes:
            raise RuntimeError("Copy operations are not allowed (requires write permission)")
        
        if not source_path.exists():
            raise RuntimeError(f"Source file {source_path} does not exist")
        
        if source_path.is_dir():
            raise RuntimeError(f"{source_path} is a directory, not a file")
        
        # Create the destination directory if it doesn't exist
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        
        # Copy the file
        shutil.copy2(source_path, dest_path)
        
        return {
            "source": str(source_path.relative_to(self.base_dir)),
            "destination": str(dest_path.relative_to(self.base_dir)),
            "size_bytes": dest_path.stat().st_size,
            "operation": "copy_file"
        }
    
    async def _move_file(self, source_path: Path, dest_path: Path) -> Dict[str, Any]:
        """
        Move a file.
        
        Args:
            source_path: Path to the source file.
            dest_path: Path to the destination file.
            
        Returns:
            Dictionary with information about the operation.
        """
        if not self.allow_writes or not self.allow_deletes:
            raise RuntimeError("Move operations are not allowed (requires write and delete permissions)")
        
        if not source_path.exists():
            raise RuntimeError(f"Source file {source_path} does not exist")
        
        if source_path.is_dir():
            raise RuntimeError(f"{source_path} is a directory, not a file")
        
        # Create the destination directory if it doesn't exist
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        
        # Move the file
        shutil.move(source_path, dest_path)
        
        return {
            "source": str(source_path.relative_to(self.base_dir)),
            "destination": str(dest_path.relative_to(self.base_dir)),
            "size_bytes": dest_path.stat().st_size,
            "operation": "move_file"
        }
    
    async def health_check(self) -> bool:
        """
        Check if the file system is accessible and the base directory exists.
        
        Returns:
            True if the file system is healthy, False otherwise.
        """
        try:
            # Check that the base directory exists and is writable
            if not os.path.exists(self.base_dir):
                os.makedirs(self.base_dir, exist_ok=True)
            
            # Check if we can write to a temporary file
            temp_path = os.path.join(self.base_dir, ".health_check_temp")
            with open(temp_path, "w") as f:
                f.write("health check")
            
            # Clean up
            os.remove(temp_path)
            
            self.logger.info(f"Health check passed: {self.base_dir} is accessible and writable")
            return True
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
    
    async def resolve(self, task: Task) -> Dict[str, Any]:
        """
        Resolve a file operation task.
        
        The task input_data should contain:
            - operation: The type of file operation (read, write, list, etc.)
            - path: The path to the file or directory
            - Other parameters specific to the operation
        
        Args:
            task: The task to resolve.
                
        Returns:
            A dictionary containing the results of the file operation.
        """
        # Extract task parameters
        operation = task.input_data.get("operation", "").lower()
        path = task.input_data.get("path", "")
        
        # Validate parameters
        if not operation:
            task.add_error("validation_error", "Missing 'operation' in task input")
            return {}
            
        if not path and operation not in ["list_base_dir"]:
            task.add_error("validation_error", "Missing 'path' in task input")
            return {}
        
        self.logger.info(f"Executing {operation} operation on path: {path}")
        
        try:
            # Handle the list_base_dir operation specially
            if operation == "list_base_dir":
                return await self._list_directory(Path(self.base_dir))
            
            # Validate the file path for other operations
            file_path = self._validate_path(path)
            
            # Execute the appropriate operation
            if operation == "read_file" or operation == "read_text":
                return await self._read_text_file(file_path)
            
            elif operation == "read_json":
                return await self._read_json_file(file_path)
            
            elif operation == "read_csv":
                return await self._read_csv_file(file_path)
            
            elif operation == "read_binary":
                return await self._read_binary_file(file_path)
            
            elif operation == "write_file" or operation == "write_text":
                content = task.input_data.get("content", "")
                return await self._write_text_file(file_path, content)
            
            elif operation == "write_json":
                content = task.input_data.get("content", {})
                return await self._write_json_file(file_path, content)
            
            elif operation == "write_csv":
                rows = task.input_data.get("rows", [])
                headers = task.input_data.get("headers")
                return await self._write_csv_file(file_path, rows, headers)
            
            elif operation == "list_directory":
                return await self._list_directory(file_path)
            
            elif operation == "delete_file":
                return await self._delete_file(file_path)
            
            elif operation == "copy_file":
                dest_path = task.input_data.get("destination", "")
                if not dest_path:
                    task.add_error("validation_error", "Missing 'destination' in task input")
                    return {}
                
                dest_path = self._validate_path(dest_path)
                return await self._copy_file(file_path, dest_path)
            
            elif operation == "move_file":
                dest_path = task.input_data.get("destination", "")
                if not dest_path:
                    task.add_error("validation_error", "Missing 'destination' in task input")
                    return {}
                
                dest_path = self._validate_path(dest_path)
                return await self._move_file(file_path, dest_path)
            
            else:
                task.add_error("unsupported_operation", f"Unsupported operation: {operation}")
                return {}
                
        except Exception as e:
            task.add_error("execution_error", str(e))
            return {}


async def main() -> None:
    """Run the example."""
    # Define the base directory for file operations
    base_dir = "file_ops_example"
    
    # Create metadata for our resolver
    metadata = TaskResolverMetadata(
        name="FileOperationsResolver",
        version="1.0.0",
        description="Resolver for file operations"
    )
    
    # Create the resolver, allowing writes and deletes for this example
    resolver = FileOperationsResolver(
        metadata=metadata,
        base_dir=base_dir,
        allowed_extensions=["txt", "json", "csv"],
        max_file_size_mb=5.0,
        allow_writes=True,
        allow_deletes=True
    )
    
    # Run a health check to make sure everything is configured correctly
    print("\n--- Running Health Check ---")
    is_healthy = await resolver.health_check()
    print(f"Health check result: {is_healthy}")
    
    if not is_healthy:
        print("Health check failed")
        return
    
    # Create a list of example tasks
    tasks = []
    
    # 1. First, write some sample files
    tasks.append(
        Task(
            name="write_text_file",
            description="Write a text file",
            input_data={
                "operation": "write_text",
                "path": "sample.txt",
                "content": "This is a sample text file.\nIt has multiple lines.\nHello, world!"
            }
        )
    )
    
    tasks.append(
        Task(
            name="write_json_file",
            description="Write a JSON file",
            input_data={
                "operation": "write_json",
                "path": "data.json",
                "content": {
                    "name": "Example Data",
                    "created_at": datetime.now().isoformat(),
                    "values": [1, 2, 3, 4, 5],
                    "metadata": {
                        "source": "FileOperationsResolver Example",
                        "version": "1.0.0"
                    }
                }
            }
        )
    )
    
    tasks.append(
        Task(
            name="write_csv_file",
            description="Write a CSV file",
            input_data={
                "operation": "write_csv",
                "path": "users.csv",
                "headers": ["id", "name", "email", "active"],
                "rows": [
                    {"id": 1, "name": "Alice Smith", "email": "alice@example.com", "active": True},
                    {"id": 2, "name": "Bob Johnson", "email": "bob@example.com", "active": True},
                    {"id": 3, "name": "Charlie Brown", "email": "charlie@example.com", "active": False},
                    {"id": 4, "name": "David Wilson", "email": "david@example.com", "active": True}
                ]
            }
        )
    )
    
    # 2. Then, read the files
    tasks.append(
        Task(
            name="read_text_file",
            description="Read a text file",
            input_data={
                "operation": "read_text",
                "path": "sample.txt"
            }
        )
    )
    
    tasks.append(
        Task(
            name="read_json_file",
            description="Read a JSON file",
            input_data={
                "operation": "read_json",
                "path": "data.json"
            }
        )
    )
    
    tasks.append(
        Task(
            name="read_csv_file",
            description="Read a CSV file",
            input_data={
                "operation": "read_csv",
                "path": "users.csv"
            }
        )
    )
    
    # 3. List directory contents
    tasks.append(
        Task(
            name="list_directory",
            description="List all files in the base directory",
            input_data={
                "operation": "list_base_dir"
            }
        )
    )
    
    # 4. Copy, move, and delete files
    tasks.append(
        Task(
            name="copy_file",
            description="Copy a file",
            input_data={
                "operation": "copy_file",
                "path": "sample.txt",
                "destination": "sample_copy.txt"
            }
        )
    )
    
    tasks.append(
        Task(
            name="move_file",
            description="Move a file",
            input_data={
                "operation": "move_file",
                "path": "sample_copy.txt",
                "destination": "moved_sample.txt"
            }
        )
    )
    
    tasks.append(
        Task(
            name="delete_file",
            description="Delete a file",
            input_data={
                "operation": "delete_file",
                "path": "moved_sample.txt"
            }
        )
    )
    
    # 5. Try an operation that should fail (invalid extension)
    tasks.append(
        Task(
            name="write_invalid_file",
            description="Write a file with an invalid extension",
            input_data={
                "operation": "write_text",
                "path": "invalid.exe",
                "content": "This should fail because .exe is not an allowed extension."
            }
        )
    )
    
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
            # Special handling for binary data or large text content
            output_data = result.output_data.copy()
            if "content" in output_data:
                if output_data.get("format") == "binary":
                    output_data["content"] = "(binary data)"
                elif isinstance(output_data["content"], str) and len(output_data["content"]) > 100:
                    output_data["content"] = output_data["content"][:100] + "... (truncated)"
            
            # For readability, format the output data as JSON
            formatted_output = json.dumps(output_data, indent=2)
            print(f"\nOutput:\n{formatted_output}")
        
        if task.errors:
            print("\nErrors:")
            for error in task.errors:
                print(f"- {error}")


if __name__ == "__main__":
    asyncio.run(main()) 