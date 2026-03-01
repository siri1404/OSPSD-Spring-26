# Cloud Storage Client API

**Vertical:** Cloud Storage

A provider-agnostic cloud storage interface with a production-ready Google Cloud Storage implementation. This project demonstrates clean architectural patterns through separation of interface from implementation.

---

## Quick Start

New to the project? Start here:

1. **[CONTRIBUTING.md](CONTRIBUTING.md)** - Setup and development workflow
2. **[Testing Guide](testing.md)** - Running tests and setting up credentials
3. **[Component READMEs](../components)** - API and implementation documentation

---

## Project Overview

### Architecture

- **cloud_storage_client_api** — Abstract interface (`CloudStorageClient` ABC) with DI system
- **gcp_client_impl** — Google Cloud Storage implementation with flexible authentication

### Key Capabilities

✓ Upload files and raw bytes  
✓ Download objects  
✓ List by prefix  
✓ Get metadata without downloading  
✓ Delete objects  
✓ Custom metadata support  

### Design Goals

- **Provider Agnostic** — Swap implementations without changing code
- **Testable** — Built-in mocking and test isolation with context variables
- **Extensible** — Support multiple cloud providers simultaneously
- **Type-Safe** — Strict `mypy` with full type hints

---

## Development Standards

| Tool | Standard |
|------|----------|
| Type Checking | `mypy` strict mode |
| Code Quality | `ruff` with all rules enabled |
| Testing | Unit + Integration + E2E coverage |
| Target Coverage | 85%+ with `pytest-cov` |

---

## Documentation Index

| Document | Purpose |
|----------|---------|
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development workflow & pull request process |
| [Testing Guide](testing.md) | Test execution, setup, credentials, and debugging |
| [Project Structure](structure.md) | Directory layout and component organization |
| [CircleCI Setup](circleci-setup.md) | CI/CD configuration and environment variables |
| [Architecture & Design](design.md) | Design patterns, DI system, authentication modes |

**Component Documentation:**
- [cloud_storage_client_api](../components/cloud_storage_client_api/README.md) — Interface contract, methods, and DI system
- [gcp_client_impl](../components/gcp_client_impl/README.md) — GCP implementation, authentication modes, and configuration

---

## For Different Users

**Want to Contribute?**  
→ Start with [CONTRIBUTING.md](CONTRIBUTING.md)

**Running Tests?**  
→ See [Testing Guide](testing.md) for credentials setup and test execution

**Understanding the Architecture?**  
→ Read [Architecture & Design](design.md)

**Using the API?**  
→ Check [cloud_storage_client_api README](../components/cloud_storage_client_api/README.md)

**Configuring GCP?**  
→ See [gcp_client_impl README](../components/gcp_client_impl/README.md)

**Setting Up CI/CD?**  
→ Visit [CircleCI Setup](circleci-setup.md)