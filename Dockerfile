FROM python:3.12-slim

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first (standard optimization)
COPY pyproject.toml uv.lock ./

COPY packages/ ./packages/

# Install project dependencies
RUN uv sync --frozen --no-cache --no-install-project

# Copy the whole project structure
COPY . .

RUN uv sync --frozen --no-cache

# Expose FastAPI port
EXPOSE 8000

# Run as a module so internal imports like 'from db.models' work perfectly
CMD ["uv", "run", "python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]