# BOSS Framework Examples

This directory contains example implementations and demonstrations of the BOSS (Business Operations System Solver) framework.

## Overview

These examples showcase different TaskResolvers and how they can be used to solve various types of tasks:

1. **Chained Resolvers** - Shows how to chain multiple TaskResolvers together to create a workflow
2. **Database Operations** - Demonstrates a TaskResolver that interacts with an SQLite database
3. **File Operations** - Illustrates how to create a TaskResolver for handling file-related tasks
4. **LLM Resolvers** - Examples of TaskResolvers that interact with large language models:
   - Anthropic Claude (requires an API key)

## Running the Examples

You can run all examples using the `run_examples.py` script:

```bash
# Run all examples
python examples/run_examples.py

# Run specific examples
python examples/run_examples.py --examples chained database

# Run all examples and clean up after
python examples/run_examples.py --examples all --clean
```

### Available Examples

- `chained` - Shows how TaskResolvers can be chained together to form workflows
- `database` - Demonstrates database operations with SQLite
- `file` - Shows file reading, writing, and processing capabilities
- `anthropic` - Demonstrates integrating with Anthropic's Claude (requires `ANTHROPIC_API_KEY` environment variable)

## Example Descriptions

### Chained Resolvers (`chained_resolvers.py`)

This example shows how to build a workflow by chaining multiple TaskResolvers together. It demonstrates:

- Extracting data from a structured input
- Transforming data based on operations
- Validating data against rules
- Chaining these operations together in a workflow

### Database Operations (`database_resolver.py`)

This example shows how to create a TaskResolver that interacts with an SQLite database, including:

- Executing queries (SELECT, INSERT, UPDATE, DELETE)
- Handling parameters and query results
- Getting database schema information
- Ensuring proper error handling and resource cleanup

### File Operations (`file_operations_resolver.py`)

This example demonstrates working with files and directories:

- Reading and writing various file formats (text, JSON, CSV)
- Listing directory contents
- Copying, moving, and deleting files
- Managing file permissions and validation

### Anthropic Resolver (`anthropic_example.py`)

This example shows how to use the BOSS framework with Anthropic's Claude models:

- Configuring API access
- Sending prompts and processing responses
- Using different model variations
- Error handling and retries

## Integration with Core BOSS Components

These examples build on top of the core BOSS components:

- `Task` and `TaskResult` models for representing tasks and their results
- `TaskResolver` abstract base class for implementing resolvers
- `TaskStatus` for tracking the state of tasks

## Additional Resources

For more information about the BOSS framework, see the main [README.md](../README.md) file in the project root directory. 