# Cloud Storage Client

Vertical: Cloud Storage (Teams 2, 6, 10)

A provider-agnostic cloud storage system implementing the shared cloud_storage_api contract (v1.0.0) with a Google Cloud Storage backend, Gemini AI tool-calling interface, Slack cross-vertical notifications, and Prometheus/Grafana observability.

## Quick Start

- [CONTRIBUTING.md](CONTRIBUTING.md) - Setup and development workflow
- [Testing Guide](testing.md) - Running tests and setting up credentials
- [Component Documentation]() - Per-component API docs available in sidebar

## Architecture

| Component | Role |
|---|---|
| cloud_storage_api (external) | Shared ABC, data models, exceptions - [repo](https://github.com/2SpaceMasterRace/ospsd-cloud-storage) |
| chat_client_api (external) | Cross-vertical chat ABC from Team 9 - [repo](https://github.com/HarshithKoriRaj/Shared-API) |
| ai_client_api | Abstract AI interface with tool calling support |
| gemini_ai_client_impl | Gemini 2.5 Flash implementation with 6 storage tools |
| chat_client_wrapper | Notification wrapper on top of Team 9's ChatClient |
| gcp_client_impl | GCP implementation of shared storage interface |
| cloud_storage_adapter | HTTP adapter implementing shared interface via generated client |
| cloud_storage_service | FastAPI service with AI chat, storage, auth, and telemetry |
| cloud_storage_service_api_client | Auto-generated OpenAPI client |

## Key Capabilities

- Upload from local files and binary file objects
- Download objects to local files
- List objects by prefix (sorted lexicographically)
- Get metadata without downloading
- Delete objects with typed result
- AI-powered natural language interface with tool calling
- Cross-vertical Slack notifications on storage and AI events
- Prometheus metrics with Grafana dashboards
- Provider-neutral exception handling

## Development Standards

| Tool | Standard |
|---|---|
| Python | 3.12+ |
| Type Checking | mypy strict mode |
| Code Quality | ruff with select = ["ALL"] |
| Testing | Unit + Integration + E2E |
| Coverage | 85%+ enforced in CI |

## Documentation Index

| Document | Purpose |
|---|---|
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development workflow and PR process |
| [Testing Guide](testing.md) | Test execution, credentials, debugging |
| [Project Structure](structure.md) | Directory layout |
| [CircleCI Setup](circleci-setup.md) | CI/CD configuration and env vars |
| [Architecture & Design](design.md) | Design patterns, AI integration, cross-vertical, observability |
| [Deployment](deployment.md) | Terraform IaC and Render deployment |
| [Observability](observability.md) | Prometheus metrics and Grafana dashboards |

## Component Documentation

- [AI Client API](components/ai_client_api.md) - Abstract AI interface and shared models
- [Gemini AI Client](components/gemini_ai_client_impl.md) - Gemini implementation with tool calling
- [Chat Client Wrapper](components/chat_client_wrapper.md) - Cross-vertical notification wrapper
- [GCP Implementation](components/gcp_client_impl.md) - Authentication, configuration, usage
- [Cloud Storage Adapter](components/cloud_storage_adapter.md) - HTTP adapter usage
- [Cloud Storage Service](components/cloud_storage_service.md) - FastAPI endpoints and auth
- [Generated API Client](components/cloud_storage_service_api_client.md) - Auto-generated client

## For Different Users

### Want to Contribute?

Start with [CONTRIBUTING.md](CONTRIBUTING.md)

### Running Tests?

See [Testing Guide](testing.md)

### Understanding the Architecture?

Read [Architecture & Design](design.md)

### Configuring GCP?

See [GCP Implementation](components/gcp_client_impl.md)

### Setting Up CI/CD?

Visit [CircleCI Setup](circleci-setup.md)

### Deploying to Render?

See [Deployment](deployment.md)

### Monitoring the Service?

Visit [Observability](observability.md)