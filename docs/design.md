# Design Document: Cloud Storage Client Architecture

## Overview

This document explains the architectural design decisions for the OSPSD Spring '26 Cloud Storage Client project, including why certain patterns were chosen and how new providers can be added.

---

## Design Principles

### 1. Separation of Concerns

The project separates the **interface contract** from **provider implementations**:

- **Interface** (`cloud_storage_client_api`): Defines what operations a storage client must support
- **Implementation** (`gcp_client_impl`): Provides concrete implementation for a specific provider

**Benefit:** Consumers write code against the interface, not the implementation. Switching providers requires only changing which package is imported.

### 2. Abstraction Barriers

The interface package has **zero dependencies** on external SDKs:

```python
# cloud_storage_client_api/client.py
from abc import ABC, abstractmethod  # Only stdlib

class CloudStorageClient(ABC):
    @abstractmethod
    def upload_bytes(self, *, data: bytes, key: str, ...) -> ObjectInfo:
        pass
```

The implementation package provides the provider-specific logic:

```python
# gcp_client_impl/client.py
from google.cloud import storage  # Provider dependency here

class GCPCloudStorageClient(CloudStorageClient):
    def upload_bytes(self, *, data: bytes, key: str, ...) -> ObjectInfo:
        # Actual GCS implementation
```

**Benefit:** 
- No dependency leakage into the interface
- Interface remains stable as providers evolve
- Easy to test interface without downloading provider SDKs

### 3. Dependency Injection (DI)

The project uses a **registry-based DI pattern** with context variable overrides:

```python
# Register a provider
def register_get_client(fn: GetClient, name: str = "default") -> None:
    _registry[name] = fn

# Retrieve a provider
def get_client(name: str = "default") -> CloudStorageClient:
    return _registry[name]()

# Override for testing
@override_get_client(fake_client, name="test"):
    # Within this context, get_client() returns fake_client
```

**Benefits:**
- **No global state pollution:** Each test can inject its own provider via context
- **Thread-safe:** ContextVar ensures isolation across concurrent tests
- **Auto-wiring:** Implementation registers itself on import
- **Multiple providers:** Can coexist natively via named providers

### 4. Configuration Management

Configuration uses a **precedence hierarchy**:

```
Constructor kwargs > Environment variables > Defaults (ADC)
```

For example, `GCPCloudStorageClient`:

```python
def __init__(self, *, bucket_name: str | None = None, ...):
    # Step 1: Use constructor arg if provided
    # Step 2: Fall back to GCS_BUCKET_NAME env var
    # Step 3: Error if neither provided
```

**Benefits:**
- Constructor args override environment for flexibility
- Environment variables allow CI/CD configuration without code changes
- Defaults (Application Default Credentials) work without setup
- Testing can override all layers

---

## Component Architecture

### cloud_storage_client_api

Provides the abstract contract and DI infrastructure.

**Files:**

1. **client.py**
   - `CloudStorageClient(ABC)` — Base class with 6 abstract methods
   - `ObjectInfo` — Immutable dataclass for metadata

2. **di.py**
   - `register_get_client()` — Register a provider factory
   - `unregister_get_client()` — Remove a provider
   - `get_client()` — Retrieve a provider instance
   - `override_get_client()` — Context manager for test isolation

3. **__init__.py**
   - Public exports: `CloudStorageClient`, `ObjectInfo`, `get_client`, `register_get_client`

**Design Rationale:**

- **Why ABC?** Enforces contract; any subclass must implement all methods
- **Why ObjectInfo?** Immutable dataclass ensures metadata isn't accidentally modified
- **Why ContextVar?** Allows test isolation without global state or thread-local storage

### gcp_client_impl

Provides Google Cloud Storage implementation.

**Files:**

1. **client.py**
   - `GCPClientConfig` — Configuration container (frozen dataclass)
   - `GCPCloudStorageClient` — Concrete implementation of `CloudStorageClient`
   - `_build_credentials()` — Three-tier auth: service account file → env var JSON → ADC
   - `_build_storage_client()` — Lazy initialization with proper error handling

2. **__init__.py**
   - Auto-registers `GCPCloudStorageClient` with DI on import
   - Provides both "gcp" and "default" provider names

**Design Rationale:**

- **Why lazy initialization?** Defers credential loading until first use; errors caught at runtime with clear messages
- **Why three auth modes?** Supports dev (file), CI/CD (env var), and production (ADC/Workload Identity)
- **Why base64 support?** CI/CD systems (CircleCI) can't store files safely; env vars are more flexible
- **Why class-level config check?** Validates configuration before any network calls


