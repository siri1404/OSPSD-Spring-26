## Project Structure

```
OSPSD-Spring-26/
├── components/
│   ├── cloud_storage_client_api/          # Interface component
│   │   ├── src/cloud_storage_client_api/
│   │   │   ├── __init__.py               # Public exports (CloudStorageClient, ObjectInfo, get_client)
│   │   │   ├── client.py                 # CloudStorageClient ABC + ObjectInfo
│   │   │   └── di.py                     # Dependency injection factory
│   │   ├── tests/                        # Unit tests for interface
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   └── gcp_client_impl/                   # GCP implementation
│       ├── src/gcp_client_impl/
│       │   ├── __init__.py               # Auto-registers with DI
│       │   └── client.py                 # GCPCloudStorageClient implementation
│       ├── tests/                        # Unit tests for GCP implementation
│       ├── pyproject.toml
│       └── README.md
│
├── tests/
│   ├── integration/                      # Integration tests (DI, provider interactions)
│   │   └── test_di.py
│   └── e2e/                              # End-to-end tests (real GCS)
│       └── test_e2e.py
│
├── docs/                                 # Full documentation
│   ├── index.md                         # Landing page with navigation
│   ├── CONTRIBUTING.md                  # Development workflow and standards
│   ├── testing.md                       # Test execution, setup, and debugging
│   ├── circleci-setup.md                # CI/CD configuration and troubleshooting
│   ├── structure.md                     # Project directory layout
│   └── design.md                        # Architecture patterns and design decisions
│
├── .circleci/
│   └── config.yml                        # CI/CD pipeline
│
├── .github/
│   ├── pull_request_template.md
│   └── Issue_Template/
│       ├── bug_report.md
│       └── feature_request.md
│
├── mkdocs.yml                            # Documentation site configuration
├── pyproject.toml                        # Root workspace config
├── .env.example                          # Environment variable template
└── README.md                             # Entire project README
```