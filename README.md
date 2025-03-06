# BOSS - Business Operations System Solver

BOSS is a powerful framework for automating business operations through task resolvers. It provides a flexible architecture for handling various tasks from database operations to file handling and AI-powered text processing.

## Features

- **Modular Architecture**: Build and combine specialized task resolvers
- **Robust Error Handling**: Comprehensive error capturing and reporting
- **Retry Logic**: Customizable retry strategies with backoff options
- **Extensible Design**: Create your own task resolvers for specific business needs
- **LLM Integration**: Built-in support for OpenAI, Anthropic, and other LLM providers
- **Type Safety**: Fully typed with Python type annotations for better development experience
- **Health Checks**: Built-in system for verifying resolver functionality

## Key Components

### Core Components

- **Task**: A generic data model representing a unit of work
- **TaskResult**: The output of a task execution with status and metadata
- **TaskStatus**: Enum representing possible task states
- **TaskResolver**: Abstract base class for implementing task handling logic
- **TaskRetryManager**: Manages retry logic with various backoff strategies

### LLM Components

- **BaseLLMTaskResolver**: Base class for LLM-powered task resolvers
- **OpenAITaskResolver**: Resolver that uses OpenAI models
- **AnthropicTaskResolver**: Resolver that uses Anthropic Claude models
- **LLMTaskResolverFactory**: Factory for dynamically selecting LLM providers

### Utility Resolvers

- **DatabaseTaskResolver**: Handles SQL database operations
- **FileOperationsResolver**: Manages file system operations
- **LogicResolver**: Handles conditional logic and branching
- **DataMapperResolver**: Transforms data between different formats

## Installation

```bash
# Install with Poetry (recommended)
poetry add boss

# Or with pip
pip install boss
```

## Quick Start

```python
from boss.core import Task, TaskResolver
from boss.core.openai_resolver import OpenAITaskResolver

# Create a simple task
task = Task(
    input_data="Explain quantum computing in simple terms",
    metadata={"resolver": "openai"}
)

# Initialize a resolver
resolver = OpenAITaskResolver(
    model_name="gpt-4",
    api_key="your-api-key"
)

# Execute the task
result = resolver(task)

# Check the result
if result.status.is_success():
    print(f"Task succeeded: {result.output_data}")
else:
    print(f"Task failed: {result.error}")
```

## Example: Database Operations

```python
from boss.core import Task
from boss.utility.database_resolver import DatabaseTaskResolver

# Create a database resolver
db_resolver = DatabaseTaskResolver(
    connection_string="sqlite:///example.db",
    read_only=False
)

# Create a task to insert data
task = Task(
    input_data={
        "operation": "INSERT",
        "table": "users",
        "data": {"name": "Jane Doe", "email": "jane@example.com", "age": 28}
    }
)

# Execute the task
result = db_resolver(task)
print(f"Insert result: {result.status}")

# Create a task to query data
query_task = Task(
    input_data={
        "operation": "SELECT",
        "table": "users",
        "columns": ["name", "email"],
        "where": {"age": {"gt": 25}}
    }
)

# Execute the query task
query_result = db_resolver(query_task)
print(f"Query result: {query_result.output_data}")
```

## Example: File Operations

```python
from boss.core import Task
from boss.utility.file_operations_resolver import FileOperationsResolver

# Create a file operations resolver
file_resolver = FileOperationsResolver(
    base_directory="./files",
    max_file_size_mb=10
)

# Create a task to write data to a file
write_task = Task(
    input_data={
        "operation": "WRITE",
        "path": "data/report.json",
        "content": {"statistics": {"users": 1250, "active": 850}},
        "format": "json"
    }
)

# Execute the write task
write_result = file_resolver(write_task)
print(f"Write result: {write_result.status}")

# Create a task to read the file
read_task = Task(
    input_data={
        "operation": "READ",
        "path": "data/report.json",
        "format": "json"
    }
)

# Execute the read task
read_result = file_resolver(read_task)
print(f"Read result: {read_result.output_data}")
```

## Example: Chaining Resolvers

```python
from boss.core import Task
from boss.patterns.chained_resolver import ChainedResolver
from boss.utility.database_resolver import DatabaseTaskResolver
from boss.core.openai_resolver import OpenAITaskResolver

# Create individual resolvers
db_resolver = DatabaseTaskResolver(connection_string="sqlite:///example.db")
llm_resolver = OpenAITaskResolver(model_name="gpt-3.5-turbo", api_key="your-api-key")

# Create a chain of resolvers
chain = ChainedResolver([
    db_resolver,
    llm_resolver
])

# Create a task that will be processed by the chain
task = Task(
    input_data={
        "db_operation": {
            "operation": "SELECT",
            "table": "customer_feedback",
            "columns": ["feedback"],
            "limit": 10
        },
        "llm_prompt": "Summarize the following customer feedback: {db_result}"
    }
)

# Execute the chained task
result = chain(task)
print(f"Chain result: {result.output_data}")
```

## Documentation

For full documentation, visit [https://boss-docs.example.com](https://boss-docs.example.com)

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for more details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 