"""
Frappe MCP Server - Python implementation using FastMCP and uv.

A comprehensive Model Context Protocol server for Frappe Framework
with document operations, schema introspection, and helper tools.
"""

__version__ = "0.2.0"
__author__ = "Applied Relevance"


def main() -> None:
    """Main entry point for the MCP server."""
    from .main import run_server
    run_server()
