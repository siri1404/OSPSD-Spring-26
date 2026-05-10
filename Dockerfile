# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# git is required because pyproject.toml pulls chat-client-api as a git+https dependency
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Copy workspace metadata first for better layer caching
COPY pyproject.toml uv.lock ./
COPY components components
COPY main.py openapi.json README.md ./

ENV UV_PROJECT_ENVIRONMENT=/app/.venv

# Install dependencies. Using --all-packages ensures all workspace members
# (ai-client-api, gemini-ai-client-impl, etc.) are included even with --no-dev.
# Note: With uv workspaces, members are auto-discovered from [tool.uv.workspace]
# members list, so they're always available in a local build regardless of
# [dependency-groups]. However, --all-packages makes this explicit.
# See: https://docs.astral.sh/uv/concepts/workspaces/
RUN uv sync --frozen --no-dev --all-packages

ENV PORT=8000
EXPOSE 8000

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "uvicorn", "cloud_storage_service.main:app", "--host", "0.0.0.0", "--port", "8000"]