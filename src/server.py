"""
FastMCP server instance and configuration.

This module sets up the main MCP server instance and registers all tools.
"""

import signal
import sys
from typing import Any

from fastmcp import FastMCP

from . import __version__
from .auth import validate_api_credentials
from .tools import helpers, documents, schema, reports


# Global server instance
mcp = FastMCP("frappe-mcp-server")


def create_server() -> FastMCP:
    """Create and configure the MCP server instance."""
    
    # Validate API credentials at startup
    credentials_check = validate_api_credentials()
    if not credentials_check["valid"]:
        print(f"ERROR: {credentials_check['message']}", file=sys.stderr)
        print("The server will start, but most operations will fail without valid API credentials.", file=sys.stderr)
        print("Please set FRAPPE_API_KEY and FRAPPE_API_SECRET environment variables.", file=sys.stderr)
    else:
        print("API credentials validation successful.", file=sys.stderr)
    
    # Register all tool modules
    helpers.register_tools(mcp)
    documents.register_tools(mcp)
    schema.register_tools(mcp)
    reports.register_tools(mcp)
    
    return mcp


def start_server(server: FastMCP) -> None:
    """Start the MCP server with proper signal handling."""
    
    def signal_handler(sig: int, frame: Any) -> None:
        """Handle shutdown signals gracefully."""
        print("Shutting down Frappe MCP server...", file=sys.stderr)
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        print("Frappe MCP server running on stdio", file=sys.stderr)
        server.run()
    except Exception as error:
        print(f"Fatal error: {error}", file=sys.stderr)
        sys.exit(1)