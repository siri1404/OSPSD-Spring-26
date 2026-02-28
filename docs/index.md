# OSPSD-Spring-26

Vertical: Cloud Storage
A provider-agnostic cloud storage interface with a Google Cloud Storage implementation.
This project separates the storage interface from provider-specific implementations to ensure clean abstraction boundaries and extensibility.

---

## Components

This repo contains two components:
- Cloud Storage Interface: cloud_storage_client_api 
- GCP Implementation: cloud_storage_client_impl

---

## Features

- Upload files and raw bytes
- Download objects as bytes
- List objects by prefix
- Delete objects
- Retrieve object metadata without downloading contents

---

## Development Standards

- `mypy` runs in strict mode
- `ruff` enforces full linting rules
- Tests include unit, integration, and end-to-end coverage

---

See the navigation panel for detailed documentation.