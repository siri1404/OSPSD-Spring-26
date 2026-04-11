## Project Structure

```
OSPSD-Spring-26/
├── components/
│   ├── gcp_client_impl/                        # GCP implementation of shared ABC
│   │   ├── src/gcp_client_impl/
│   │   │   ├── __init__.py                     # Exports GCPCloudStorageClient
│   │   │   └── client.py                       # CloudStorageClient implementation
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   ├── cloud_storage_adapter/                  # HTTP adapter implementing shared ABC
│   │   ├── src/cloud_storage_adapter/
│   │   │   ├── __init__.py                     # Exports CloudStorageAdapter
│   │   │   └── adapter.py                      # CloudStorageClient over HTTP
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   ├── cloud_storage_service/                  # FastAPI service wrapping GCP impl
│   │   ├── src/cloud_storage_service/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                         # Endpoints
│   │   │   ├── auth.py                         # OAuth 2.0 authentication
│   │   │   ├── models.py                       # Pydantic request/response models
│   │   │   └── sessions.py                     # In-memory session store
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   └── cloud_storage_service_api_client/       # Auto-generated OpenAPI client
│       ├── cloud_storage_service_api_client/
│       │   ├── api/                            # Endpoint wrappers
│       │   ├── models/                         # Response/request models
│       │   ├── client.py                       # Client + AuthenticatedClient
│       │   └── types.py                        # Shared types (File, Response, Unset)
│       ├── pyproject.toml
│       └── README.md
│
├── tests/
│   ├── integration/                            # Shared contract compliance tests
│   │   └── test_di.py
│   └── e2e/                                    # Full workflow tests
│       └── test_e2e.py
│
├── docs/                                       # Documentation
│   ├── index.md
│   ├── CONTRIBUTING.md
│   ├── testing.md
│   ├── circleci-setup.md
│   ├── structure.md
│   ├── design.md
│   └── components/                             # Per-component docs for mkdocs
│
├── .circleci/
│   └── config.yml                              # CI/CD pipeline
│
├── .github/
│   ├── pull_request_template.md
│   └── Issue_Template/
│       ├── bug_report.md
│       └── feature_request.md
│
├── mkdocs.yml                                  # Documentation site config
├── pyproject.toml                              # Root workspace config (ruff, mypy, pytest, coverage)
├── main.py                                     # Sanity check entry point
├── openapi.json                                # OpenAPI spec for client generation
├── Dockerfile                                  # Container build
├── render.yaml                                 # Render deployment config
└── README.md                                   # Project overview
```

External dependency: The shared `cloud_storage_api` interface is not in this repo. It is pulled from https://github.com/2SpaceMasterRace/ospsd-cloud-storage as a pinned git dependency (`v1.0.0`).