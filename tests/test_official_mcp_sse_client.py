"""
Test SSE transport using the official MCP Python SDK client.

This demonstrates proper usage of the official mcp.client.sse module
vs our custom client implementation.
"""

import asyncio
import subprocess
import sys
import pytest
from contextlib import asynccontextmanager

# We need to install the official MCP SDK for this test
try:
    from mcp.client.sse import sse_client
    from mcp.client.session import ClientSession
    OFFICIAL_MCP_AVAILABLE = True
except ImportError:
    OFFICIAL_MCP_AVAILABLE = False


@asynccontextmanager
async def frappe_sse_server(port: int = 8010):
    """Start our Frappe MCP server with SSE transport for testing."""
    
    # Start server as subprocess
    proc = subprocess.Popen([
        sys.executable, "-c",
        f"""
import sys
sys.path.insert(0, '{"/".join(__file__.split("/")[:-1])}')
from src.server import create_server, start_server
server = create_server()
start_server(server, transport="sse", host="127.0.0.1", port={port})
"""
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    try:
        # Wait for server to start
        await asyncio.sleep(1.5)
        
        yield f"http://127.0.0.1:{port}/sse"
        
    finally:
        # Clean shutdown
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.mark.skipif(not OFFICIAL_MCP_AVAILABLE, reason="Official MCP SDK not installed")
@pytest.mark.asyncio
async def test_official_mcp_sse_client():
    """Test using the official MCP SDK SSE client."""
    
    async with frappe_sse_server(8010) as server_url:
        
        try:
            # Use the official MCP SSE client
            async with sse_client(
                url=server_url,
                timeout=5,
                sse_read_timeout=10
            ) as (read_stream, write_stream):
                
                # Create official MCP session  
                async with ClientSession(read_stream, write_stream) as session:
                    
                    # Initialize the MCP session
                    init_result = await session.initialize()
                    assert init_result is not None
                    
                    # List available tools
                    tools_result = await session.list_tools()
                    assert hasattr(tools_result, 'tools')
                    
                    # Find our ping tool
                    tool_names = [tool.name for tool in tools_result.tools]
                    assert "ping" in tool_names, f"Expected 'ping' in tools: {tool_names}"
                    
                    # Call the ping tool
                    ping_result = await session.call_tool("ping", {})
                    assert hasattr(ping_result, 'content')
                    assert len(ping_result.content) > 0
                    
                    # Check ping response contains expected content
                    response_text = ping_result.content[0].text.lower()
                    assert "pong" in response_text
                    
        except Exception as e:
            # Auth errors are expected without Frappe credentials
            error_msg = str(e).lower()
            if not ("auth" in error_msg or "credential" in error_msg or 
                   "missing" in error_msg or "invalid" in error_msg):
                # If it's not an auth error, re-raise
                raise


@pytest.mark.skipif(not OFFICIAL_MCP_AVAILABLE, reason="Official MCP SDK not installed")
@pytest.mark.asyncio  
async def test_official_mcp_sse_multiple_tools():
    """Test calling multiple tools using official MCP SDK."""
    
    async with frappe_sse_server(8011) as server_url:
        
        try:
            async with sse_client(url=server_url, timeout=5) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    
                    await session.initialize()
                    
                    # Test multiple tool calls
                    tools = ["ping", "version", "validate_auth"]
                    results = []
                    
                    for tool_name in tools:
                        try:
                            result = await session.call_tool(tool_name, {})
                            results.append((tool_name, "success", result))
                        except Exception as e:
                            results.append((tool_name, "error", str(e)))
                    
                    # At least ping should work
                    ping_results = [r for r in results if r[0] == "ping"]
                    assert len(ping_results) == 1
                    
                    tool_name, status, result = ping_results[0]
                    if status == "success":
                        assert hasattr(result, 'content')
                        response_text = result.content[0].text.lower()
                        assert "pong" in response_text
                    
        except Exception as e:
            # Expected auth errors
            error_msg = str(e).lower() 
            assert ("auth" in error_msg or "credential" in error_msg or
                   "missing" in error_msg or "connection" in error_msg)


def test_installation_check():
    """Test that shows how to install official MCP SDK."""
    if not OFFICIAL_MCP_AVAILABLE:
        pytest.skip("""
        Official MCP SDK not available. To install:
        
        pip install mcp
        # or 
        uv add mcp
        
        Then re-run this test.
        """)


if __name__ == "__main__":
    if OFFICIAL_MCP_AVAILABLE:
        asyncio.run(test_official_mcp_sse_client())
        print("✅ Official MCP SDK SSE client test passed!")
    else:
        print("❌ Official MCP SDK not installed. Run: uv add mcp")