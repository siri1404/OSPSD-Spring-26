# Contributing Guide

## Getting Started

### Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) package manager
- Git configured with your GitHub account

### Setup

```bash
git clone https://github.com/siri1404/OSPSD-Spring-26.git
cd OSPSD-Spring-26
uv sync --all-packages --group dev
```

This installs all workspace packages (`ai_client_api`, `gemini_ai_client_impl`, `chat_client_wrapper`, `gcp_client_impl`, `cloud_storage_adapter`, `cloud_storage_service`, `cloud_storage_service_api_client`) plus the shared `cloud_storage_api` and `chat_client_api` git dependencies and all dev tools (`pytest`, `ruff`, `mypy`, etc.).

## Project Structure

```
OSPSD-Spring-26/
├── components/
│   ├── ai_client_api/                      # AI interface (abstract ABC)
│   ├── gemini_ai_client_impl/              # Gemini implementation with tool calling
│   ├── chat_client_wrapper/                # Notification wrapper (cross-vertical)
│   ├── gcp_client_impl/                    # GCP implementation of shared ABC
│   ├── cloud_storage_adapter/              # HTTP adapter implementing shared ABC
│   ├── cloud_storage_service/              # FastAPI service with AI, auth, observability
│   └── cloud_storage_service_api_client/   # Auto-generated OpenAPI client
├── infrastructure/                         # Terraform IaC for Render
├── monitoring/                             # Prometheus + Grafana config
├── tests/
│   ├── integration/                        # Contract compliance + AI/chat flows
│   ├── e2e/                                # Full workflow tests (local + deployed)
│   └── mocks/                              # Reusable mock implementations
├── docs/
├── .circleci/
│   └── config.yml
├── pyproject.toml                          # Workspace config, ruff, mypy, pytest, coverage
├── Dockerfile                              # FastAPI service container
└── main.py                                 # Sanity check entry point
```

External dependencies:

- `cloud_storage_api` — shared storage ABC from [ospsd-cloud-storage](https://github.com/2SpaceMasterRace/ospsd-cloud-storage) (pinned to `v1.0.0`)
- `chat_client_api` — shared chat ABC from Team 9 (pinned to commit rev)

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

For the full test command reference, see [testing.md](testing.md). For CI/CD setup, see [circleci-setup.md](circleci-setup.md).

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
def upload_file(self, container: str, local_path: str, remote_path: str) -> ObjectInfo:
    """Upload a local file to cloud storage.

    Args:
        container: Bucket/container name.
        local_path: Path to the local file.
        remote_path: Destination key in storage.

    Returns:
        ObjectInfo with metadata about the uploaded object.

    Raises:
        LocalFileAccessError: If local_path cannot be read.
        ObjectNotFoundError: If the container does not exist.
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

