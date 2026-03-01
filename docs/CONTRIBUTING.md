# Contributing Guide

## Getting Started

### Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) package manager
- Git configured with your GitHub account

### Setup

```bash
git clone https://github.com/siri1404/OSPSD-Spring-26.git
cd OSPSD-Spring-26
uv sync --all-packages --group dev
```

This installs both workspace packages (`cloud_storage_client_api` and `gcp_client_impl`) plus all dev tools (`pytest`, `ruff`, `mypy`, etc.).

## Project Structure

```
OSPSD-Spring-26/
├── components/
│   ├── cloud_storage_client_api/       # Abstract API package
│   │   ├── src/cloud_storage_client_api/
│   │   │   ├── client.py              # CloudStorageClient ABC + ObjectInfo
│   │   │   ├── di.py                  # DI registry (get_client / register / override)
│   │   │   └── __init__.py
│   │   └── tests/
│   │       ├── test_client_api.py
│   │       └── test_get_client.py
│   └── gcp_client_impl/               # GCP implementation package
│       ├── src/gcp_client_impl/
│       │   ├── client.py              # GCPCloudStorageClient
│       │   └── __init__.py            # Auto-registers on import
│       └── tests/
│           ├── test_config.py
│           ├── test_credentials.py
│           ├── test_object_info.py
│           ├── test_operations.py
│           ├── test_registration.py
│           └── test_storage_client.py
├── tests/
│   ├── integration/
│   │   └── test_di.py                 # Cross-component DI + thread-safety tests
│   └── e2e/
│       └── test_e2e.py                # Full workflow tests against real GCS
├── docs/
│   ├── CONTRIBUTING.md                # This file
│   ├── testing.md                     # Test strategy, markers, and commands
│   ├── circleci-setup.md              # CI/CD pipeline and environment setup
│   ├── design.md                      # Architecture patterns and design decisions
│   ├── structure.md                   # Project directory layout
│   └── index.md                       # Landing page with navigation
├── .circleci/
│   └── config.yml
└── pyproject.toml                     # Workspace config, ruff, mypy, pytest, coverage
```

## Development Workflow

### Before Committing

```bash
# Auto-fix and format
uv run ruff check . --fix
uv run ruff format .

# Type check (strict)
uv run mypy components/

# Unit tests with coverage (must reach 85 %)
uv run pytest components/ --cov=components/ --cov-fail-under=85

# Integration tests
uv run pytest tests/integration/ -v --no-cov
```

For the full test command reference and marker guide, see [testing.md](testing.md).
For running E2E tests with real GCS credentials, see [circleci-setup.md](circleci-setup.md).

### Commit Messages

Use conventional commit format:

| Prefix | When to use |
|---|---|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `test:` | Adding or updating tests |
| `docs:` | Documentation only |
| `refactor:` | Code restructuring without behaviour change |
| `chore:` | Tooling, deps, config |

### Pull Request Process

1. Keep your branch up to date:
   ```bash
   git fetch origin
   git rebase origin/main
   ```
2. Push your branch and open a PR on GitHub
3. Wait for all CircleCI jobs to pass (lint → typecheck → unit → integration → e2e)
4. Get at least one review approval
5. Address feedback in the same branch, then merge

## Code Style

### Type Hints

- All functions and methods must be fully annotated
- Use `from __future__ import annotations` at the top of every file
- Avoid `Any` unless interfacing with an untyped external library (`ANN401` is suppressed only in `gcp_client_impl` for Google Cloud objects)

### Docstrings

Public classes and methods must have Google-style docstrings:

```python
def upload_bytes(self, *, data: bytes, key: str) -> ObjectInfo:
    """Upload raw bytes to storage.

    Args:
        data: The bytes to upload.
        key: The object key/path in storage.

    Returns:
        ObjectInfo with metadata about the uploaded object.

    Raises:
        FileNotFoundError: If the object does not exist.
    """
```

### Tests

- Mark all tests with `@pytest.mark.unit`, `@pytest.mark.integration`, or `@pytest.mark.e2e`
- Unit tests must not make real network calls — use `unittest.mock` or `pytest-mock`
- Coverage must stay at or above **85 %** on `components/`

## Reporting Issues

**Bug?** Open a [Bug Report](https://github.com/siri1404/OSPSD-Spring-26/issues/new?template=bug_report.md). Include expected vs actual behaviour, steps to reproduce, and any error output.

**Feature idea?** Open a [Feature Request](https://github.com/siri1404/OSPSD-Spring-26/issues/new?template=feature_request.md). Include the problem statement, proposed solution, and alternatives considered.

Common labels: `bug`, `enhancement`, `docs`, `help wanted`, `good first issue`.

## Questions

Check existing issues first, then open a discussion or reach out to the maintainers.

