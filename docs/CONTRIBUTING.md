# Contributing Guide

## Getting Started

### Prerequisites

- Python 3.11 or higher
- `uv` package manager installed
- Git configured with your GitHub account

### Initial Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/siri1404/OSPSD-Spring-26.git
   cd OSPSD-Spring-26
   ```

2. Install dependencies:
   ```bash
   uv sync --all-packages

   ```

3. Create a branch for your work:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Workflow

### Before Committing

All code must pass quality checks and tests:

```bash
# 1. Format and lint
uv run ruff check . --fix              # Auto-fix linting issues
uv run ruff format .                   # Format code

# 2. Type checking
uv run mypy src tests                  # Static type validation

# 3. Run tests locally
uv run pytest src/ -v                  # Unit tests
uv run pytest tests/integration/ -v    # Integration tests (no credentials needed)
```

**Note**: If you have GCP credentials set up, you can also run:
```bash
uv run pytest tests/e2e/ -v           # E2E tests against real GCS
```

### Commit Messages

Follow conventional commit format for consistency:

- `feat: add GCP bucket listing` (new feature)
- `fix: handle permission denied errors` (bug fix)
- `test: add tests for upload_bytes` (tests)
- `docs: update API documentation` (documentation)
- `refactor: simplify client initialization` (refactoring)

### Pull Request Process

1. Ensure your branch is up to date with `main`:
   ```bash
   git fetch origin
   git rebase origin/main
   ```

2. Push your branch:
   ```bash
   git push origin feature/your-feature-name
   ```

3. Create a pull request on GitHub:
   - Use the [Pull Request Template](.github/pull_request_template.md)
   - Follow the sections: Summary, Problem Statement, Solution Overview, Detailed Changes, Technical Design
   - Include testing details and breaking changes if applicable

4. Wait for CircleCI to pass all checks (lint, type, unit tests)

5. Request review from at least one team member

6. Address feedback and push updates to the same branch

7. Merge after approval

## Project Structure

```
cloud-storage-client/
├── components/
│   ├── cloud_storage_client_api/       # Interface component
│   │   ├── src/cloud_storage_client_api/
│   │   │   ├── client.py              # CloudStorageClient ABC
│   │   │   ├── di.py                  # Dependency injection factory
│   │   │   └── __init__.py            # Public exports
│   │   └── tests/
│   │       └── test_get_client.py      # Test factory and DI
│   └── cloud_storage_client_impl/      # GCP implementation
│       ├── src/cloud_storage_client_impl/
│       │   ├── client.py              # GCPCloudStorageClient
│       │   ├── di.py                  # GCP registration
│       │   └── __init__.py            # Imports to trigger registration
│       └── tests/
│           └── test_client.py          # GCP client tests
├── tests/
│   └── integration/
│       └── tests_di.py                 # Cross-component DI tests
├── docs/
│   ├── circleci-setup.md              # CI/CD configuration
│   ├── testing.md                     # Testing strategy
│   └── DESIGN.md                      # Architecture & design
├── .circleci/
│   └── config.yml                     # CircleCI pipeline
└── pyproject.toml                     # Project dependencies
```

## Code Style Guidelines

### Type Hints
- All functions and methods must have type hints
- Use `from typing import ...` for complex types
- Avoid `Any` unless absolutely necessary

### Docstrings
- Public classes and methods must have docstrings
- Use Google-style format:
  ```python
  def upload_bytes(self, *, data: bytes, key: str) -> ObjectInfo:
      """Upload raw bytes to storage.
      
      Args:
          data: The bytes to upload.
          key: The object key/path in storage.
          
      Returns:
          ObjectInfo with metadata about the uploaded object.
          
      Raises:
          PermissionError: If credentials lack upload permissions.
      """
  ```

### Testing
- Write tests for all new features
- Aim for >85% code coverage
- Use `@pytest.mark.unit` for unit tests
- Use `@pytest.mark.integration` for integration tests
- Use `@pytest.mark.e2e` for end-to-end tests

### Reporting Issues

**Found a Bug?**
Open a [Bug Report](https://github.com/siri1404/OSPSD-Spring-26/issues/new?template=bug_report.md) using the provided template. Include:
- Summary of the issue
- Expected vs. actual behavior
- Steps to reproduce
- Severity level (Critical/High/Medium/Low)
- Error messages or logs

**Have a Feature Idea?**
Open a [Feature Request](https://github.com/siri1404/OSPSD-Spring-26/issues/new?template=feature_request.md) using the provided template. Include:
- Problem statement
- Proposed solution
- Use case and motivation
- Alternatives considered
- Impact and scope
- Priority level

### Keywords for Issues/PRs
- `bug`: Something is broken
- `enhancement`: New feature or improvement
- `docs`: Documentation update
- `help wanted`: Could use community help
- `good first issue`: Good for new contributors

## Running Tests

```bash
# All unit tests
uv run pytest src/ -v

# Integration tests
uv run pytest tests/integration/ -v

# With coverage report
uv run pytest src/ --cov=src --cov-report=term-missing

# Specific test file
uv run pytest components/cloud_storage_client_api/tests/test_get_client.py -v

# Tests matching a pattern
uv run pytest -k "test_upload" -v
```

## Debugging

### Local Development with GCP

If you want to test against real GCS locally:

1. Create a GCP service account and download the JSON key
2. Set the environment variable:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
   ```
3. Create a test bucket in GCS
4. Set the bucket name:
   ```bash
   export GCS_BUCKET_NAME=your-test-bucket
   ```
5. Run E2E tests:
   ```bash
   uv run pytest tests/e2e/ -v
   ```

### Viewing Test Coverage

After running tests with coverage:
```bash
uv run pytest src/ --cov=src --cov-report=html
open htmlcov/index.html
```

## Questions or Need Help?

- Check existing issues on GitHub
- Review the [Design Document](DESIGN.md)
- Ask in team discussions
- Reach out to the maintainers

---

