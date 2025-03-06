# BOSS - Business Operating System As A Service

BOSS is a comprehensive system designed to automate business operations through a flexible, composable architecture of task resolvers. It consists of two main components: Lanager Framework and Lighthouse.

## Project Architecture

```
BOSS
│
├── Lanager Framework - Task execution framework
│   ├── TaskResolver - Base component for resolving tasks
│   ├── Masteries - Execution workflows of TaskResolvers
│   └── Specialized TaskResolvers - LLM-based, API, etc.
│
└── Lighthouse - Data storage and registry
    ├── TaskResolver Registry - Catalog of available TaskResolvers
    ├── Mastery Registry - Catalog of available Masteries
    ├── Worklist - Queue of tasks to be performed
    └── Context Registry - Organizational values and context
```

For more detailed information about the implementation phases and timeline, see our:
👉 **[Implementation Plan](docs/implementation/implementation_plan.md)** 

## Core Concepts

### TaskResolver

TaskResolver is the foundational component of the BOSS system. Each TaskResolver:

- Takes an `InputTask` described in its specifications
- Processes the task using its internal logic
- Returns either a `TaskResult` or throws a `TaskError`
- Updates the Task model before returning/throwing
- Has a main function to check its health
- Contains metadata (version, depth, description, evolution strategy)

### Lanager

Lanager is a special type of TaskResolver that:

- Creates and executes "Masteries" (Python code that orchestrates TaskResolvers)
- Can pick existing Masteries from the registry or compose new ones
- Handles errors by evolving the specific TaskResolver or Mastery
- Can use other Lanagers of lower depth
- Avoids redundancy while maintaining specificity

### Lighthouse

Lighthouse is the data management component that:

- Maintains registries for TaskResolvers and Masteries
- Stores organizational context and values (goals, KPIs, etc.)
- Manages the worklist of tasks to be performed
- Provides a web interface for interaction with the system

## TaskResolver Testing and Tracking

Each TaskResolver must be thoroughly tested before being integrated into the system. After implementing a TaskResolver:

1. Run its `health_check` method to ensure it's properly set up
2. Test it with sample tasks appropriate for its functionality
3. Fix any bugs discovered during testing
4. Update the test tracking document
5. Make a git commit with a descriptive message about the TaskResolver

We maintain detailed tracking of TaskResolvers in two documents:

👉 **[Implemented and Tested TaskResolvers](implemented_and_tested_so_far.md)** 👈 - Tracks testing results for implemented TaskResolvers

👉 **[TaskResolvers Tracker](task_resolvers_tracker.md)** 👈 - Comprehensive list of all planned TaskResolvers with implementation status

These documents contain detailed information about all TaskResolvers in the system, their implementation status, and test results.

## Implementation Checklist

- [ ] Setup project with Poetry and define dependencies
- [ ] Create base TaskResolver models and interfaces
- [ ] Implement basic LLM TaskResolvers (OpenAI, Anthropic, Together AI)
- [ ] Create the Registry system with GraphQL, vector, and cache plugins
- [ ] Implement TaskResolver registry functionality
- [ ] Develop Mastery creation and execution capabilities
- [ ] Implement Lanager with evolution strategies
- [ ] Create Lighthouse database models and APIs
- [ ] Develop web interface for BOSS
- [ ] Add BOSS replication functionality for new organizations

## LLM Integration

BOSS integrates with multiple LLM providers:

- OpenAI (GPT models)
- Anthropic (Claude models)
- Together AI (various models)

## TaskResolver Types To Implement

1. **Base LLM TaskResolvers**
   - [ ] OpenAI GPT Resolver
   - [ ] Anthropic Claude Resolver
   - [ ] Together AI Resolver

2. **Registry TaskResolvers**
   - [ ] TaskResolver Registry Manager
   - [ ] Mastery Registry Manager
   - [ ] Health Check Resolver

3. **Lanager TaskResolvers**
   - [ ] Mastery Composer
   - [ ] Mastery Executor
   - [ ] TaskResolver Evolver

4. **Context TaskResolvers**
   - [ ] Organization Values Resolver
   - [ ] Historical Data Resolver
   - [ ] Context Provider Resolver

5. **Utility TaskResolvers**
   - [ ] API Wrapper Resolvers
   - [ ] Data Mapper Resolvers
   - [ ] Logic Resolvers

## Development Workflow

1. Implement base TaskResolver models and interfaces
2. Create basic LLM TaskResolvers with health checks
3. Develop the Registry system for TaskResolvers and Masteries
4. Implement Lanager with basic Mastery capabilities
5. Build the Lighthouse components
6. Create the web interface
7. Implement BOSS replication functionality

