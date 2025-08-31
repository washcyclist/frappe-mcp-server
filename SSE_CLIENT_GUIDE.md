# SSE Client Implementation Guide

## Why I Didn't Use the Official MCP SDK Initially

You asked an excellent question about why I created a custom SSE client instead of using the official MCP SDK. Here's the complete picture:

### The Discovery

**The official MCP Python SDK DOES support SSE transport!** 🎉

I initially created a custom client because:
1. **Documentation Gap**: The official MCP docs don't prominently feature SSE client examples
2. **Testing Focus**: I wanted to quickly validate our server's SSE transport was working
3. **Learning Process**: Building a custom client helped understand the MCP protocol better

### Official MCP SDK vs FastMCP vs Custom Clients

## 🏢 **Official MCP SDK** (Recommended for Production)

**Pros:**
- ✅ Full MCP protocol compliance
- ✅ Proper session management and lifecycle
- ✅ Built-in authentication (OAuth, etc.)
- ✅ Error handling and reconnection logic
- ✅ Type safety with Pydantic models
- ✅ Supports stdio, SSE, and StreamableHTTP transports

**Cons:**
- ❌ More complex setup for simple use cases
- ❌ Heavier dependency footprint
- ❌ Less documentation/examples for SSE specifically

**Installation:**
```bash
uv add mcp
# or
pip install mcp
```

**Example Usage:**
```python
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def use_official_client():
    async with sse_client(
        url="http://localhost:8000/sse",
        timeout=10
    ) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            
            # List tools
            tools_result = await session.list_tools()
            
            # Call tool
            result = await session.call_tool("ping", {})
            print(result.content[0].text)
```

## ⚡ **FastMCP** (Server-Side Framework)

**What it is:**
- Server-side framework for building MCP servers quickly
- Used by our Frappe MCP server
- Not a client library

**Key Features:**
- Rapid server development
- Built-in transport handling (stdio, SSE)
- Decorator-based tool registration
- Auto-generated documentation

## 🛠️ **Custom SSE Client** (Educational/Testing)

**When to use:**
- Learning the MCP protocol
- Quick testing and validation
- Minimal dependency requirements
- Custom integration needs

**Our Implementation:**
```python
class MCPSSEClient:
    async def send_request(self, method: str, params: dict = None):
        request_data = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": method,
            "params": params or {}
        }
        
        response = await self.client.post(
            self.base_url,
            json=request_data,
            headers={"Content-Type": "application/json"}
        )
        return response.json()
```

## 🚀 **For Chat Interface Integration**

### Best Approach: Official MCP SDK

```python
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

class ChatBot:
    async def connect_to_mcp_server(self, server_url: str):
        self.client_context = sse_client(url=server_url)
        self.streams = await self.client_context.__aenter__()
        read_stream, write_stream = self.streams
        
        self.session = ClientSession(read_stream, write_stream)
        await self.session.__aenter__()
        await self.session.initialize()
    
    async def call_mcp_tool(self, tool_name: str, args: dict):
        result = await self.session.call_tool(tool_name, args)
        return result.content[0].text
```

### Integration with LLM Frameworks

**LangChain Integration:**
```python
from langchain.tools import Tool
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def create_langchain_tools_from_mcp(server_url: str):
    async with sse_client(url=server_url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            
            langchain_tools = []
            for mcp_tool in tools_result.tools:
                def create_tool_func(tool_name):
                    async def tool_func(args_str: str):
                        args = json.loads(args_str) if args_str else {}
                        result = await session.call_tool(tool_name, args)
                        return result.content[0].text
                    return tool_func
                
                langchain_tools.append(Tool(
                    name=mcp_tool.name,
                    description=mcp_tool.description,
                    func=create_tool_func(mcp_tool.name)
                ))
            
            return langchain_tools
```

**OpenAI Assistant Integration:**
```python
import openai
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

class OpenAIWithMCP:
    def __init__(self, mcp_server_url: str):
        self.mcp_server_url = mcp_server_url
        self.session = None
    
    async def setup_mcp(self):
        self.client_context = sse_client(url=self.mcp_server_url)
        self.streams = await self.client_context.__aenter__()
        read_stream, write_stream = self.streams
        
        self.session = ClientSession(read_stream, write_stream)
        await self.session.__aenter__()
        await self.session.initialize()
    
    async def chat_with_tools(self, user_message: str):
        # Get available MCP tools
        tools_result = await self.session.list_tools()
        
        # Convert to OpenAI function calling format
        functions = []
        for tool in tools_result.tools:
            functions.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema or {}
                }
            })
        
        # Call OpenAI with available functions
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[{"role": "user", "content": user_message}],
            tools=functions
        )
        
        # Handle function calls
        if response.choices[0].message.tool_calls:
            for tool_call in response.choices[0].message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                # Call MCP tool
                result = await self.session.call_tool(function_name, function_args)
                # Process result...
        
        return response.choices[0].message.content
```

## 🎯 **Recommendations**

### For Production Applications:
1. **Use Official MCP SDK** - Full protocol support and proper session management
2. **SSE Transport** - Better for web applications and scalable architectures
3. **Proper Error Handling** - Handle auth failures, connection drops, timeouts

### For Learning/Testing:
1. **Custom Clients** - Great for understanding the protocol
2. **FastMCP for Servers** - Rapid development and testing
3. **Our Test Suite** - Examples of both approaches

### For Chat Interfaces:
1. **Official SDK + Session Management** - Persistent connections
2. **Tool Discovery** - Dynamic tool loading from MCP servers
3. **LLM Integration** - Convert MCP tools to LLM function calling

## 📊 **Transport Comparison**

| Transport | Use Case | Pros | Cons |
|-----------|----------|------|------|
| stdio | CLI tools, Claude Code | Simple, direct | Single connection |
| SSE | Web apps, chat interfaces | HTTP-based, scalable | Persistent connection |
| StreamableHTTP | Serverless, REST APIs | Stateless, cloud-friendly | More complex |

## 🔧 **Testing Your Implementation**

### Test Official MCP Client:
```bash
# Install MCP SDK
uv add mcp

# Run official client test
uv run pytest tests/test_official_mcp_sse_client.py -v

# Run chat interface example  
FRAPPE_API_KEY=your-key FRAPPE_API_SECRET=your-secret FRAPPE_BASE_URL=your-url \\
python examples/chat_interface.py
```

### Start Your Server:
```bash
# Start with SSE transport
uvx frappe-mcp-server --transport sse --port 8080
```

## ✅ **Final Answer to Your Question**

**Why didn't I use the official MCP SDK initially?**
- I should have! The official SDK has excellent SSE support
- My custom client was for quick testing and learning
- The official SDK is definitely the right choice for production

**For embedding in your chat interface:**
- Use `mcp.client.sse.sse_client` and `mcp.client.session.ClientSession`
- The official SDK handles protocol complexities properly
- Perfect for LLM integration with function calling

The official MCP SDK is mature, well-designed, and the right choice for production applications! 🚀