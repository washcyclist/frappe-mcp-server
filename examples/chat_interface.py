#!/usr/bin/env python3
"""
Chat Interface Example for Frappe MCP Server

This example demonstrates how to integrate the Frappe MCP server
into a chat-style interface with tool calling capabilities.

Usage:
    python examples/chat_interface.py
    
Environment Variables:
    FRAPPE_API_KEY - Your Frappe API key
    FRAPPE_API_SECRET - Your Frappe API secret  
    FRAPPE_BASE_URL - Your Frappe site URL
    MCP_SERVER_PORT - Port for SSE server (default: 8080)
"""

import asyncio
import json
import os
import sys
from typing import Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from mcp.client.sse import sse_client
    from mcp.client.session import ClientSession
    OFFICIAL_MCP_AVAILABLE = True
except ImportError:
    OFFICIAL_MCP_AVAILABLE = False
    print("⚠️  Official MCP SDK not available. Install with: uv add mcp")


@dataclass
class ChatMessage:
    """Represents a chat message."""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = None
    tool_calls: List[Dict[str, Any]] = None
    tool_results: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.tool_calls is None:
            self.tool_calls = []
        if self.tool_results is None:
            self.tool_results = []


class FrappeChatInterface:
    """Chat interface that can call Frappe MCP tools."""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.session = None
        self.available_tools = {}
        self.conversation_history = []
        
    async def connect(self):
        """Connect to the Frappe MCP server."""
        print(f"🔗 Connecting to Frappe MCP server at {self.server_url}")
        
        if not OFFICIAL_MCP_AVAILABLE:
            print("❌ Official MCP SDK required. Install with: uv add mcp")
            return False
            
        try:
            self.client_context = sse_client(
                url=self.server_url,
                timeout=10,
                sse_read_timeout=60
            )
            
            self.streams = await self.client_context.__aenter__()
            read_stream, write_stream = self.streams
            
            self.session = ClientSession(read_stream, write_stream)
            await self.session.__aenter__()
            
            # Initialize MCP connection
            await self.session.initialize()
            
            # Load available tools
            await self._load_tools()
            
            print(f"✅ Connected! {len(self.available_tools)} tools available")
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self.session:
            await self.session.__aexit__(None, None, None)
        if hasattr(self, 'client_context'):
            await self.client_context.__aexit__(None, None, None)
    
    async def _load_tools(self):
        """Load available tools from the server."""
        try:
            result = await self.session.list_tools()
            self.available_tools = {}
            
            for tool in result.tools:
                self.available_tools[tool.name] = {
                    'description': tool.description,
                    'inputSchema': tool.inputSchema
                }
                
        except Exception as e:
            print(f"⚠️  Could not load tools: {e}")
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names."""
        return list(self.available_tools.keys())
    
    def show_tool_help(self, tool_name: str = None):
        """Show help for tools."""
        if tool_name:
            if tool_name in self.available_tools:
                tool = self.available_tools[tool_name]
                print(f"\n🔧 {tool_name}")
                print(f"Description: {tool['description']}")
                if tool.get('inputSchema'):
                    print(f"Input Schema: {json.dumps(tool['inputSchema'], indent=2)}")
            else:
                print(f"❌ Tool '{tool_name}' not found")
        else:
            print("\\n📋 Available Frappe Tools:")
            for name, tool in self.available_tools.items():
                print(f"  • {name} - {tool['description']}")
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call a specific tool and return the result."""
        if tool_name not in self.available_tools:
            return {"error": f"Tool '{tool_name}' not available"}
        
        try:
            result = await self.session.call_tool(tool_name, arguments or {})
            
            # Extract text content from result
            content = []
            if hasattr(result, 'content'):
                for item in result.content:
                    if hasattr(item, 'text'):
                        content.append(item.text)
                    else:
                        content.append(str(item))
            
            return {
                "success": True,
                "tool": tool_name,
                "arguments": arguments,
                "content": content
            }
            
        except Exception as e:
            return {
                "success": False,
                "tool": tool_name,
                "arguments": arguments,
                "error": str(e)
            }
    
    async def process_message(self, user_input: str) -> ChatMessage:
        """Process a user message and determine if tools should be called."""
        
        # Add user message to history
        user_msg = ChatMessage(role="user", content=user_input)
        self.conversation_history.append(user_msg)
        
        # Simple tool detection (in a real app, you'd use an LLM here)
        response_content = ""
        tool_calls = []
        tool_results = []
        
        # Check for direct tool commands
        if user_input.startswith("/"):
            await self._handle_command(user_input, tool_calls, tool_results)
            response_content = "Command executed."
        
        # Check for tool-related keywords
        elif any(keyword in user_input.lower() for keyword in ["count", "list", "show", "get"]):
            # Try to extract tool calls from natural language
            suggested_tools = await self._suggest_tools(user_input)
            if suggested_tools:
                response_content += f"I can help with that using these tools: {', '.join(suggested_tools)}\\n"
                response_content += "Use /call <tool_name> [arguments] to execute."
        
        else:
            response_content = "I'm a Frappe assistant. I can help you with Frappe operations. "
            response_content += "Try asking me to count documents, list data, or use /help for commands."
        
        # Create assistant response
        assistant_msg = ChatMessage(
            role="assistant", 
            content=response_content,
            tool_calls=tool_calls,
            tool_results=tool_results
        )
        self.conversation_history.append(assistant_msg)
        
        return assistant_msg
    
    async def _handle_command(self, command: str, tool_calls: List, tool_results: List):
        """Handle slash commands."""
        parts = command[1:].split()
        cmd = parts[0] if parts else ""
        
        if cmd == "help":
            self.show_tool_help()
            
        elif cmd == "tools":
            print(f"Available tools: {', '.join(self.get_available_tools())}")
            
        elif cmd == "call" and len(parts) >= 2:
            tool_name = parts[1]
            arguments = {}
            
            # Parse arguments if provided
            if len(parts) > 2:
                try:
                    arguments = json.loads(' '.join(parts[2:]))
                except json.JSONDecodeError:
                    print("❌ Invalid arguments format (expected JSON)")
                    return
            
            # Call the tool
            result = await self.call_tool(tool_name, arguments)
            tool_calls.append({"tool": tool_name, "arguments": arguments})
            tool_results.append(result)
            
            # Display result
            if result.get("success"):
                print(f"\\n🔧 Tool Result from '{tool_name}':")
                for content in result["content"]:
                    print(content)
            else:
                print(f"❌ Tool '{tool_name}' failed: {result.get('error')}")
                
        elif cmd == "info" and len(parts) >= 2:
            tool_name = parts[1]
            self.show_tool_help(tool_name)
            
        else:
            print("Available commands:")
            print("  /help - Show available tools")
            print("  /tools - List tool names") 
            print("  /call <tool> [args] - Call a tool")
            print("  /info <tool> - Show tool details")
    
    async def _suggest_tools(self, user_input: str) -> List[str]:
        """Suggest relevant tools based on user input."""
        suggestions = []
        input_lower = user_input.lower()
        
        # Simple keyword matching
        if "count" in input_lower:
            suggestions.append("count_documents")
        if "list" in input_lower:
            suggestions.extend(["list_documents", "list_reports", "get_doctype_list"])
        if "ping" in input_lower:
            suggestions.append("ping")
        if "version" in input_lower:
            suggestions.append("version")
        
        return [tool for tool in suggestions if tool in self.available_tools]
    
    def show_conversation(self):
        """Display the conversation history."""
        print("\\n💬 Conversation History:")
        for msg in self.conversation_history[-5:]:  # Show last 5 messages
            timestamp = msg.timestamp.strftime("%H:%M")
            if msg.role == "user":
                print(f"[{timestamp}] 👤 You: {msg.content}")
            else:
                print(f"[{timestamp}] 🤖 Assistant: {msg.content}")
                if msg.tool_calls:
                    print(f"       🔧 Used tools: {[call['tool'] for call in msg.tool_calls]}")


