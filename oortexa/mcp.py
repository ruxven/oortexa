import os
import argparse
import json
import socket
import asyncio
from mcp.server.fastmcp import FastMCP, Context
from oortexa.abstract_tools import abstract_tools, ToolContext, _logger

# Shared communication settings
DAEMON_HOST = "127.0.0.1"
DAEMON_PORT = 8999


def call_daemon(tool_name: str, args: dict):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((DAEMON_HOST, DAEMON_PORT))
        payload = {"tool": tool_name, "args": args}
        s.sendall(json.dumps(payload).encode())

        response_data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            response_data += chunk

        return json.loads(response_data.decode())


# Initialize FastMCP
mcp = FastMCP("OORTExA")


@mcp.tool()
def ask_oortexa(
    action: str,
    payload: str = "",
    path: str = None,
    offset: int = None,
    limit: int = None,
    ctx: Context = None,
) -> str:
    """
    Interact with the OORTExA persistent session.

    Actions:
    - bash: Run 'payload' as a shell command.
    - ls: List files in 'path' (default '.').
    - read: Read file at 'path'. Optional 'offset' and 'limit'.
    - write: Write 'payload' to 'path'.
    - grep: Search for 'payload' (regex) in 'path'.
    - glob: Find files matching 'payload' glob.
    - status: Show current target and config path.
    """
    if action == "status":
        active = os.environ.get(
            "OORTEXA_TARGET", ToolContext._config.get("active_target", "local")
        )
        cfg_path = ToolContext._config.get("_loaded_from", "unknown")
        return f"OORTExA Status:\n- Active Target: {active}\n- Config Path: {cfg_path}\n- CWD (Local): {os.getcwd()}"

    if ctx:
        ctx.info(f"OORTExA executing action: {action}")

    tool_map = {
        "bash": "oortexa_bash",
        "ls": "oortexa_ls",
        "read": "oortexa_read",
        "write": "oortexa_write",
        "grep": "oortexa_grep",
        "glob": "oortexa_glob",
    }

    if action not in tool_map:
        return f"Unknown action: {action}. Available Actions: {list(tool_map.keys())}"

    args = {}
    if action == "bash":
        args = {"command": payload}
    elif action == "ls":
        args = {"path": path or "."}
    elif action == "read":
        args = {"path": path, "offset": offset, "limit": limit}
    elif action == "write":
        args = {"path": path, "content": payload}
    elif action == "grep":
        args = {"pattern": payload, "path": path or "."}
    elif action == "glob":
        args = {"pattern": payload}

    try:
        # Check if we are in bridge mode
        if os.environ.get("OORTEXA_BRIDGE") == "1":
            resp = call_daemon(tool_map[action], args)
            if resp.get("status") == "ok":
                result = resp.get("result")
            else:
                return f"Daemon Error: {resp.get('message')}"
        else:
            # Standard/Direct Mode
            t_name = tool_map[action]
            target_tool = next((t for t in abstract_tools if t.name == t_name), None)
            if not target_tool:
                return f"Error: Tool {t_name} not found in abstract_tools"
            result = target_tool.invoke(args)

        if isinstance(result, dict) and "stdout" in result:
            return f"STDOUT:\n{result['stdout']}\nSTDERR:\n{result['stderr']}\nEXIT CODE: {result['exit_code']}"
        return str(result)
    except ConnectionRefusedError:
        return "Error: OORTExA daemon is not running. Start it with '--daemon'."
    except Exception as e:
        return f"Unexpected error: {str(e)}"


# Daemon Logic
class ToolDaemon:
    def __init__(self, host: str = DAEMON_HOST, port: int = DAEMON_PORT):
        self.host = host
        self.port = port

    async def handle_client(self, reader, writer):
        try:
            data = await reader.read(65536)
            if not data:
                return
            request = json.loads(data.decode())
            tool_name = request.get("tool")
            args = request.get("args", {})

            target_tool = next((t for t in abstract_tools if t.name == tool_name), None)
            if not target_tool:
                response = {"status": "error", "message": f"Tool {tool_name} not found"}
            else:
                try:
                    result = target_tool.invoke(args)
                    response = {"status": "ok", "result": result}
                except Exception as e:
                    response = {"status": "error", "message": str(e)}

            writer.write(json.dumps(response).encode())
            await writer.drain()
        except Exception as e:
            _logger.error(f"Daemon handler error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def run(self):
        server = await asyncio.start_server(self.handle_client, self.host, self.port)
        print(f"OORTExA Daemon serving on {self.host}:{self.port}")
        async with server:
            await server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OORTExA Unified MCP & Daemon")
    parser.add_argument("--config", type=str, help="Path to oortexa.yml")
    parser.add_argument(
        "--daemon", action="store_true", help="Start as a persistent background daemon"
    )
    parser.add_argument(
        "--bridge",
        action="store_true",
        help="Start as a thin MCP bridge to an existing daemon",
    )
    args, unknown = parser.parse_known_args()

    config_path = args.config or os.getenv("OORTEXA_CONFIG") or "oortexa.yml"

    if args.daemon:
        if os.path.exists(config_path):
            ToolContext.load_config(config_path)

        async def run_daemon():
            daemon = ToolDaemon()
            try:
                await daemon.run()
            finally:
                ToolContext.close_ssh_connections()

        try:
            asyncio.run(run_daemon())
        except KeyboardInterrupt:
            print("\nDaemon shutting down...")
    elif args.bridge:
        os.environ["OORTEXA_BRIDGE"] = "1"
        mcp.run()
    else:
        # Standard MCP direct mode
        if os.path.exists(config_path):
            ToolContext.load_config(config_path)
        try:
            mcp.run()
        finally:
            ToolContext.close_ssh_connections()
