## Project Structure

```
OSPSD-Spring-26/
├── components/
│   ├── ai_client_api/                          # AI interface (abstract ABC)
│   │   ├── src/ai_client_api/
│   │   │   ├── __init__.py                     # Exports AiClientApi, AIResponse
│   │   │   ├── client.py                       # AiClientApi abstract base class
│   │   │   └── models.py                       # AIResponse, ToolDefinition, ToolParameter
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   ├── gemini_ai_client_impl/                  # Gemini implementation with tool calling
│   │   ├── src/gemini_ai_client_impl/
│   │   │   ├── __init__.py                     # Exports GeminiAiClient
│   │   │   ├── client.py                       # Gemini implementation with tool loop
│   │   │   └── tools.py                        # 6 storage tool Pydantic models
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   ├── chat_client_wrapper/                    # Notification wrapper (cross-vertical)
│   │   ├── src/chat_client_wrapper/
│   │   │   ├── __init__.py                     # Exports ChatNotificationWrapper
│   │   │   ├── wrapper.py                      # Notification wrapper logic
│   │   │   └── notifications.py                # NotificationMessages formatters
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
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
│   ├── cloud_storage_service/                  # FastAPI service with AI, auth, observability
│   │   ├── src/cloud_storage_service/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                         # 12 endpoints + DI + middleware
│   │   │   ├── auth.py                         # OAuth 2.0 authentication
│   │   │   ├── models.py                       # Pydantic request/response models
│   │   │   ├── sessions.py                     # In-memory session store
│   │   │   ├── slack_adapter.py                # SlackChatClient (Team 9 impl)
│   │   │   └── middleware/
│   │   │       ├── __init__.py                 # Exports PrometheusMiddleware
│   │   │       └── telemetry.py                # PrometheusMiddleware + 3 metrics
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
├── infrastructure/                             # Terraform IaC for Render deployment
│   ├── main.tf                                 # 3 Render services: cloud_storage, prometheus, grafana
│   ├── outputs.tf                              # Output URLs for dashboard/metrics
│   └── variables.tf                            # Render/GCP/Slack/Gemini configuration
│
├── monitoring/                                 # Prometheus + Grafana config
│   ├── Dockerfile.prometheus                   # Prometheus container
│   ├── Dockerfile.grafana                      # Grafana container
│   ├── prometheus.yml                          # Production scrape config (10s interval)
│   ├── prometheus-local.yml                    # Local dev scrape config
│   ├── grafana-datasource.yml                  # Prometheus datasource config
│   ├── grafana-dashboard-provider.yml          # Dashboard provisioning
│   └── grafana_dashboard.json                  # 7-panel dashboard definition
│
├── scripts/                                    # Build utilities
│   ├── __init__.py
│   └── apply_generator_patches.py              # Patches for openapi-python-client
│
├── tests/
│   ├── mocks/                                  # Reusable mock implementations
│   │   ├── __init__.py
│   │   ├── mock_ai_client.py                   # MockAiClientApi
│   │   └── mock_chat_client.py                 # MockChatClientApi
│   ├── integration/                            # Shared contract compliance tests
│   │   ├── conftest.py                         # Shared fixtures (autouse AI/chat mocks)
│   │   ├── test_di.py                          # DI + FakeClient contract proof
│   │   ├── test_ai_storage_flow.py             # AI + storage tool dispatch flows
│   │   └── test_ai_chat_flow.py                # AI + chat notification flows
│   └── e2e/                                    # Full workflow tests
│       ├── test_e2e.py                         # Local E2E (real GCS)
│       └── test_e2e_workflow.py                # Render E2E (post-deploy)
│
├── docs/                                       # Documentation
│   ├── index.md                                # Landing page with quick start
│   ├── CONTRIBUTING.md                         # Development workflow
│   ├── testing.md                              # Test execution guide
│   ├── circleci-setup.md                       # CI/CD configuration
│   ├── structure.md                            # This file
│   ├── design.md                               # Architecture + HW3 sections
│   ├── deployment.md                           # Terraform + Render setup
│   ├── observability.md                        # Prometheus/Grafana guide
│   └── components/                             # Per-component docs for mkdocs
│       ├── ai_client_api.md
│       ├── gemini_ai_client_impl.md
│       ├── chat_client_wrapper.md
│       ├── gcp_client_impl.md
│       ├── cloud_storage_adapter.md
│       ├── cloud_storage_service.md
│       └── cloud_storage_service_api_client.md
│
├── .circleci/
│   └── config.yml                              # 9-job CI/CD pipeline (CircleCI)
│
├── .github/
│   ├── pull_request_template.md
│   └── Issue_Template/
│       ├── bug_report.md
│       └── feature_request.md
│
├── mkdocs.yml                                  # Documentation site config
├── pyproject.toml                              # Root workspace config (uv, ruff, mypy, pytest, coverage)
├── main.py                                     # Sanity check entry point
├── openapi.json                                # OpenAPI spec from cloud_storage_service
├── gen_openapi.py                              # Script to regenerate openapi-python-client
├── Dockerfile                                  # FastAPI service container
├── coverage.xml                                # Code coverage report (CI)
└── README.md                                   # Project overview
```

## External Dependencies

- **cloud_storage_api** (v1.0.0) — Shared `CloudStorageClient` ABC from Team 6 cross-team repo
  - Source: https://github.com/2SpaceMasterRace/ospsd-cloud-storage (git dependency)
  
- **chat_client_api** — Shared `ChatClient` ABC from Team 9 cross-vertical integration
  - Source: https://github.com/HarshithKoriRaj/Shared-API (git dependency)

## Key Directories by Use Case

- **For Development:** Start with `CONTRIBUTING.md` (in docs/) and review components/*/README.md
- **For Testing:** See `docs/testing.md` for setup and execution
- **For CI/CD:** Review `.circleci/config.yml` and `docs/circleci-setup.md`
- **For Infrastructure:** Check `infrastructure/` and `docs/deployment.md`
- **For Observability:** See `monitoring/` and `docs/observability.md`
- **For AI Integration:** Review `components/gemini_ai_client_impl/` and `docs/components/gemini_ai_client_impl.md`
- **For Cross-Vertical Integration:** Check `components/chat_client_wrapper/` and `docs/components/chat_client_wrapper.md`