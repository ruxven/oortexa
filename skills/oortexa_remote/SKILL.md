# OORTExA Remote Skill
This skill enables remote development via an MCP server.

## Overview
OORTExA is exposed via a single MCP tool: `ask_oortexa`.
This tool allows you to perform operations on the remote environment provided by the MCP.

## Tool Usage: `ask_oortexa`

### Parameters
- `action`: The operation to perform.
- `payload`: Data or command string for the action.
- `path`: File or directory path (optional for some actions).
- `offset`: Line number to start reading from (optional).
- `limit`: Number of lines to read (optional).

### Valid Actions
- `bash`: Run a shell command. Use `payload` for the command string.
- `ls`: List files. Use `path`.
- `read`: Read a file. Use `path`, with optional `offset` and `limit`.
- `write`: Write to a file. Use `path` and `payload` for content.
- `grep`: Search content. Use `payload` for pattern and `path` for location.
- `glob`: Find files. Use `payload` for the glob pattern.
- `status`: Show current environment status (active target, config path).

### Examples
- **Check environment:** `ask_oortexa(action="bash", payload="uname -a")`
- **List directory:** `ask_oortexa(action="ls", path="src")`
- **Search for configs:** `ask_oortexa(action="glob", payload="**/*.conf")`
- **Read file segment:** `ask_oortexa(action="read", path="main.c", offset=1, limit=50)`
- **Write content:** `ask_oortexa(action="write", path="notes.txt", payload="Internal draft")`
- **Check Status:** `ask_oortexa(action="status")`

### Valid Actions
- `bash`: Run a shell command. Use `payload` for the command string.
- `ls`: List files. Use `path`.
- `read`: Read a file. Use `path`, with optional `offset` and `limit`.
- `write`: Write to a file. Use `path` and `payload` for content.
- `grep`: Search content. Use `payload` for pattern and `path` for location.
- `glob`: Find files. Use `payload` for the glob pattern.

### Examples
- **Check environment:** `ask_oortexa(action="bash", payload="uname -a")`
- **Search for configs:** `ask_oortexa(action="glob", payload="**/*.conf")`
