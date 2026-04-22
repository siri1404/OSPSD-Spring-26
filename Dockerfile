# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Copy workspace metadata first for better layer caching
COPY pyproject.toml uv.lock ./
COPY components components
COPY main.py openapi.json README.md ./

ENV UV_PROJECT_ENVIRONMENT=/app/.venv

# Add this line ↓
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

RUN uv sync --frozen --no-dev --no-editable --all-packages

ENV PORT=8000
EXPOSE 8000

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "uvicorn", "cloud_storage_service.main:app", "--host", "0.0.0.0", "--port", "8000"]