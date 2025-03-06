# BOSS (Business Operations System Solver)

BOSS is a flexible framework for automating and orchestrating business operations through a system of specialized task resolvers.

## Overview

BOSS provides a modular architecture for defining, executing, and managing tasks across various business domains. At its core, BOSS consists of:

- **Task Models**: Standardized representations of work to be done
- **Task Resolvers**: Specialized components that process specific types of tasks 
- **Workflow Capabilities**: Ways to chain and orchestrate multiple resolvers

The framework is designed to be extensible, allowing organizations to integrate with various services, databases, APIs, and AI systems.

## Key Features

- **Flexible Task Resolution**: Process tasks with specialized resolvers based on task requirements
- **AI Integration**: Built-in support for LLM-based task processing with models like Claude
- **Database Operations**: Connect to and interact with various databases
- **File Handling**: Process files in various formats
- **Workflow Orchestration**: Chain multiple resolvers together for complex workflows
- **Error Handling**: Robust retry mechanisms and error tracking
- **Health Monitoring**: Built-in health checks for resolvers and dependencies

## Architecture

BOSS follows a modular architecture with these key components:

### Core Components

- **Task**: The fundamental unit of work with input data, status tracking, and error handling
- **TaskResult**: Represents the outcome of task processing
- **TaskResolver**: Abstract base class for all task resolvers
- **TaskStatus**: Enumeration of possible task states (PENDING, PROCESSING, COMPLETED, ERROR, etc.)

### Resolver Types

- **BaseLLMTaskResolver**: Base class for LLM-powered resolvers
- **AnthropicTaskResolver**: Resolver for Anthropic's Claude models
- **DatabaseTaskResolver**: Resolver for database operations
- **FileOperationsResolver**: Resolver for file handling
- **WorkflowResolver**: Resolver for chaining multiple resolvers

## Getting Started

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/BOSS.git
cd BOSS

# Install dependencies using Poetry
poetry install
```

### Basic Example

```python
import asyncio
from boss.core.task_models import Task
from boss.core.task_resolver import TaskResolverMetadata
from examples.chained_resolvers import DataExtractorResolver

async def main():
    # Create a task resolver with metadata
    metadata = TaskResolverMetadata(
        name="DataExtractor",
        version="1.0.0",
        description="Extracts data from structured input"
    )
    resolver = DataExtractorResolver(metadata)
    
    # Create a task
    task = Task(
        name="extract_user_info",
        description="Extract specific user fields",
        input_data={
            "data": {
                "username": "johndoe",
                "email": "john@example.com",
                "age": 30,
                "address": "123 Main St"
            },
            "extract_fields": ["username", "email", "age"]
        }
    )
    
    # Process the task
    result = await resolver(task)
    
    # Print the result
    print(f"Task status: {result.status}")
    print(f"Output: {result.output_data}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Examples

The `examples/` directory contains several examples demonstrating different capabilities of the BOSS framework:

- `chained_resolvers.py`: Shows how to chain multiple resolvers together
- `database_resolver.py`: Demonstrates database operations
- `file_operations_resolver.py`: Shows file handling capabilities
- `anthropic_example.py`: Demonstrates integration with Claude models

To run all examples:

```bash
python examples/run_examples.py --examples all
```

See the [examples README](examples/README.md) for more details.

## Development

### Project Structure

```
BOSS/
│
├── boss/               # Core framework
│   ├── core/           # Core components
│   │   ├── task_models.py      # Task and TaskResult models
│   │   ├── task_resolver.py    # Base TaskResolver class
│   │   ├── task_status.py      # Task status enum
│   │   ├── task_retry.py       # Retry logic
│   │   ├── base_llm_resolver.py # Base LLM resolver
│   │   ├── anthropic_resolver.py # Anthropic integration
│   │   └── llm_factory.py      # LLM provider factory
│   │
│   └── utils/          # Utility functions
│
├── examples/           # Example implementations
│   ├── chained_resolvers.py
│   ├── database_resolver.py
│   ├── file_operations_resolver.py
│   ├── anthropic_example.py
│   └── run_examples.py
│
├── tests/              # Test suite
│
├── pyproject.toml      # Project configuration
└── README.md           # Project documentation
```

### Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 