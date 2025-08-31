#!/usr/bin/env python3
"""
Main entry point for the Frappe MCP Server.

This module handles command-line arguments, version display, and server startup.
"""

import sys
import os
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


def check_version_flag() -> bool:
    """Check if version flag is present in command line arguments."""
    return "--version" in sys.argv or "-v" in sys.argv


def run_server() -> None:
    """Initialize and run the MCP server."""
    # Handle version flag before any other imports
    if check_version_flag():
        show_version()
        sys.exit(0)
    
    print("Starting Frappe MCP server...", file=sys.stderr)
    print(f"Current working directory: {os.getcwd()}", file=sys.stderr)
    
    # Import server after version check to avoid loading overhead
    from .server import create_server, start_server
    
    server = create_server()
    start_server(server)


if __name__ == "__main__":
    run_server()