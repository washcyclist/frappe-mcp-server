# Multi-stage Dockerfile for Frappe MCP Server using uv
FROM python:3.12-slim-bookworm AS base

# Set environment variables for production
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Builder stage - install uv and dependencies
FROM base AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.5.0 /uv /bin/uv

# Set uv environment variables for containerized builds
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# Create working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies into virtual environment
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copy source code
COPY src/ ./src/

# Install the package itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Production stage - minimal runtime
FROM base AS production

# Install runtime dependencies (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 mcpuser && \
    useradd --uid 1000 --gid mcpuser --shell /bin/bash --create-home mcpuser

# Copy virtual environment from builder
COPY --from=builder --chown=mcpuser:mcpuser /opt/venv /opt/venv

# Copy application code
COPY --from=builder --chown=mcpuser:mcpuser /app/src /app/src

# Set up environment
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/app/src:$PYTHONPATH"

# Switch to non-root user
USER mcpuser
WORKDIR /app

# Set resource limits (aligned with MCP Toolkit requirements)
# CPU limit: 1 core, Memory limit: 2GB (enforced by docker-compose)

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; from src.frappe_mcp_server import __version__; print(__version__); sys.exit(0)"

# Default command - run the MCP server
ENTRYPOINT ["python", "-m", "src.frappe_mcp_server.main"]
CMD []

# Development stage - includes dev dependencies and tools
FROM builder AS development

# Install development dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# Install additional development tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Set up development environment
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/app/src:$PYTHONPATH"

# Development port for HTTP mode
EXPOSE 8000

# Development user (can be root for convenience)
WORKDIR /app

# Default development command
CMD ["python", "-m", "src.frappe_mcp_server.main"]