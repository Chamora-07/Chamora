FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory to the root of the monorepo
WORKDIR /app

# 1. Copy workspace-level configuration
COPY pyproject.toml uv.lock ./
COPY db/ ./db/

# 2. Copy the ENTIRE sub-package directory
COPY packages/metrics_retriever/ ./packages/metrics_retriever/

# 3. Install dependencies
RUN uv sync --frozen --no-cache --package metrics_retriever

# 4. Copy the root orchestrator and services
COPY main.py ./
COPY services/ ./services/
COPY api/ ./api/

# 5. Ensure Python can find your workspace modules
ENV PYTHONPATH="/app:/app/packages/metrics_retriever"

# 6. Run via FastAPI — uses router.py + RetrieverManager (60s observer, not __main__)
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]