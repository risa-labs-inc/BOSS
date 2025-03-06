# Dependency Version Tracker

This document tracks all dependencies in the project, their versions, when they were last updated, and their current status.

## Core Dependencies

| Package       | Version  | Updated    | Status      | Notes                                |
|---------------|----------|------------|-------------|--------------------------------------|
| python        | ^3.9     | 2024-03-05 | Up-to-date  | Project requirement                  |
| numpy         | ^1.22.0  | 2024-03-06 | Outdated    | Latest is ^2.2.3, update planned     |
| faiss-cpu     | ^1.7.4   | 2024-03-05 | Up-to-date  | ML feature indexing and search       |
| asyncio       | ^3.4.3   | 2024-03-05 | Up-to-date  | Async operations support             |
| together      | ^1.4.1   | 2024-03-05 | Up-to-date  | Latest Together AI API integration   |

## Development Dependencies

| Package       | Version  | Updated    | Status      | Notes                                |
|---------------|----------|------------|-------------|--------------------------------------|
| pytest        | ^7.3.1   | 2024-03-05 | Outdated    | Latest is ^8.3.5, update planned     |
| pytest-asyncio| ^0.21.0  | 2024-03-05 | Outdated    | Latest is ^0.25.3, update planned    |
| mypy          | ^1.3.0   | 2024-03-06 | Outdated    | Latest is ^1.15.0, update planned    |
| black         | ^23.3.0  | 2024-03-06 | Outdated    | Latest is ^25.1.0, update planned    |
| isort         | ^5.12.0  | 2024-03-05 | Outdated    | Latest is ^6.0.1, update planned     |
| flake8        | ^6.0.0   | 2024-03-05 | Outdated    | Latest is ^7.1.2, update planned     |

## Future/Planned Dependencies

| Package       | Planned Version | Status      | Notes                                |
|---------------|----------------|-------------|--------------------------------------|
| xai           | TBD            | Planned     | Not yet officially available         |

## How to Update the Tracker

1. When adding a new dependency, add a new entry to the relevant table
2. When updating a dependency, update the "Version" and "Updated" columns
3. Regularly review the "Status" column and check for newer versions with:
   ```
   ./scripts/poetry_latest.sh check [package-name]
   ```
4. After performing dependency updates, update this document

## Last Full Dependency Audit: 2024-03-06

Run a new full audit with:
```
./scripts/poetry_latest.sh update
``` 