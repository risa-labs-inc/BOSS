# Dependency Version Tracker

This document tracks all dependencies in the project, their versions, when they were last updated, and their current status.

## Core Dependencies

| Package       | Version  | Updated    | Status      | Notes                                |
|---------------|----------|------------|-------------|--------------------------------------|
| python        | ^3.10    | 2024-03-06 | Up-to-date  | Project requirement                  |
| numpy         | ^2.2.3   | 2024-03-06 | Up-to-date  | Latest version                       |
| faiss-cpu     | ^1.10.0  | 2024-03-06 | Up-to-date  | Latest version                       |
| asyncio       | ^3.4.3   | 2024-03-06 | Up-to-date  | Async operations support             |
| together      | ^1.4.1   | 2024-03-06 | Up-to-date  | Latest Together AI API integration   |
| xai-grok-sdk  | ^0.0.12  | 2024-03-06 | Up-to-date  | Official xAI Grok API client         |
| pyyaml        | ^6.0.2   | 2024-03-06 | Up-to-date  | YAML parsing/serialization support   |
| jsonschema    | ^4.23.0  | 2024-03-07 | Up-to-date  | JSON Schema validation               |

## Development Dependencies

| Package       | Version  | Updated    | Status      | Notes                                |
|---------------|----------|------------|-------------|--------------------------------------|
| pytest        | ^8.3.5   | 2024-03-06 | Up-to-date  | Latest version                       |
| pytest-asyncio| ^0.25.3  | 2024-03-06 | Up-to-date  | Latest version                       |
| mypy          | ^1.15.0  | 2024-03-06 | Up-to-date  | Latest version                       |
| black         | ^25.1.0  | 2024-03-06 | Up-to-date  | Latest version                       |
| isort         | ^6.0.1   | 2024-03-06 | Up-to-date  | Latest version                       |
| flake8        | ^7.1.2   | 2024-03-06 | Up-to-date  | Latest version                       |
| types-pyyaml  | ^6.0.12  | 2024-03-06 | Up-to-date  | Type stubs for PyYAML               |

## Other Dependencies (From Audit)

| Package           | Current Version | Latest Version | Status      | Notes                      |
|-------------------|----------------|----------------|-------------|----------------------------|
| click             | -              | ^8.1.8         | Outdated    | Update with other deps     |
| iniconfig         | -              | ^2.0.0         | Outdated    | Update with other deps     |
| mccabe            | -              | ^0.7.0         | Outdated    | Update with other deps     |
| mypy-extensions   | -              | ^1.0.0         | Outdated    | Update with other deps     |
| packaging         | -              | ^24.2          | Outdated    | Update with other deps     |
| pathspec          | -              | ^0.12.1        | Outdated    | Update with other deps     |
| platformdirs      | -              | ^4.3.6         | Outdated    | Update with other deps     |
| pluggy            | -              | ^1.5.0         | Outdated    | Update with other deps     |
| pycodestyle       | -              | ^2.12.1        | Up-to-date  | Updated with latest flake8 |
| pyflakes          | -              | ^3.2.0         | Up-to-date  | Updated with latest flake8 |
| typing-extensions | -              | ^4.12.2        | Outdated    | Update with other deps     |
| requests          | -              | ^2.31.0        | Up-to-date  | Added with xai-grok-sdk    |

## Future/Planned Dependencies

| Package       | Planned Version | Status      | Notes                                |
|---------------|----------------|-------------|--------------------------------------|
| official-grok-sdk | TBD        | Planned     | When official Grok 3 API is released |

## How to Update the Tracker

1. When adding a new dependency, add a new entry to the relevant table
2. When updating a dependency, update the "Version" and "Updated" columns
3. Regularly review the "Status" column and check for newer versions
4. After performing dependency updates, update this document

## Last Full Dependency Audit: 2024-03-06

## Update Plan (Q2 2024)

1. Monitor for official Grok 3 API release (priority: high)
2. Update all remaining indirect dependencies (priority: medium)
3. Update secondary dependencies (priority: low)

## Dependency Tracker

| Package | Current Version | Latest Version | Last Updated |
|---------|----------------|----------------|--------------|
| psutil | 5.9.8 | 5.9.8 | 2024-06-11 |
| jinja2 | 3.1.3 | 3.1.3 | 2024-06-11 |
| types-jinja2 | 2.11.9 | 2.11.9 | 2024-06-11 |
| matplotlib | 3.8.2 | 3.8.2 | 2024-06-11 |
| fastapi | 0.108.0 | 0.108.0 | 2024-06-11 |
| uvicorn | 0.25.0 | 0.25.0 | 2024-06-11 |
| httpx | 0.28.1 | 0.28.1 | 2024-03-07 | 