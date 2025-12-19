# Builder stage - has shell and package management tools
FROM python:3.11-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Change the working directory to the `app` directory
WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --link-mode=copy

# Copy the project into the image
ADD . /app

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --link-mode=copy

# Production stage - distroless (no shell, minimal attack surface)
ARG PYTHON_VERSION=3.11
FROM gcr.io/distroless/python3-debian12:nonroot

WORKDIR /app

# Copy the entire virtual environment
COPY --from=builder /app/.venv /app/.venv

# Copy the application code
COPY --from=builder /app/src /app/src
COPY --from=builder /app/pyproject.toml /app/pyproject.toml

# Expose port for MCP server (standardized on 8080)
EXPOSE 8080

# Set port environment variable
ENV PORT=8080

# Set Python path to include the virtual environment and source directories
ENV PYTHONPATH=/app/.venv/lib/python3.11/site-packages:/app/src:/app

# Run as non-root user (uid 65532 by default in distroless :nonroot)
# No USER directive needed - already non-root

# Run the MCP server with the distroless Python
ENTRYPOINT ["/usr/bin/python3"]
CMD ["-m", "prefect_mcp_server"]
