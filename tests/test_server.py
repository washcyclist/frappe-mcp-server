"""
Basic tests for the Frappe MCP Server.

These tests validate the server starts correctly and basic functionality works.
"""

import pytest
from src.server import create_server
from src.auth import validate_api_credentials
from src import __version__


def test_server_creation():
    """Test that the server can be created successfully."""
    server = create_server()
    assert server is not None
    # The server should be a FastMCP instance
    assert server.name == "frappe-mcp-server"


def test_version():
    """Test that version information is available."""
    assert __version__ is not None
    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_auth_validation_no_credentials():
    """Test authentication validation when no credentials are provided."""
    result = validate_api_credentials()
    assert isinstance(result, dict)
    assert "valid" in result
    assert "message" in result
    assert "details" in result
    # Without credentials set, should be invalid
    assert result["valid"] is False


@pytest.mark.asyncio
async def test_tool_imports():
    """Test that all tool modules can be imported successfully."""
    # Test document tools
    from src.tools import documents
    assert hasattr(documents, 'register_tools')
    
    # Test schema tools
    from src.tools import schema
    assert hasattr(schema, 'register_tools')
    
    # Test report tools
    from src.tools import reports
    assert hasattr(reports, 'register_tools')
    
    # Test helper tools
    from src.tools import helpers
    assert hasattr(helpers, 'register_tools')


def test_api_client_creation():
    """Test that the Frappe API client can be imported and configured."""
    from src.frappe_api import FrappeApiClient, FrappeApiError
    
    # Should be able to create client (though it will fail without proper config)
    assert FrappeApiClient is not None
    assert FrappeApiError is not None


@pytest.mark.asyncio
async def test_count_documents_tool_registration():
    """Test that the count_documents tool is properly registered."""
    server = create_server()
    
    # Get all tools from the server (returns a dict)
    tools = await server.get_tools()
    
    # Check that count_documents tool is registered
    assert "count_documents" in tools
    
    # Get the count_documents tool
    count_tool = tools["count_documents"]
    assert count_tool is not None
    
    # Check that the tool has proper documentation
    assert "Count documents in Frappe" in count_tool.description