# Frappe MCP Server (Python + uv + Docker)

A modern, containerized Python implementation of the Model Context Protocol (MCP) server for Frappe Framework, built with FastMCP, uv for dependency management, and Docker for deployment.

## Features

- **Document Operations**: Full CRUD operations for Frappe documents
- **Schema Introspection**: DocType field definitions and structure analysis
- **Report Generation**: Query reports, financial statements, and data exports
- **Method Calling**: Execute whitelisted Frappe methods
- **Authentication**: Secure API key/secret authentication

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Access to a Frappe site with API credentials

### Setup
```bash
git clone https://github.com/appliedrelevance/frappe_mcp_server_uv.git
cd frappe_mcp_server_uv
cp .env.example .env
# Edit .env with your Frappe credentials
docker-compose up -d frappe-mcp-server
```

## Available MCP Tools

### Document Operations
- `create_document`: Create new Frappe documents
- `get_document`: Retrieve document by DocType and name
- `update_document`: Update existing documents
- `delete_document`: Delete documents
- `list_documents`: Query documents with filters
- `call_method`: Execute whitelisted Frappe methods

### Schema Operations
- `get_doctype_schema`: Get complete DocType structure
- `get_field_options`: Get Link/Select field options
- `get_doctype_list`: List available DocTypes
- `get_frappe_usage_info`: Combined schema and usage information

### Report Operations
- `run_query_report`: Execute Frappe query reports
- `get_report_meta`: Get report metadata and structure
- `list_reports`: List available reports
- `run_doctype_report`: Generate DocType-based reports
- `get_financial_statements`: Access P&L, Balance Sheet, Cash Flow

### Helper Operations
- `ping`: Server health check
- `version`: Get server version information
- `validate_auth`: Check API credential status

## Development

```bash
# Install with development dependencies
uv sync --dev

# Run tests
uv run pytest

# Format code
uv run black src/ && uv run isort src/
```

## License

ISC License - see LICENSE file for details.