# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Copy workspace metadata first for better layer caching
COPY pyproject.toml uv.lock ./
COPY components components
COPY main.py openapi.json README.md ./

# --all-packages: installs every workspace member and all transitive deps.
# --no-editable: copies packages into .venv/site-packages as real installs,
#   not editable path references (required for containers).
# No changes to pyproject.toml needed — adding a new component just requires
# dropping it in components/ and running `uv lock`.
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
RUN uv sync --frozen --no-dev --no-editable --all-packages

ENV PORT=8000
EXPOSE 8000

# Use venv directly — avoids uv run re-resolving dependencies at startup
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "uvicorn", "cloud_storage_service.main:app", "--host", "0.0.0.0", "--port", "8000"]