FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory to the root of the monorepo
WORKDIR /app

# 1. Copy workspace-level configuration
COPY pyproject.toml uv.lock ./

# 2. Copy the ENTIRE sub-package directory
# This includes the pyproject.toml AND the metrics_retriever/ code folder
# Hatchling needs to see the folder to validate the package during sync
COPY packages/metrics_retriever/ ./packages/metrics_retriever/

# 3. Install dependencies
# uv will now find the code folder and Hatchling will be happy
RUN uv sync --frozen --no-cache --package metrics_retriever

# 4. Copy the root orchestrator
COPY main.py ./

# 5. Ensure Python can find your workspace modules
ENV PYTHONPATH="/app/packages/metrics_retriever"

# 6. Run the orchestrator
CMD ["uv", "run", "python", "main.py"]