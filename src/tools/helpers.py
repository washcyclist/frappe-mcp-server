"""
Helper MCP tools for basic server operations.

This module provides basic utilities like ping, version info, 
and authentication validation tools.
"""

from typing import Any, Dict

from .. import __version__
from ..auth import validate_api_credentials


def register_tools(mcp: Any) -> None:
    """Register helper tools with the MCP server."""
    
    @mcp.tool()
    def ping() -> str:
        """A simple tool to check if the server is responding."""
        return "pong"
    
    @mcp.tool()
    def version() -> str:
        """Get version information for the Frappe MCP server."""
        return f"Frappe MCP Server version {__version__}"
    
    @mcp.tool()
    def validate_auth() -> Dict[str, Any]:
        """Validate API credentials and return authentication status."""
        return validate_api_credentials()