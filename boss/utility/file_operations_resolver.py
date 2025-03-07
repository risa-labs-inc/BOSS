"""
FileOperationsResolver implementation for handling file operations.

This module provides a TaskResolver that can handle file operations such as
reading, writing, and processing files in various formats.
"""
import os
import json
import csv
import yaml  # type: ignore
import logging
import shutil
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, TextIO, BinaryIO, cast
from enum import Enum

from ..core.task_models import Task, TaskResult, TaskError
from ..core.task_resolver import TaskResolver, TaskResolverMetadata
from ..core.task_status import TaskStatus


class FileOperation(str, Enum):
    """Enum for supported file operations."""
    READ = "READ"
    WRITE = "WRITE"
    APPEND = "APPEND"
    DELETE = "DELETE"
    COPY = "COPY"
    MOVE = "MOVE"
    LIST = "LIST"
    EXISTS = "EXISTS"
    MAKEDIRS = "MAKEDIRS"


class FileFormat(str, Enum):
    """Enum for supported file formats."""
    TEXT = "text"
    BINARY = "binary"
    JSON = "json"
    CSV = "csv"
    YAML = "yaml"


class FileOperationsResolver(TaskResolver):
    """
    A TaskResolver that handles file operations.
    
    This resolver can read, write, and process files in various formats,
    with support for operations like copying, moving, and deleting files.
    """
    
    def __init__(
        self, 
        base_directory: str,
        allowed_extensions: Optional[List[str]] = None,
        max_file_size_mb: float = 10.0,
        allow_writes: bool = True,
        allow_deletes: bool = False,
        metadata: Optional[TaskResolverMetadata] = None
    ):
        """
        Initialize a new FileOperationsResolver.
        
        Args:
            base_directory: Base directory for file operations.
            allowed_extensions: List of allowed file extensions (None means all).
            max_file_size_mb: Maximum file size in megabytes.
            allow_writes: Whether to allow write operations.
            allow_deletes: Whether to allow delete operations.
            metadata: Metadata about this resolver.
        """
        if metadata is None:
            metadata = TaskResolverMetadata(
                name="FileOperationsResolver",
                version="1.0.0",
                description="Resolver for file operations",
                max_retries=3,
                evolution_threshold=3
            )
            
        super().__init__(metadata)
        self.base_directory = os.path.abspath(base_directory)
        self.allowed_extensions = allowed_extensions
        self.max_file_size_mb = max_file_size_mb
        self.allow_writes = allow_writes
        self.allow_deletes = allow_deletes
        
        # Create the base directory if it doesn't exist
        os.makedirs(self.base_directory, exist_ok=True)
        
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initialized FileOperationsResolver with base directory: {self.base_directory}")
        if allowed_extensions:
            self.logger.info(f"Allowed extensions: {', '.join(allowed_extensions)}")
    
    def _validate_path(self, file_path: str, task: Optional[Task] = None) -> Path:
        """
        Validate that a file path is within the base directory and has an allowed extension.
        
        Args:
            file_path: Relative path to validate.
            task: The task associated with this operation.
            
        Returns:
            Absolute path to the file.
            
        Raises:
            RuntimeError: If the path is invalid.
        """
        # Convert to absolute path and normalize
        abs_path = os.path.abspath(os.path.join(self.base_directory, file_path))
        
        # Check that the path is within the base directory
        if not abs_path.startswith(self.base_directory):
            raise RuntimeError(f"Path {file_path} is outside the base directory")
        
        # Check the file extension
        if self.allowed_extensions:
            ext = os.path.splitext(abs_path)[1].lower()
            if ext and ext[1:] not in self.allowed_extensions:
                raise RuntimeError(f"File extension {ext} is not allowed")
        
        return Path(abs_path)
    
    def _check_file_size(self, file_path: Path, task: Optional[Task] = None) -> None:
        """
        Check if a file's size is within the allowed limit.
        
        Args:
            file_path: Path to the file to check.
            task: The task associated with this operation.
            
        Raises:
            RuntimeError: If the file is too large.
        """
        if not file_path.exists():
            return
        
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > self.max_file_size_mb:
            raise RuntimeError(
                f"File {file_path.name} is too large ({size_mb:.2f} MB > {self.max_file_size_mb} MB)"
            )
    
    def _read_file(self, file_path: Path, file_format: FileFormat, task: Optional[Task] = None) -> Any:
        """
        Read a file and parse its contents according to the specified format.
        
        Args:
            file_path: Path to the file to read.
            file_format: Format of the file (text, json, csv, etc.).
            task: The task associated with this operation.
            
        Returns:
            The contents of the file in the appropriate format.
            
        Raises:
            RuntimeError: If there's an error reading the file.
        """
        self._check_file_size(file_path, task)
        
        try:
            if file_format == FileFormat.BINARY:
                with open(file_path, 'rb') as f:
                    return f.read()
            
            elif file_format == FileFormat.TEXT:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
                
            elif file_format == FileFormat.JSON:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
                
            elif file_format == FileFormat.CSV:
                rows = []
                with open(file_path, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        rows.append(dict(row))
                return rows
                
            elif file_format == FileFormat.YAML:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
                
            else:
                raise RuntimeError(f"Unsupported file format: {file_format}")
                
        except (IOError, json.JSONDecodeError, yaml.YAMLError, csv.Error) as e:
            raise RuntimeError(f"Error reading file {file_path}: {str(e)}")
    
    def _write_file(self, file_path: Path, content: Any, file_format: FileFormat, 
                   append: bool = False, task: Optional[Task] = None) -> Dict[str, Any]:
        """
        Write content to a file in the specified format.
        
        Args:
            file_path: Path to the file to write.
            content: Content to write to the file.
            file_format: Format of the file (text, json, csv, etc.).
            append: Whether to append to the file instead of overwriting.
            task: The task associated with this operation.
            
        Returns:
            Dictionary with information about the write operation.
            
        Raises:
            RuntimeError: If there's an error writing the file.
        """
        if not self.allow_writes:
            raise RuntimeError("Write operations are not allowed")
        
        # Create parent directories if they don't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        mode = 'a' if append else 'w'
        binary_mode = 'ab' if append else 'wb'
        
        try:
            if file_format == FileFormat.BINARY:
                with open(file_path, binary_mode) as f:
                    if isinstance(content, (str, bytes)):
                        if isinstance(content, str):
                            content = content.encode('utf-8')
                        f.write(content)
                    else:
                        raise RuntimeError("Binary content must be string or bytes")
            
            elif file_format == FileFormat.TEXT:
                with open(file_path, mode, encoding='utf-8') as f:
                    if isinstance(content, str):
                        f.write(content)
                    else:
                        f.write(str(content))
                
            elif file_format == FileFormat.JSON:
                with open(file_path, mode, encoding='utf-8') as f:
                    json.dump(content, f, indent=2)
                
            elif file_format == FileFormat.CSV:
                if not isinstance(content, list) or not all(isinstance(item, dict) for item in content):
                    raise RuntimeError("CSV content must be a list of dictionaries")
                
                if not content:
                    raise RuntimeError("CSV content cannot be empty")
                
                fieldnames = content[0].keys()
                
                with open(file_path, mode, encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    if not append or file_path.stat().st_size == 0:
                        writer.writeheader()
                    writer.writerows(content)
                
            elif file_format == FileFormat.YAML:
                with open(file_path, mode, encoding='utf-8') as f:
                    yaml.safe_dump(content, f, default_flow_style=False)
                
            else:
                raise RuntimeError(f"Unsupported file format: {file_format}")
                
            return {
                "path": str(file_path),
                "size": file_path.stat().st_size,
                "operation": "append" if append else "write",
                "format": file_format.value
            }
                
        except (IOError, TypeError, json.JSONDecodeError, yaml.YAMLError, csv.Error) as e:
            raise RuntimeError(f"Error writing to file {file_path}: {str(e)}")
    
    def _delete_file(self, file_path: Path, task: Optional[Task] = None) -> Dict[str, Any]:
        """
        Delete a file.
        
        Args:
            file_path: Path to the file to delete.
            task: The task associated with this operation.
            
        Returns:
            Dictionary with information about the delete operation.
            
        Raises:
            RuntimeError: If there's an error deleting the file.
        """
        if not self.allow_deletes:
            raise RuntimeError("Delete operations are not allowed")
        
        if not file_path.exists():
            raise RuntimeError(f"File {file_path} does not exist")
        
        try:
            if file_path.is_file():
                file_size = file_path.stat().st_size
                file_path.unlink()
                return {
                    "path": str(file_path),
                    "size": file_size,
                    "operation": "delete"
                }
            else:
                raise RuntimeError(f"{file_path} is not a file")
                
        except IOError as e:
            raise RuntimeError(f"Error deleting file {file_path}: {str(e)}")
    
    def _copy_file(self, source_path: Path, dest_path: Path, task: Optional[Task] = None) -> Dict[str, Any]:
        """
        Copy a file.
        
        Args:
            source_path: Path to the source file.
            dest_path: Path to the destination file.
            task: The task associated with this operation.
            
        Returns:
            Dictionary with information about the copy operation.
            
        Raises:
            RuntimeError: If there's an error copying the file.
        """
        if not self.allow_writes:
            raise RuntimeError("Copy operations require write permissions")
        
        if not source_path.exists():
            raise RuntimeError(f"Source file {source_path} does not exist")
        
        if not source_path.is_file():
            raise RuntimeError(f"{source_path} is not a file")
        
        # Create parent directories if they don't exist
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            self._check_file_size(source_path, task)
            shutil.copy2(source_path, dest_path)
            
            return {
                "source": str(source_path),
                "destination": str(dest_path),
                "size": dest_path.stat().st_size,
                "operation": "copy"
            }
                
        except IOError as e:
            raise RuntimeError(f"Error copying file {source_path} to {dest_path}: {str(e)}")
    
    def _move_file(self, source_path: Path, dest_path: Path, task: Optional[Task] = None) -> Dict[str, Any]:
        """
        Move a file.
        
        Args:
            source_path: Path to the source file.
            dest_path: Path to the destination file.
            task: The task associated with this operation.
            
        Returns:
            Dictionary with information about the move operation.
            
        Raises:
            RuntimeError: If there's an error moving the file.
        """
        if not self.allow_writes:
            raise RuntimeError("Move operations require write permissions")
        
        if not self.allow_deletes:
            raise RuntimeError("Move operations require delete permissions")
        
        if not source_path.exists():
            raise RuntimeError(f"Source file {source_path} does not exist")
        
        if not source_path.is_file():
            raise RuntimeError(f"{source_path} is not a file")
        
        # Create parent directories if they don't exist
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            self._check_file_size(source_path, task)
            file_size = source_path.stat().st_size
            shutil.move(str(source_path), str(dest_path))
            
            return {
                "source": str(source_path),
                "destination": str(dest_path),
                "size": file_size,
                "operation": "move"
            }
                
        except IOError as e:
            raise RuntimeError(f"Error moving file {source_path} to {dest_path}: {str(e)}")
    
    def _list_directory(self, directory_path: Path, task: Optional[Task] = None) -> Dict[str, Any]:
        """
        List the contents of a directory.
        
        Args:
            directory_path: Path to the directory to list.
            task: The task associated with this operation.
            
        Returns:
            Dictionary with information about the directory contents.
            
        Raises:
            RuntimeError: If there's an error listing the directory.
        """
        if not directory_path.exists():
            raise RuntimeError(f"Directory {directory_path} does not exist")
        
        if not directory_path.is_dir():
            raise RuntimeError(f"{directory_path} is not a directory")
        
        try:
            files = []
            directories = []
            
            for item in directory_path.iterdir():
                if item.is_file():
                    files.append({
                        "name": item.name,
                        "path": str(item.relative_to(self.base_directory)),
                        "size": item.stat().st_size,
                        "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat()
                    })
                elif item.is_dir():
                    directories.append({
                        "name": item.name,
                        "path": str(item.relative_to(self.base_directory)),
                        "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat()
                    })
            
            return {
                "directory": str(directory_path.relative_to(self.base_directory)),
                "files": files,
                "directories": directories,
                "total_files": len(files),
                "total_directories": len(directories)
            }
                
        except IOError as e:
            raise RuntimeError(f"Error listing directory {directory_path}: {str(e)}")
    
    def _file_exists(self, file_path: Path, task: Optional[Task] = None) -> Dict[str, Any]:
        """
        Check if a file exists.
        
        Args:
            file_path: Path to the file to check.
            task: The task associated with this operation.
            
        Returns:
            Dictionary with information about the file existence.
        """
        exists = file_path.exists()
        is_file = exists and file_path.is_file()
        is_dir = exists and file_path.is_dir()
        
        result = {
            "path": str(file_path),
            "exists": exists,
            "is_file": is_file,
            "is_directory": is_dir
        }
        
        if exists:
            result["size"] = file_path.stat().st_size if is_file else None
            result["modified"] = datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
        
        return result
    
    def _make_directories(self, directory_path: Path, task: Optional[Task] = None) -> Dict[str, Any]:
        """
        Create directories.
        
        Args:
            directory_path: Path to the directories to create.
            task: The task associated with this operation.
            
        Returns:
            Dictionary with information about the operation.
            
        Raises:
            RuntimeError: If there's an error creating the directories.
        """
        if not self.allow_writes:
            raise RuntimeError("Directory creation requires write permissions")
        
        try:
            directory_path.mkdir(parents=True, exist_ok=True)
            
            return {
                "path": str(directory_path),
                "operation": "makedirs",
                "exists": True
            }
                
        except IOError as e:
            raise RuntimeError(f"Error creating directories {directory_path}: {str(e)}")
    
    async def health_check(self) -> bool:
        """
        Check if the file system is accessible.
        
        Returns:
            True if the file system is healthy, False otherwise.
        """
        try:
            test_file = Path(self.base_directory) / ".health_check"
            test_content = f"Health check at {datetime.now().isoformat()}"
            
            # Check if we can write
            if self.allow_writes:
                with open(test_file, 'w', encoding='utf-8') as f:
                    f.write(test_content)
                
                # Check if we can read
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Clean up
                if self.allow_deletes:
                    test_file.unlink()
                
                return content == test_content
            else:
                # If we can't write, just check if the directory exists
                return Path(self.base_directory).exists() and Path(self.base_directory).is_dir()
                
        except Exception as e:
            self.logger.error(f"File system health check failed: {e}")
            return False
    
    async def get_health_details(self) -> Dict[str, Any]:
        """
        Get detailed health check results.
        
        Returns:
            Dictionary with health check results.
        """
        try:
            base_dir_path = Path(self.base_directory)
            is_healthy = base_dir_path.exists() and base_dir_path.is_dir()
            
            # Get disk usage information
            total_space = shutil.disk_usage(self.base_directory).total / (1024 * 1024 * 1024)
            free_space = shutil.disk_usage(self.base_directory).free / (1024 * 1024 * 1024)
            
            return {
                "healthy": is_healthy,
                "base_directory": self.base_directory,
                "base_directory_exists": base_dir_path.exists(),
                "is_directory": base_dir_path.is_dir() if base_dir_path.exists() else False,
                "allow_writes": self.allow_writes,
                "allow_deletes": self.allow_deletes,
                "max_file_size_mb": self.max_file_size_mb,
                "allowed_extensions": self.allowed_extensions,
                "disk_usage": {
                    "total_gb": round(total_space, 2),
                    "free_gb": round(free_space, 2),
                    "used_percent": round((1 - (free_space / total_space)) * 100, 2)
                }
            }
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {
                "healthy": False,
                "message": f"File system health check failed: {e}",
                "base_directory": self.base_directory
            }
    
    async def resolve(self, task: Task) -> TaskResult:
        """
        Resolve a file operation task.
        
        The task input_data should be a dictionary containing:
            - operation: The type of operation (READ, WRITE, APPEND, DELETE, COPY, MOVE, LIST, EXISTS, MAKEDIRS)
            - path: Path to the file or directory, relative to the base directory
            - format: Format of the file (text, binary, json, csv, yaml) for READ and WRITE operations
            - content: Content to write for WRITE and APPEND operations
            - destination: Destination path for COPY and MOVE operations
        
        Returns:
            TaskResult with the operation results.
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
            operation_str = input_data.get("operation", "").upper()
            if not operation_str:
                raise TaskError(
                    task=task,
                    error_type="MISSING_OPERATION",
                    message="Operation type is required",
                    details={"input_data": input_data}
                )
            
            # Try to parse as FileOperation enum
            try:
                operation = FileOperation(operation_str)
            except ValueError:
                raise TaskError(
                    task=task,
                    error_type="INVALID_OPERATION",
                    message=f"Invalid operation type: {operation_str}",
                    details={"input_data": input_data, "valid_operations": [op.value for op in FileOperation]}
                )
            
            # Extract common parameters
            path_str = input_data.get("path")
            if not path_str and operation != FileOperation.MAKEDIRS:
                raise TaskError(
                    task=task,
                    error_type="MISSING_PATH",
                    message="Path is required",
                    details={"input_data": input_data}
                )
            
            # Validate path if provided
            try:
                if path_str:
                    path = self._validate_path(path_str, task)
                else:
                    path = None
            except RuntimeError as e:
                raise TaskError(
                    task=task,
                    error_type="INVALID_PATH",
                    message=str(e),
                    details={"input_data": input_data}
                )
            
            # Handle different operation types
            if operation == FileOperation.READ:
                # Extract format
                format_str = input_data.get("format", "text").lower()
                try:
                    file_format = FileFormat(format_str)
                except ValueError:
                    raise TaskError(
                        task=task,
                        error_type="INVALID_FORMAT",
                        message=f"Invalid file format: {format_str}",
                        details={"input_data": input_data, "valid_formats": [f.value for f in FileFormat]}
                    )
                
                # Ensure path is not None
                if not path:
                    raise TaskError(
                        task=task,
                        error_type="MISSING_PATH",
                        message="Path is required for READ operation",
                        details={"input_data": input_data}
                    )
                
                # Read the file
                try:
                    content = self._read_file(path, file_format, task)
                    return TaskResult.success(
                        task=task,
                        output_data={
                            "content": content,
                            "path": str(path),
                            "format": file_format.value
                        }
                    )
                except RuntimeError as e:
                    raise TaskError(
                        task=task,
                        error_type="READ_ERROR",
                        message=str(e),
                        details={"input_data": input_data}
                    )
            
            elif operation in (FileOperation.WRITE, FileOperation.APPEND):
                # Extract format and content
                format_str = input_data.get("format", "text").lower()
                content = input_data.get("content")
                
                if content is None:
                    raise TaskError(
                        task=task,
                        error_type="MISSING_CONTENT",
                        message="Content is required for write operations",
                        details={"input_data": input_data}
                    )
                
                try:
                    file_format = FileFormat(format_str)
                except ValueError:
                    raise TaskError(
                        task=task,
                        error_type="INVALID_FORMAT",
                        message=f"Invalid file format: {format_str}",
                        details={"input_data": input_data, "valid_formats": [f.value for f in FileFormat]}
                    )
                
                # Write the file
                try:
                    # Ensure path is not None
                    if not path:
                        raise TaskError(
                            task=task,
                            error_type="MISSING_PATH",
                            message=f"Path is required for {operation.value} operation",
                            details={"input_data": input_data}
                        )
                    
                    result = self._write_file(
                        path, 
                        content, 
                        file_format, 
                        append=(operation == FileOperation.APPEND),
                        task=task
                    )
                    return TaskResult.success(
                        task=task,
                        output_data=result
                    )
                except RuntimeError as e:
                    raise TaskError(
                        task=task,
                        error_type="WRITE_ERROR",
                        message=str(e),
                        details={"input_data": input_data}
                    )
            
            elif operation == FileOperation.DELETE:
                # Ensure path is not None
                if not path:
                    raise TaskError(
                        task=task,
                        error_type="MISSING_PATH",
                        message="Path is required for DELETE operation",
                        details={"input_data": input_data}
                    )
                
                # Delete the file
                try:
                    result = self._delete_file(path, task)
                    return TaskResult.success(
                        task=task,
                        output_data=result
                    )
                except RuntimeError as e:
                    raise TaskError(
                        task=task,
                        error_type="DELETE_ERROR",
                        message=str(e),
                        details={"input_data": input_data}
                    )
            
            elif operation in (FileOperation.COPY, FileOperation.MOVE):
                # Extract destination
                dest_str = input_data.get("destination")
                if not dest_str:
                    raise TaskError(
                        task=task,
                        error_type="MISSING_DESTINATION",
                        message="Destination is required for copy and move operations",
                        details={"input_data": input_data}
                    )
                
                # Validate destination
                try:
                    dest_path = self._validate_path(dest_str, task)
                except RuntimeError as e:
                    raise TaskError(
                        task=task,
                        error_type="INVALID_DESTINATION",
                        message=str(e),
                        details={"input_data": input_data}
                    )
                
                # Perform the operation
                try:
                    # Ensure path is not None
                    if not path:
                        raise TaskError(
                            task=task,
                            error_type="MISSING_PATH",
                            message=f"Source path is required for {operation.value} operation",
                            details={"input_data": input_data}
                        )
                    
                    if operation == FileOperation.COPY:
                        result = self._copy_file(path, dest_path, task)
                    else:  # MOVE
                        result = self._move_file(path, dest_path, task)
                    
                    return TaskResult.success(
                        task=task,
                        output_data=result
                    )
                except RuntimeError as e:
                    error_type = "COPY_ERROR" if operation == FileOperation.COPY else "MOVE_ERROR"
                    raise TaskError(
                        task=task,
                        error_type=error_type,
                        message=str(e),
                        details={"input_data": input_data}
                    )
            
            elif operation == FileOperation.LIST:
                # Ensure path is not None
                if not path:
                    raise TaskError(
                        task=task,
                        error_type="MISSING_PATH",
                        message="Path is required for LIST operation",
                        details={"input_data": input_data}
                    )
                
                # List directory
                try:
                    result = self._list_directory(path, task)
                    return TaskResult.success(
                        task=task,
                        output_data=result
                    )
                except RuntimeError as e:
                    raise TaskError(
                        task=task,
                        error_type="LIST_ERROR",
                        message=str(e),
                        details={"input_data": input_data}
                    )
            
            elif operation == FileOperation.EXISTS:
                # Ensure path is not None
                if not path:
                    raise TaskError(
                        task=task,
                        error_type="MISSING_PATH",
                        message="Path is required for EXISTS operation",
                        details={"input_data": input_data}
                    )
                
                # Check if file exists
                try:
                    result = self._file_exists(path, task)
                    return TaskResult.success(
                        task=task,
                        output_data=result
                    )
                except RuntimeError as e:
                    raise TaskError(
                        task=task,
                        error_type="EXISTS_ERROR",
                        message=str(e),
                        details={"input_data": input_data}
                    )
            
            elif operation == FileOperation.MAKEDIRS:
                # Create directories
                try:
                    # If path wasn't provided, use the makedirs path
                    if not path:
                        makedirs_path = input_data.get("makedirs_path")
                        if not makedirs_path:
                            raise TaskError(
                                task=task,
                                error_type="MISSING_PATH",
                                message="Path is required for MAKEDIRS operation",
                                details={"input_data": input_data}
                            )
                        path = self._validate_path(makedirs_path, task)
                    
                    result = self._make_directories(path, task)
                    return TaskResult.success(
                        task=task,
                        output_data=result
                    )
                except RuntimeError as e:
                    raise TaskError(
                        task=task,
                        error_type="MAKEDIRS_ERROR",
                        message=str(e),
                        details={"input_data": input_data}
                    )
            
            else:
                # This should never happen as we validate against the enum
                raise TaskError(
                    task=task,
                    error_type="UNEXPECTED_ERROR",
                    message=f"Unexpected operation: {operation}",
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
            self.logger.error(f"Unexpected error in FileOperationsResolver: {e}", exc_info=True)
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