**Test Markers:**

- `@pytest.mark.unit` — Fast, isolated, mocked provider calls
- `@pytest.mark.integration` — Component interactions without external dependencies
- `@pytest.mark.e2e` — Real GCS against test bucket (slow, requires credentials)
- `@pytest.mark.circleci` — Runnable in CI without local credential files
- `@pytest.mark.local_credentials` — Requires local GOOGLE_APPLICATION_CREDENTIALS file

---

## Authentication Strategy

### Three Authentication Modes

#### Mode 1: Service Account File Path
**Use Case:** Local development, CI/CD with file-based secrets

```python
import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/path/to/key.json"

client = GCPCloudStorageClient()
```

**GCP Processing:**
- Reads `GOOGLE_APPLICATION_CREDENTIALS` env var
- Loads JSON from file path
- Creates credentials from JSON
- Advantage: Works with gcloud CLI and most GCP tools

#### Mode 2: Service Account JSON (Env Var)
**Use Case:** CircleCI and other CI systems that can't store files

```python
import base64
import os

key_json = {...}  # Service account JSON
key_b64 = base64.b64encode(json.dumps(key_json).encode()).decode()
os.environ["GCP_SERVICE_KEY"] = key_b64

client = GCPCloudStorageClient()
```

**GCP Processing:**
1. Try to decode as base64
2. Fall back to treating as raw JSON
3. Parse JSON
4. Create credentials from parsed JSON

**Advantage:** Works with string-based secrets in CI systems

#### Mode 3: Application Default Credentials (ADC)
**Use Case:** Production with Workload Identity, local gcloud CLI

```python
# No env vars needed; uses:
# 1. ~/.config/gcloud/application_default_credentials.json (gcloud login)
# 2. Metadata server (Workload Identity on GKE)
# 3. Service account attached to compute instance (GCE)

client = GCPCloudStorageClient()
```

**Advantage:** Zero configuration; automatic in production environments

### Priority Resolution

When multiple credentials are available, priority is:

```python
if credentials_path (arg or GOOGLE_APPLICATION_CREDENTIALS):
    Use file-based credentials
elif GCP_SERVICE_KEY:
    Parse JSON and use credentials
else:
    Use Application Default Credentials
```

---

## Error Handling Philosophy

All errors are **fail-fast and informative**:

### Configuration Errors (Fail Immediately)

```python
# Missing bucket config
client = GCPCloudStorageClient()  # Before any network call:
# RuntimeError: "GCS bucket is not configured. Set `GCS_BUCKET_NAME` or pass `bucket_name`"

# Missing dependencies
import gcp_client_impl
# RuntimeError: "google-cloud-storage is not installed. Install dependencies: `uv sync`"
```

### Credential Errors (Fail on First Use)

```python
# Invalid GCP_SERVICE_KEY
client = GCPCloudStorageClient(bucket_name="test")
client.upload_bytes(data=b"test", key="test.txt")
# RuntimeError: "GCP_SERVICE_KEY must be valid JSON... or base64-encoded JSON"
```

### Operational Errors (Propagate GCS Errors)

```python
# Object not found
client.download_bytes(key="nonexistent.txt")
# FileNotFoundError: GCS object not found

# Permission denied
client.delete(key="protected.txt")
# PermissionError: Access denied by GCS
```

---

## Extending to Other Providers

### Template: Adding AWS S3 Support

Step 1: Create component structure

```bash
mkdir -p components/aws_client_impl/src/aws_client_impl/tests
```

Step 2: Implement `CloudStorageClient`

```python
# components/aws_client_impl/src/aws_client_impl/client.py
from cloud_storage_client_api import CloudStorageClient, ObjectInfo

class AWSCloudStorageClient(CloudStorageClient):
    def __init__(self, *, bucket_name: str | None = None, ...):
        # Read AWS_BUCKET_NAME, AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
        pass
    
    def upload_bytes(self, *, data: bytes, key: str, ...) -> ObjectInfo:
        # Use boto3 to upload to S3
        pass
    
    # Implement remaining 5 methods
```

Step 3: Register with DI

```python
# components/aws_client_impl/src/aws_client_impl/__init__.py
from cloud_storage_client_api import register_get_client
from aws_client_impl.client import AWSCloudStorageClient

def _make_aws_client() -> CloudStorageClient:
    return AWSCloudStorageClient()

register_get_client(_make_aws_client, name="aws")
register_get_client(_make_aws_client)  # Also as default
```

