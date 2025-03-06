# BOSS Python Agent - Package Structure

This directory contains the core code for the BOSS Python Agent, which is responsible for extracting requirements from documentation and automatically generating implementations with self-healing capabilities.

## Directory Structure

The package is organized as follows:

```
boss_py_agent/
│
├── core/                       # Core functionality
│   ├── implementation_orchestrator.py  # Handles implementation generation
│   └── requirements_extractor.py       # Extracts requirements from docs
│
├── utils/                      # Utility modules
│   ├── api_client.py           # Claude API client with retry logic
│   ├── diagnostics.py          # Metrics collection and health reporting
│   ├── error_handler.py        # Comprehensive error handling
│   ├── config_manager.py       # Configuration management
│   └── logging_config.py       # Logging setup
│
├── tests/                      # Unit and integration tests
│
├── boss_py_agent.py            # Main application class
├── __main__.py                 # Entry point for running as a package
├── __init__.py                 # Package initialization
├── run_agent.py                # Script for running the agent
└── install.sh                  # Installation script
```

## Key Components

### Implementation Orchestrator

The `ImplementationOrchestrator` class in `core/implementation_orchestrator.py` is responsible for:

- Generating code from requirements using the Claude API
- Organizing the code into a well-structured output format
- Validating implementations for syntax and other issues
- Evolving implementations when issues are detected
- Automatically refactoring large implementations into separate files

### Requirements Extractor

The `RequirementsExtractor` class in `core/requirements_extractor.py` handles:

- Scanning documentation to extract implementation requirements
- Storing requirements with status tracking
- Prioritizing requirements for implementation

### API Client

The `ClaudeAPIClient` class in `utils/api_client.py` provides:

- Robust connection to the Claude API
- Multiple retry strategies
- Rate limit handling
- Error classification and recovery

### Error Handling

The `ErrorHandler` class in `utils/error_handler.py` implements:

- A comprehensive error hierarchy
- Error severity classification
- Multiple recovery strategies
- Error tracking and statistics

### Diagnostics

The `Diagnostics` class in `utils/diagnostics.py` offers:

- Metrics collection for API calls and implementations
- System resource monitoring
- Health reporting and alerting

## Main Application

The `BossPyAgent` class in `boss_py_agent.py` ties everything together, providing:

- A unified interface for the agent's capabilities
- Configuration management
- Command-line interface

## Running the Agent

You can run the agent using:

```bash
python -m boss_py_agent [--scan|--implement|--status]
```

or by using the convenience script:

```bash
./run_agent.py [--scan|--implement|--status]
```

## Development

When developing or extending the agent, follow these guidelines:

1. Add new utility functions to the appropriate module in `utils/`
2. Place core functionality in the `core/` directory
3. Add tests for new functionality in the `tests/` directory
4. Keep file sizes manageable - refactor when a file exceeds 150 lines
5. Follow PEP 8 style guidelines with a maximum line length of 79 characters

## Features

- Automatic requirement extraction from documentation
- Prioritization of requirements for implementation
- Self-prompting implementation with Claude API
- Validation of implementations against requirements
- Status tracking for implemented and pending requirements
- Daemon mode for continuous implementation

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/BOSS.git
cd BOSS
```

2. Install dependencies using Poetry:
```bash
poetry install
```

3. Activate the virtual environment:
```bash
poetry shell
```

4. Set your Anthropic API key:
```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

## Usage

### Scanning Documentation

To scan documentation for requirements:

```bash
python -m boss_py_agent --scan --docs-dir ./docs
```

This will scan all files in the `docs` directory for requirements and save them to the requirements file.

### Starting Self-Prompting

To start the self-prompting process for one cycle:

```bash
python -m boss_py_agent --start
```

This will extract requirements, prioritize them, and implement them using the Claude API.

### Running in Daemon Mode

To run the agent in continuous mode:

```bash
python -m boss_py_agent --daemon
```

This will run the agent continuously until all requirements are implemented or the maximum number of cycles is reached.

### Checking Status

To check the status of requirements implementation:

```bash
python -m boss_py_agent --status
```

This will show the number of implemented and pending requirements, along with a list of pending requirements.

### Configuration

You can configure the agent using command-line arguments or a configuration file:

```bash
python -m boss_py_agent --config config.json
```

Example configuration file:

```json
{
  "docs_dir": "./docs",
  "implementation_dir": "./boss",
  "requirements_file": "./.boss_py_agent/requirements.json",
  "max_implementations_per_cycle": 5,
  "max_cycles": 100,
  "scan_interval": 3600
}
```

## Directories

- `boss_py_agent/core`: Core functionality for requirement extraction and implementation
- `boss_py_agent/utils`: Utility functions
- `boss_py_agent/tests`: Test files

## Replacing Shell Scripts

This Python agent is designed to replace the shell script-based implementation of the BOSS agent. After thorough testing and verification, you can remove the shell scripts.

## License

[Your License] 