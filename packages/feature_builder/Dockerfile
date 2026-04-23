FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory to the root of the monorepo
WORKDIR /app

# 1. Copy workspace-level configuration
COPY pyproject.toml uv.lock ./

# 2. Copy the shared database package
# Even if the builder doesn't use DB yet, keeping the root structure 
# consistent prevents uv sync errors in a workspace.
COPY db/ ./db/

# 3. Copy the feature_builder sub-package
COPY packages/feature_builder/ ./packages/feature_builder/

# 4. Install dependencies for this specific package
# Note: Use the 'name' defined in your packages/feature_builder/pyproject.toml
RUN uv sync --frozen --no-cache --package feature-builder

# 5. Ensure Python looks at the root for shared modules 
# and the package folder for the worker code
ENV PYTHONPATH="/app:/app/packages/feature_builder"

# 6. Run the worker loop
# We use the module flag (-m) to ensure relative imports inside the package work
CMD ["uv", "run", "python", "-m", "feature_builder.main"]