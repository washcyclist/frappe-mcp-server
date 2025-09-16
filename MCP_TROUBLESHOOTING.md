# MCP Server Configuration Troubleshooting

## Problem Description

The Frappe MCP server is properly configured in the project's `.mcp.json` file but Claude Code consistently ignores this configuration on startup, requiring manual reconnection each time Claude restarts.

## Current Configuration

### User-Level MCP Configuration (`~/.config/claude-code/mcp_servers.json`)
**CURRENT (Updated for SSE daemon connection):**
```json
{
  "frappe-mcp-server": {
    "url": "http://localhost:8069/sse",
    "env": {
      "FRAPPE_API_KEY": "ff09790d111aeab",
      "FRAPPE_API_SECRET": "226fc3b57acb830",
      "FRAPPE_BASE_URL": "https://epinomy.com",
      "PYTHONUNBUFFERED": "1",
      "PYTHONDONTWRITEBYTECODE": "1",
      "LOG_LEVEL": "INFO"
    }
  }
}
```

**PREVIOUS (stdio transport - launches new instances):**
```json
{
  "frappe-mcp-server": {
    "command": "uv",
    "args": ["run", "python", "-m", "src.main"],
    "cwd": "/Volumes/Berthold/Code/tools/mcp/frappe_mcp_server_uv",
    "env": {
      "FRAPPE_API_KEY": "ff09790d111aeab",
      "FRAPPE_API_SECRET": "226fc3b57acb830",
      "FRAPPE_BASE_URL": "https://epinomy.com",
      "PYTHONUNBUFFERED": "1",
      "PYTHONDONTWRITEBYTECODE": "1",
      "LOG_LEVEL": "INFO"
    }
  }
}
```

### Previous Project MCP Configuration (`.mcp.json`) - DEPRECATED
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
- [x] **NEW**: Configured Claude Code user-level MCP configuration
- [x] **NEW**: Moved from SSE transport to stdio transport with uv
- [x] **NEW**: Renamed .env to .env.gde to test credential handling
- [x] **NEW**: Created `~/.config/claude-code/mcp_servers.json` with embedded credentials
- [x] **NEW**: Configured server as macOS system service for persistent operation
- [ ] Checked Claude Code logs for MCP discovery errors
- [ ] Verified environment variables are accessible to Claude

## Potential Root Causes

1. **SSE Transport Issues**: Claude might have problems with SSE-based MCP servers
2. **URL Resolution**: localhost/127.0.0.1 might not be accessible from Claude's context
3. **Race Condition**: Server might not be running when Claude attempts connection
4. **Permission Issues**: Claude might lack permissions to access local HTTP servers
5. **Configuration Parsing**: Bug in Claude's `.mcp.json` parser for project-scoped configs

## Current Status (Latest Debugging Session)

**Daemon Discovery**: Identified that a Frappe MCP server is already running as macOS daemon on localhost:8069/sse
- Confirmed SSE server responds properly with `curl -v http://localhost:8069/sse`
- Server returns proper SSE headers: `content-type: text/event-stream`

**Configuration Update**: Modified MCP configuration to connect to existing daemon instead of launching new instances
- **OLD**: Used `command` + `args` to launch stdio transport via uv
- **NEW**: Using `url: "http://localhost:8069/sse"` to connect to running daemon
- **IMPORTANT**: Kept environment variables in config since daemon won't have credentials

**Transport Migration**: Successfully migrated from stdio transport back to SSE transport, but connecting to existing daemon rather than launching new server.

**Credential Management**: 
- Renamed `.env` to `.env.gde` to test server behavior without local env file
- Server starts successfully without .env file (version 0.2.0 confirmed)
- Credentials now passed through MCP protocol via `env` section in client config

**Service Configuration**:
- Server configured as macOS system service for persistent operation
- Service restart requires manual intervention: `sudo launchctl stop/start com.frappe.mcp.server`

## Next Investigation Steps

1. ✅ ~~Check if stdio transport works instead of SSE~~ - **COMPLETED**: Configured stdio transport via uv
2. ✅ ~~Try different URL formats (localhost vs 127.0.0.1)~~ - **COMPLETED**: Identified daemon on localhost:8069
3. ✅ ~~Identify if daemon server is already running~~ - **COMPLETED**: Found SSE server on port 8069
4. ✅ ~~Update configuration to connect to daemon instead of launching new instance~~ - **COMPLETED**: Updated to use `url` field
5. **CURRENT**: Test if Claude Code recognizes the SSE daemon connection after restart
6. **PENDING**: Verify credential passing through MCP protocol to daemon
7. **PENDING**: Add logging to server to confirm Claude connection attempts

## Workaround

Currently requires manual MCP server management through `claude mcp` command after each restart, causing complete loss of conversation context.

## Impact

- **High**: Forces frequent Claude restarts during development
- **High**: Complete loss of conversation context and debugging progress
- **Medium**: Inefficient development workflow
- **Medium**: Unable to maintain debugging state across sessions