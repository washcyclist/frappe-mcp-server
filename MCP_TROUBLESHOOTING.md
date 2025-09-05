# MCP Server Configuration Troubleshooting

## Problem Description

The Frappe MCP server is properly configured in the project's `.mcp.json` file but Claude Code consistently ignores this configuration on startup, requiring manual reconnection each time Claude restarts.

## Current Configuration

### Project MCP Configuration (`.mcp.json`)
```json
{
  "mcpServers": {
    "frappe-mcp-server": {
      "type": "sse",
      "url": "http://127.0.0.1:8000/sse"
    }
  }
}
```

### MCP Config Hierarchy
According to `claude mcp` output:
- User config: `/Users/geordie/.claude.json` (global)
- **Project config: `/Volumes/Berthold/Code/tools/mcp/frappe_mcp_server_uv/.mcp.json`** ← Should be automatically loaded
- Local config: `/Users/geordie/.claude.json [project: ...]` (private)

## Expected Behavior

1. Claude should automatically discover and connect to MCP servers defined in project `.mcp.json`
2. The frappe-mcp-server should appear in the MCP server list alongside playwright
3. Connection should persist across Claude restarts without manual intervention

## Actual Behavior

1. ✅ Only playwright MCP server shows as connected
2. ❌ frappe-mcp-server is completely ignored despite being in `.mcp.json`
3. ❌ Must manually reconfigure after every Claude restart
4. ❌ Lose all conversation context when forced to restart Claude for MCP debugging

## Troubleshooting Steps Attempted

- [x] Verified `.mcp.json` exists in project root
- [x] Verified JSON syntax is valid
- [x] Confirmed server runs successfully on http://127.0.0.1:8000/sse
- [x] Used `claude mcp` command to create initial configuration
- [ ] Checked Claude Code logs for MCP discovery errors
- [ ] Tested with stdio transport instead of SSE
- [ ] Verified environment variables are accessible to Claude

## Potential Root Causes

1. **SSE Transport Issues**: Claude might have problems with SSE-based MCP servers
2. **URL Resolution**: localhost/127.0.0.1 might not be accessible from Claude's context
3. **Race Condition**: Server might not be running when Claude attempts connection
4. **Permission Issues**: Claude might lack permissions to access local HTTP servers
5. **Configuration Parsing**: Bug in Claude's `.mcp.json` parser for project-scoped configs

## Next Investigation Steps

1. Check if stdio transport works instead of SSE
2. Try different URL formats (localhost vs 127.0.0.1)
3. Add logging to server startup to see if Claude attempts connection
4. Test with a minimal MCP server to isolate the issue
5. Compare working playwright config vs frappe-mcp-server config

## Workaround

Currently requires manual MCP server management through `claude mcp` command after each restart, causing complete loss of conversation context.

## Impact

- **High**: Forces frequent Claude restarts during development
- **High**: Complete loss of conversation context and debugging progress
- **Medium**: Inefficient development workflow
- **Medium**: Unable to maintain debugging state across sessions