## Getting Started

```bash
# Clone the repository
git clone [repository-url]

# Install dependencies using Poetry
poetry install

# Activate the virtual environment
poetry shell

# Set up environment variables (copy .env.example to .env)
cp .env.example .env

# Run tests
pytest
```

## Contributing

1. Create specific TaskResolvers for new functionality
2. Ensure each TaskResolver has a proper health check
3. Document TaskResolver inputs, outputs, and errors
4. Update the Registry with new TaskResolvers
5. Update the [Implemented and Tested TaskResolvers](implemented_and_tested_so_far.md) document
6. Make a git commit documenting the TaskResolver implementation

## BOSS Replication

BOSS can be replicated for other organizations through a protected feature in the web interface. When creating a new BOSS instance:

1. A new repository is created and initialized with git
2. The core components are copied and configured
3. Organization-specific values and context are set up

This README will be updated as development progresses with detailed implementation notes and additional TaskResolvers.

# BOSS Python Agent

A self-evolving implementation generator powered by Claude API. This agent extracts requirements from documentation and automatically implements them with self-healing capabilities.

## Features

- **Automated Requirements Extraction**: Scans documentation to identify implementation requirements
- **AI-Powered Implementation Generation**: Leverages Claude API to generate high-quality Python code
- **Self-Healing Code Evolution**: Automatically detects and fixes issues in generated implementations
- **Comprehensive Error Handling**: Multi-layered error classification and recovery strategies
- **Diagnostic Monitoring**: Detailed metrics and health reporting for API calls and implementations
- **Configurable Behavior**: Extensive configuration options via config files or environment variables

## Installation

### Using Poetry (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-username/boss-py-agent.git
cd boss-py-agent

# Install dependencies using Poetry
poetry install

# Activate the virtual environment
poetry shell
```

### Using pip

```bash
# Clone the repository
git clone https://github.com/your-username/boss-py-agent.git
cd boss-py-agent

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root:

```
BOSS_API_KEY=your_claude_api_key
BOSS_MODEL=claude-3-7-sonnet-20240229
BOSS_DOCS_DIR=your/docs/directory
BOSS_IMPLEMENTATION_DIR=implementations
BOSS_REQUIREMENTS_DIR=requirements
```

Alternatively, you can create a JSON configuration file:

```json
{
  "api_key": "your_claude_api_key",
  "model": "claude-3-7-sonnet-20240229",
  "docs_dir": "your/docs/directory",
  "implementation_dir": "implementations",
  "requirements_dir": "requirements"
}
```

## Usage

### Scanning Documentation

```bash
python -m boss_py_agent --scan --docs-dir /path/to/docs
```

This command will scan the documents in the specified directory, extract requirements, and save them to a JSON file.

### Implementing Requirements

```bash
python -m boss_py_agent --implement --max-implementations 5
```

This will generate implementations for up to 5 pending requirements using the Claude API.

### Getting Status

```bash
python -m boss_py_agent --status
```

Display the current status of requirements extraction and implementation.

### Manually Evolving an Implementation

```bash
python -m boss_py_agent --evolve <implementation_id>
```

Manually trigger the evolution process for a specific implementation to fix issues.

## Advanced Features

### Self-Healing Evolution

The BOSS Python Agent includes advanced self-healing capabilities:

1. **Automatic Issue Detection**: The agent can detect syntax errors, import issues, and execution problems in generated code
2. **Intelligent Evolution**: Failed implementations are automatically evolved with feedback about the specific issue
3. **Progressive Learning**: Each evolution attempt builds on previous attempts, creating increasingly robust implementations

### Advanced Error Handling

The agent implements a sophisticated error handling system:

1. **Error Hierarchy**: Structured error classification with severity levels
2. **Recovery Strategies**: Different recovery strategies based on error type
3. **Error Tracking**: Comprehensive error history and statistics for debugging

### Diagnostics

The agent includes built-in diagnostic tools:

1. **Performance Metrics**: Tracks API call durations, success rates, and implementation statistics
2. **Health Reports**: Generates detailed health reports for monitoring agent performance
3. **System Metrics**: Collects system-level metrics (CPU, memory, disk usage) during operation

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=boss_py_agent
```

### Code Style

```bash
# Format code
black boss_py_agent

# Check types
mypy boss_py_agent

# Lint code
pylint boss_py_agent
```

## License

This project is licensed under the MIT License - see the LICENSE file for details. 