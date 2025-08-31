# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based Model Context Protocol (MCP) server for Frappe Framework, built with FastMCP, uv for dependency management, and Docker for containerized deployment. The server provides comprehensive Frappe operations including document CRUD, schema introspection, and report generation.

## Development Commands

### Dependency Management (uv)
```bash
# Install dependencies with dev tools
uv sync --dev

# Install dependencies for production
uv sync --no-dev

# Add new dependency
uv add package-name

# Add development dependency  
uv add --dev package-name
```

### Development Server
```bash
# Run the server locally (stdio mode)
uv run python -m src.main

# Check version
uv run python -m src.main --version
```

### Testing
```bash
# Run all tests
uv run pytest

# Run tests with asyncio support
uv run pytest -v
```

### Code Quality
```bash
# Format code
uv run black src/ && uv run isort src/

# Type checking
uv run mypy src/
```

### Docker Development
```bash
# Build and run production container
docker-compose up -d frappe-mcp-server

# Build and run development container with volume mounts
docker-compose --profile development up frappe-mcp-dev

# Build development image
docker build --target development -t frappe-mcp-dev .
```

## Architecture Overview

### Core Structure
- **`src/main.py`**: Entry point with CLI argument handling and server startup
- **`src/server.py`**: FastMCP server instance creation and tool registration  
- **`src/frappe_api.py`**: HTTP client for Frappe API interactions
- **`src/auth.py`**: Authentication and credential validation

### Tool Organization
The MCP tools are organized in `src/tools/` by functionality:
- **`helpers.py`**: Basic utilities (ping, version, auth validation)
- **`documents.py`**: Document CRUD operations (create, read, update, delete, list)
- **`schema.py`**: DocType schema introspection and field analysis
- **`reports.py`**: Query reports, financial statements, and data exports

### Environment Configuration
Required environment variables in `.env`:
- `FRAPPE_API_KEY`: Frappe API key for authentication
- `FRAPPE_API_SECRET`: Frappe API secret for authentication  
- `FRAPPE_BASE_URL`: Base URL of the Frappe site (e.g., https://mysite.frappe.cloud)

## Key Dependencies

- **FastMCP**: Core MCP server framework
- **httpx**: Async HTTP client for Frappe API calls
- **Pydantic**: Data validation and serialization
- **uv**: Fast Python package manager

## Container Architecture

Multi-stage Docker build with three targets:
- **base**: Python 3.12 slim base image
- **production**: Minimal runtime with non-root user and health checks
- **development**: Includes dev dependencies and tools for local development

Resource limits aligned with MCP Toolkit requirements (1 CPU core, 2GB memory).