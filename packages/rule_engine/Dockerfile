FROM python:3.12-slim

# 1. Copy uv binaries
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

# 2. Copy workspace config
COPY pyproject.toml uv.lock ./

# 3. Copy ALL packages (This ensures hatchling can see the whole workspace map)
COPY packages/ ./packages/
COPY db/ ./db/

# 4. Install everything in the workspace
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# 5. Environment setup
ENV PYTHONPATH="/app:/app/packages/rule_engine"

# 6. Run the engine
CMD ["uv", "run", "python", "-m", "rule_engine.main"]