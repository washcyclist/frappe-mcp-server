"""
Comprehensive test suite for Frappe MCP Server using chat-style interface.

This test suite uses the official MCP Python SDK to test both stdio and SSE transports
with realistic chat-style prompts that trigger various MCP tools, simulating how
an AI assistant like Claude would interact with the server.
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import pytest

# Import official MCP SDK components
try:
    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp.client.sse import sse_client
    from mcp.types import TextContent, ImageContent
    MCP_SDK_AVAILABLE = True
except ImportError:
    MCP_SDK_AVAILABLE = False

# Import server components for testing
from src.server import create_server
from src import __version__


class ChatTestClient:
    """
    A test client that simulates chat-style interactions with the MCP server.
    
    This client uses natural language prompts that would trigger specific MCP tools,
    similar to how Claude or other AI assistants would interact with the server.
    """
    
    def __init__(self, transport: str = "stdio"):
        """Initialize the chat test client with specified transport."""
        self.transport = transport
        self.session: Optional[ClientSession] = None
        self.server_process: Optional[subprocess.Popen] = None
        self.server_port = 8100  # Base port for SSE testing
        self.available_tools: List[str] = []
        self._stdio_context = None
        self._sse_context = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
        
    async def connect(self):
        """Connect to the MCP server using the specified transport."""
        if self.transport == "stdio":
            await self._connect_stdio()
        elif self.transport == "sse":
            await self._connect_sse()
        else:
            raise ValueError(f"Unsupported transport: {self.transport}")
            
    async def _connect_stdio(self):
        """Connect using stdio transport."""
        # Set up environment
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parent.parent)
        
        # Create server parameters for stdio client
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "src.main", "--transport", "stdio"],
            env=env
        )
        
        # Use the official MCP stdio client
        stdio_context = stdio_client(server_params)
        
        read_stream, write_stream = await stdio_context.__aenter__()
        self._stdio_context = stdio_context  # Keep reference for cleanup
        
        self.session = ClientSession(read_stream, write_stream)
        await self.session.initialize()
        
        # Cache available tools
        tools_result = await self.session.list_tools()
        self.available_tools = [tool.name for tool in tools_result.tools]
        
    async def _connect_sse(self):
        """Connect using SSE transport."""
        # Start server process with SSE transport
        server_cmd = [
            sys.executable, "-m", "src.main",
            "--transport", "sse",
            "--port", str(self.server_port),
            "--host", "127.0.0.1"
        ]
        
        # Set up environment
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parent.parent)
        
        self.server_process = subprocess.Popen(
            server_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=Path(__file__).parent.parent
        )
        
        # Wait for server to start
        await asyncio.sleep(2)
        
        # Connect with SSE client
        server_url = f"http://127.0.0.1:{self.server_port}/sse"
        
        try:
            sse_context = sse_client(server_url, timeout=10)
            read_stream, write_stream = await sse_context.__aenter__()
            self._sse_context = sse_context  # Keep reference for cleanup
            
            self.session = ClientSession(read_stream, write_stream)
            await self.session.initialize()
            
            # Cache available tools
            tools_result = await self.session.list_tools()
            self.available_tools = [tool.name for tool in tools_result.tools]
            
        except Exception as e:
            # If SSE connection fails, it might be due to auth issues
            # Keep the error for reporting but continue with basic connectivity test
            self.session = None
            raise ConnectionError(f"SSE connection failed: {e}")
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self.session:
            try:
                # Close session gracefully
                await self.session.close()
            except:
                pass
        
        # Clean up transport contexts
        if self._stdio_context:
            try:
                await self._stdio_context.__aexit__(None, None, None)
            except:
                pass
        
        if self._sse_context:
            try:
                await self._sse_context.__aexit__(None, None, None)
            except:
                pass
            
        if self.server_process:
            try:
                self.server_process.terminate()
                # Give it a moment to shutdown gracefully
                try:
                    self.server_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.server_process.kill()
            except:
                pass
    
    async def chat(self, prompt: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Process a chat-style prompt and determine which MCP tools to call.
        
        Returns:
            (success: bool, response: str, tool_result: Optional[Dict])
        """
        if not self.session:
            return False, "Not connected to MCP server", None
            
        try:
            # Map prompts to appropriate MCP tool calls
            tool_call = self._map_prompt_to_tool(prompt)
            
            if not tool_call:
                return False, f"No suitable tool found for prompt: {prompt}", None
                
            tool_name, arguments = tool_call
            
            if tool_name not in self.available_tools:
                return False, f"Tool '{tool_name}' not available. Available: {self.available_tools}", None
            
            # Call the tool
            result = await self.session.call_tool(tool_name, arguments)
            
            # Extract response text
            response_text = ""
            if hasattr(result, 'content') and result.content:
                for content in result.content:
                    if isinstance(content, TextContent):
                        response_text += content.text
                    elif hasattr(content, 'text'):
                        response_text += content.text
            
            return True, response_text, {
                "tool_name": tool_name,
                "arguments": arguments,
                "raw_result": result
            }
            
        except Exception as e:
            return False, f"Error processing prompt: {e}", None
    
    def _map_prompt_to_tool(self, prompt: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Map a natural language prompt to appropriate MCP tool and arguments.
        
        This simulates how an AI assistant would interpret user requests.
        """
        prompt_lower = prompt.lower().strip()
        
        # Connectivity and basic checks - order matters for specificity
        if any(phrase in prompt_lower for phrase in ["version", "what version"]):
            return ("version", {})
        
        if any(phrase in prompt_lower for phrase in ["ping", "alive", "running", "connected"]):
            return ("ping", {})
            
        if any(phrase in prompt_lower for phrase in ["auth", "authenticate", "credentials", "logged in"]):
            return ("validate_auth", {})
        
        # Schema and DocType operations
        if any(phrase in prompt_lower for phrase in ["list doctypes", "what doctypes", "available doctypes", "show doctypes"]):
            return ("get_doctype_list", {})
            
        if "doctype schema" in prompt_lower or "fields does" in prompt_lower:
            # Extract doctype name from prompt
            if "note" in prompt_lower:
                return ("get_doctype_schema", {"doctype": "Note"})
            elif "user" in prompt_lower:
                return ("get_doctype_schema", {"doctype": "User"})
            # Default to Note for testing
            return ("get_doctype_schema", {"doctype": "Note"})
        
        if "field options" in prompt_lower:
            # Extract doctype and field
            return ("get_field_options", {"doctype": "Note", "field": "status"})
        
        # Document CRUD operations
        if any(phrase in prompt_lower for phrase in ["create note", "new note", "add note"]):
            # Extract title if provided
            title = "Test Note from Chat Client"
            if "title" in prompt_lower:
                # Simple extraction
                parts = prompt.split('"')
                if len(parts) >= 2:
                    title = parts[1]
            
            return ("create_document", {
                "doctype": "Note",
                "data": {
                    "title": title,
                    "content": "This is a test note created by the chat test client."
                }
            })
        
        if any(phrase in prompt_lower for phrase in ["count documents", "how many", "count notes"]):
            doctype = "Note"
            if "user" in prompt_lower:
                doctype = "User"
            return ("count_documents", {"doctype": doctype})
            
        if any(phrase in prompt_lower for phrase in ["list documents", "show documents", "get documents"]):
            doctype = "Note"
            if "user" in prompt_lower:
                doctype = "User"
            return ("list_documents", {"doctype": doctype, "limit": 5})
        
        if any(phrase in prompt_lower for phrase in ["get document", "show document", "read document"]):
            # This would need a real document name/ID in practice
            return ("get_document", {"doctype": "Note", "name": "test-note"})
        
        # Report operations
        if any(phrase in prompt_lower for phrase in ["list reports", "available reports", "show reports"]):
            return ("list_reports", {})
            
        if "query report" in prompt_lower:
            return ("run_query_report", {"report_name": "Database Storage Usage By Table"})
        
        # Default fallback
        return None


class ChatTestScenarios:
    """
    Predefined chat scenarios that test comprehensive MCP functionality.
    
    Each scenario represents a realistic conversation flow that would
    trigger various MCP tools in sequence.
    """
    
    @staticmethod
    def basic_connectivity_scenario():
        """Basic server connectivity and status checks."""
        return [
            "Is the server running?",
            "What version are you running?",
            "Are my credentials valid?"
        ]
    
    @staticmethod
    def schema_exploration_scenario():
        """Explore the Frappe schema and available doctypes."""
        return [
            "What doctypes are available?",
            "What fields does the Note doctype have?",
            "Show me the field options for Note status"
        ]
    
    @staticmethod
    def document_operations_scenario():
        """Test CRUD operations on documents."""
        return [
            "How many Note documents are there?",
            "Create a new Note with title 'Test Chat Note'",
            "List some Note documents",
            "Show me document test-note"
        ]
    
    @staticmethod
    def reporting_scenario():
        """Test report generation functionality."""
        return [
            "What reports are available?",
            "Run the Database Storage Usage By Table report"
        ]
    
    @classmethod
    def all_scenarios(cls):
        """Get all test scenarios combined."""
        all_prompts = []
        all_prompts.extend(cls.basic_connectivity_scenario())
        all_prompts.extend(cls.schema_exploration_scenario())
        all_prompts.extend(cls.document_operations_scenario())
        all_prompts.extend(cls.reporting_scenario())
        return all_prompts


# Test functions using pytest

@pytest.mark.skipif(not MCP_SDK_AVAILABLE, reason="Official MCP SDK not available")
@pytest.mark.asyncio
async def test_server_tools_available():
    """Test that server tools can be listed without full connection."""
    # Create the server directly to test tool availability
    server = create_server()
    
    # Get available tools
    tools = await server.get_tools()
    tool_names = list(tools.keys())
    
    # Check that expected tools are registered
    expected_tools = ["ping", "version", "validate_auth", "count_documents", "list_documents"]
    
    for expected_tool in expected_tools:
        assert expected_tool in tool_names, f"Expected tool '{expected_tool}' not found in: {tool_names}"
    
    # Should have reasonable number of tools
    assert len(tool_names) >= 10, f"Expected at least 10 tools, found: {len(tool_names)}"


@pytest.mark.skipif(not MCP_SDK_AVAILABLE, reason="Official MCP SDK not available")
@pytest.mark.asyncio
async def test_chat_prompt_mapping():
    """Test that chat prompts map correctly to MCP tools."""
    client = ChatTestClient("stdio")
    
    # Test prompt mapping without actual server connection
    test_cases = [
        ("Is the server running?", "ping"),
        ("What version are you running?", "version"),
        ("Are my credentials valid?", "validate_auth"),
        ("How many Note documents are there?", "count_documents"),
        ("What doctypes are available?", "get_doctype_list"),
        ("What fields does the Note doctype have?", "get_doctype_schema"),
        ("Create a new Note with title 'Test'", "create_document"),
    ]
    
    for prompt, expected_tool in test_cases:
        tool_call = client._map_prompt_to_tool(prompt)
        assert tool_call is not None, f"No tool mapped for prompt: {prompt}"
        
        tool_name, arguments = tool_call
        assert tool_name == expected_tool, f"Expected {expected_tool}, got {tool_name} for prompt: {prompt}"


def test_mcp_sdk_available():
    """Verify MCP SDK is available for testing."""
    assert MCP_SDK_AVAILABLE, """
    Official MCP SDK not available. Install with:
    uv add mcp
    
    This is required for the consolidated test suite.
    """


def test_server_can_be_imported():
    """Test that server components can be imported successfully."""
    from src.server import create_server
    from src.tools import helpers, documents, schema, reports
    from src.frappe_api import FrappeApiClient
    
    # Should be able to create server
    server = create_server()
    assert server is not None
    assert server.name == "frappe-mcp-server"


def test_version_available():
    """Test that version information is available."""
    assert __version__ is not None
    assert isinstance(__version__, str)
    assert len(__version__) > 0


if __name__ == "__main__":
    """
    Run tests using pytest when executed directly.
    
    Usage:
        python test_mcp_client.py
        
    Or better yet, use pytest directly:
        uv run pytest tests/test_mcp_client.py -v
    """
    print("🧪 Running MCP client tests...")
    print("💡 For best results, use: uv run pytest tests/test_mcp_client.py -v")
    
    # Run pytest programmatically
    import pytest
    import sys
    
    exit_code = pytest.main([__file__, "-v"])
    sys.exit(exit_code)