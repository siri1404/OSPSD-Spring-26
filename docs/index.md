# Cloud Storage Client

**Vertical:** Cloud Storage (Teams 2, 6, 10)

A provider-agnostic cloud storage system implementing the shared `cloud_storage_api` contract (`v1.0.0`) with a Google Cloud Storage backend, FastAPI service, and HTTP adapter.

## Quick Start

1. [CONTRIBUTING.md](CONTRIBUTING.md) - Setup and development workflow
2. [Testing Guide](testing.md) - Running tests and setting up credentials
3. [Component READMEs](../components) - Per-component API documentation

## Architecture

| Component | Role |
|---|---|
| `cloud_storage_api` (external) | Shared ABC, data models, exceptions - [repo](https://github.com/2SpaceMasterRace/ospsd-cloud-storage) |
| `gcp_client_impl` | GCP implementation of shared interface |
| `cloud_storage_adapter` | HTTP adapter implementing shared interface via generated client |
| `cloud_storage_service` | FastAPI service wrapping GCP implementation |
| `cloud_storage_service_api_client` | Auto-generated OpenAPI client |

## Key Capabilities

- Upload from local files and binary file objects
- Download objects to local files
- List objects by prefix (sorted lexicographically)
- Get metadata without downloading
- Delete objects with typed result
- Provider-neutral exception handling

## Development Standards

| Tool | Standard |
|---|---|
| Python | `3.12+` |
| Type Checking | `mypy` strict mode |
| Code Quality | `ruff` with `select = ["ALL"]` |
| Testing | Unit + Integration + E2E |
| Coverage | `85%+` enforced in CI |

## Documentation Index

| Document | Purpose |
|---|---|
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development workflow and PR process |
| [Testing Guide](testing.md) | Test execution, credentials, debugging |
| [Project Structure](structure.md) | Directory layout |
| [CircleCI Setup](circleci-setup.md) | CI/CD configuration and env vars |
| [Architecture & Design](design.md) | Design patterns and component interactions |

**Component Documentation:**

- [GCP Implementation](../components/gcp_client_impl/README.md) - Authentication, configuration, usage
- [Cloud Storage Adapter](../components/cloud_storage_adapter/README.md) - HTTP adapter usage
- [Cloud Storage Service](../components/cloud_storage_service/README.md) - FastAPI endpoints and auth
- [Generated API Client](../components/cloud_storage_service_api_client/README.md) - Auto-generated client

## For Different Users

**Want to Contribute?**

Start with [CONTRIBUTING.md](CONTRIBUTING.md)

**Running Tests?**

See [Testing Guide](testing.md)

**Understanding the Architecture?**

Read [Architecture & Design](design.md)

**Configuring GCP?**

See [GCP Implementation README](../components/gcp_client_impl/README.md)

**Setting Up CI/CD?**

Visit [CircleCI Setup](circleci-setup.md)