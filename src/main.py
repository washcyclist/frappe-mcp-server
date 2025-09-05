#!/usr/bin/env python3
"""
Main entry point for the Frappe MCP Server.

This module handles command-line arguments, version display, and server startup.
"""

import sys
import os
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Add current package to path for relative imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from . import __version__


def show_version() -> None:
    """Display version information."""
    print(__version__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Frappe MCP Server - Model Context Protocol server for Frappe Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Transport Examples:
  frappe-mcp-server                    # stdio transport (default)
  frappe-mcp-server --transport sse    # SSE transport on localhost:8000
  frappe-mcp-server -t sse -p 9000     # SSE transport on port 9000

Environment Variables:
  FRAPPE_API_KEY      - Frappe API key for authentication
  FRAPPE_API_SECRET   - Frappe API secret for authentication  
  FRAPPE_BASE_URL     - Base URL of Frappe site (e.g., https://site.frappe.cloud)
        """
    )
    
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Show version and exit"
    )
    
    parser.add_argument(
        "--transport", "-t",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio)"
    )
    
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for SSE transport (default: 127.0.0.1)"
    )
    
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8000,
        help="Port for SSE transport (default: 8000)"
    )
    
    return parser.parse_args()


def run_server() -> None:
    """Initialize and run the MCP server."""
    args = parse_args()
    
    # Handle version flag
    if args.version:
        show_version()
        sys.exit(0)
    
    print("Starting Frappe MCP server...", file=sys.stderr)
    print(f"Current working directory: {os.getcwd()}", file=sys.stderr)
    print(f"Transport: {args.transport}", file=sys.stderr)
    
    # Import server after version check to avoid loading overhead
    from .server import create_server, start_server
    
    server = create_server(host=args.host, port=args.port)
    start_server(server, transport=args.transport, host=args.host, port=args.port)


def main() -> None:
    """Main entry point for console script."""
    run_server()


if __name__ == "__main__":
    run_server()