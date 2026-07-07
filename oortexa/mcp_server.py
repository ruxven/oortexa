"""
Custom MCP Server implementation for SSH and Podman execution.
This provides the bridge to execute commands inside containers or remote hosts.
"""

from mcp.server.fastmcp import FastMCP
import subprocess
import shlex

mcp = FastMCP("ContainerExecutor")

@mcp.tool()
def podman_exec(container_name: str, command: str) -> str:
    """Execute a command inside a podman container."""
    try:
        full_cmd = ["podman", "exec", container_name] + shlex.split(command)
        result = subprocess.run(full_cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error executing command: {e.stderr}"

@mcp.tool()
def ssh_exec(host: str, command: str) -> str:
    """Execute a command on a remote host via SSH."""
    try:
        full_cmd = ["ssh", host, command]
        result = subprocess.run(full_cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"SSH Error: {e.stderr}"

if __name__ == "__main__":
    mcp.run()