Step 4: Add comprehensive tests

```python
# components/aws_client_impl/tests/
# test_config.py       — AWS config precedence
# test_credentials.py  — IAM role, access key parsing
# test_operations.py   — S3 upload, download, list, delete
```

Step 5: Use in code

```python
import aws_client_impl
from cloud_storage_client_api import get_client

client = get_client(name="aws")  # Or get_client() if aws is default
client.upload_bytes(data=b"test", key="test.txt")
```

### Checklist for New Providers

- [ ] Component created under `components/`
- [ ] Implements all 6 `CloudStorageClient` methods
- [ ] Configuration reads from environment variables with constructor override
- [ ] Comprehensive unit tests (config, credentials, operations)
- [ ] DI registration in `__init__.py` (both named and default)
- [ ] README documenting config vars and auth modes
- [ ] CI/CD tests use appropriate markers (`@pytest.mark.circleci`, `@pytest.mark.local_credentials`)

---

## Testing Philosophy

### Isolation Layers

1. **Interface Tests** (`cloud_storage_client_api/tests/`)
   - Verify ABC contract
   - Test DI factory
   - No provider dependencies

2. **Unit Tests** (`gcp_client_impl/tests/`)
   - Mock Google Cloud Storage SDK
   - Test config precedence
   - Test error handling
   - Fast execution (< 1 second total)

3. **Integration Tests** (`tests/integration/`)
   - Verify DI across components
   - Test provider switching
   - Test thread safety and context isolation
   - No external dependencies

4. **E2E Tests** (`tests/e2e/`)
   - Real GCS against test bucket
   - Full workflows: upload → head → download → list → delete
   - Separate markers for env-var and file-based credentials
   - Slow but validates entire system

### Coverage Requirements

- Minimum 85% code coverage (enforced in CI)
- Untestable lines marked with `# pragma: no cover`
- All error paths covered

---

## Type System

The project uses **strict mypy** with minimal exceptions:

### Why Strict?

1. **Catches Bugs Early:** Type errors prevent runtime failures
2. **Documents Intent:** Type hints serve as inline documentation
3. **Tooling Support:** IDEs can provide better autocomplete and refactoring
4. **Maintainability:** Future developers understand expected types

### Exception Handling

```python
# google.auth.* doesn't have complete type stubs
[[tool.mypy.overrides]]
module = ["google.auth.*"]
ignore_missing_imports = true

# Pytest fixtures are challenging to type
[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_decorators = false
```

### Type Annotations Style

```python
# Use | for unions (Python 3.10+)
def upload_bytes(
    self,
    *,
    data: bytes,
    key: str,
    metadata: Mapping[str, str] | None = None,
) -> ObjectInfo:
    pass

# Use TYPE_CHECKING for circular imports
if TYPE_CHECKING:
    from collections.abc import Mapping
```

---

## Code Quality Standards

### Linting with Ruff

- **select = ["ALL"]** — Enable all rules
- **Justified ignores:**
  - `D203`, `D213` — Docstring conflicts with formatter
  - `COM812`, `ISC001` — Conflict with black formatter
  - `S101` in tests — `assert` is required for pytest
  - `ANN` in tests — Type hints less critical in test code
  - `SLF001` in tests — Private member access OK when testing internals

### Formatting with Ruff

- 130 character line length
- Consistent indentation
- No unused imports

### Docstring Conventions

```python
"""Single-line summary for simple functions."""

def complex_function(x: int) -> str:
    """Brief summary.

    Longer description if needed, explaining the logic and edge cases.

    Args:
        x: Parameter description and type.

    Returns:
        Return value description.

    Raises:
        ValueError: When input is invalid.
    """
```

---

## Dependency Management

### Why `uv`?

- **Fast:** Reimplemented Python package manager in Rust
- **Workspace Support:** Monorepo management built-in
- **Lock File:** Deterministic dependencies across machines
- **No requirements.txt:** Cleaner package declarations

### Workspace Structure

```yaml
[tool.uv.workspace]
members = ["components/*"]  # Auto-discovers both components

[tool.uv.sources]
cloud_storage_client_api = { workspace = true }
gcp-client-impl = { workspace = true }
```

### Installation

```bash
uv sync              # Install all packages + dev tools
uv sync --group dev  # Only dev tools
```