async def main():
    """Main chat interface loop."""
    # Configuration
    port = os.getenv("MCP_SERVER_PORT", "8080")
    server_url = f"http://localhost:{port}/sse"
    
    print("🤖 Frappe Chat Interface")
    print("=" * 50)
    print(f"Server URL: {server_url}")
    
    # Check environment
    if not all([os.getenv("FRAPPE_API_KEY"), os.getenv("FRAPPE_API_SECRET"), os.getenv("FRAPPE_BASE_URL")]):
        print("⚠️  Warning: Frappe credentials not set. Some tools may fail.")
        print("   Set FRAPPE_API_KEY, FRAPPE_API_SECRET, and FRAPPE_BASE_URL")
    
    # Start chat interface
    chat = FrappeChatInterface(server_url)
    
    if not await chat.connect():
        print("❌ Could not connect to Frappe MCP server.")
        print("   Make sure the server is running with:")
        print(f"   uvx frappe-mcp-server --transport sse --port {port}")
        return
    
    try:
        print("\\n🎯 Chat Interface Ready!")
        print("Type your questions or use /help for commands")
        print("Type 'quit' to exit\\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                    
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    break
                
                if user_input == '/history':
                    chat.show_conversation()
                    continue
                
                # Process the message
                response = await chat.process_message(user_input)
                print(f"🤖 Assistant: {response.content}")
                
            except KeyboardInterrupt:
                print("\\n\\n👋 Goodbye!")
                break
            except EOFError:
                break
                
    finally:
        await chat.disconnect()


if __name__ == "__main__":
    asyncio.run(main())