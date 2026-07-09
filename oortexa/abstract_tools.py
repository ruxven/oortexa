import os
import subprocess
import shlex
import yaml
from io import StringIO
from typing import Annotated, Literal, Optional
from langchain_core.tools import tool
from fabric import Connection
import logging

_logger = logging.getLogger("oortexa")

class ToolContext:
    _config = {}
    _ssh_connections: dict = {}

    @classmethod
    def load_config(cls, config_path: str = None):
        if not config_path:
            config_path = os.environ.get("OORTEXA_CONFIG", "config.yaml")

        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    cls._config = yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise ValueError(f"Failed to parse config file {config_path}: {e}")
        else:
            cls._config = {"active_target": "local", "targets": {"local": {"type": "local"}}}

    @classmethod
    def get_target_config(cls):
        active = os.environ.get("OORTEXA_TARGET", cls._config.get("active_target", "local"))
        targets = cls._config.get("targets", {})

        if "target" in cls._config:
            return cls._config["target"]

        return targets.get(active, {"type": "local"})

    @classmethod
    def _get_ssh_connection(cls, ssh_cfg: dict) -> Connection:
        host = ssh_cfg.get("host", "localhost")
        user = ssh_cfg.get("user")
        port = ssh_cfg.get("port", 22)
        identity = ssh_cfg.get("identity")

        connect_kwargs = {}
        if identity:
            connect_kwargs["key_filename"] = os.path.expanduser(identity)

        key = (host, user, port, identity)

        if key not in cls._ssh_connections:
            conn = Connection(
                host=host,
                user=user,
                port=port,
                connect_kwargs=connect_kwargs,
            )
            conn.open()
            cls._ssh_connections[key] = conn

        return cls._ssh_connections[key]

    @classmethod
    def close_ssh_connections(cls):
        for conn in cls._ssh_connections.values():
            try:
                conn.close()
            except Exception:
                pass
        cls._ssh_connections.clear()


def _run_cmd(cmd: str, input_data: str = None):
    _logger.debug(f"_run_cmd cmd: {cmd}")
    cfg = ToolContext.get_target_config()
    target_type = cfg.get("type", "local")

    # Common SSH settings
    ssh_cfg = cfg.get("ssh", {})

    # Common Container settings
    container_cfg = cfg.get("container", {})
    c_tool = container_cfg.get("tool", cfg.get("tool", "podman"))
    c_name = container_cfg.get("name", "oortexa-worker")
    c_mode = container_cfg.get("mode", "exec")
    c_image = container_cfg.get("image", "fedora:latest")
    c_args = container_cfg.get("args", [])

    # Working directory for any target
    basedir = container_cfg.get("basedir") or cfg.get("basedir", "./")

    # Compose specific settings
    compose_tool = cfg.get("tool", "docker-compose")
    compose_service = cfg.get("service")
    compose_file = cfg.get("file")
    compose_args = [f"-f {compose_file}"] if compose_file else []

    # --- SSH-based targets (persistent Fabric connections) ---
    if target_type in ("ssh", "ssh+container", "ssh+script"):
        conn = ToolContext._get_ssh_connection(ssh_cfg)

        if target_type == "ssh":
            inner_cmd = cmd
        elif target_type == "ssh+container":
            target_ref = c_name if c_mode == "exec" else c_image
            inner_cmd = (
                f"{c_tool} {c_mode} {' '.join(c_args)} {target_ref} "
                f"bash -c {shlex.quote(cmd)}"
            )
        elif target_type == "ssh+script":
            script_path = cfg.get("script")
            cmd = script_path
            if not script_path:
                raise ValueError("Target type 'ssh+script' requires a 'script' path in config.")
            inner_cmd = f"bash {script_path} {shlex.quote(cmd)}"

        if basedir:
            inner_cmd = f"cd {basedir};" + inner_cmd

        kwargs = {"hide": True, "warn": True}
        if input_data is not None:
            kwargs["in_stream"] = StringIO(input_data)

        _logger.debug(f"inner_cmd: {inner_cmd}")
        result = conn.run(inner_cmd, **kwargs)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exited,
        }

    # --- Subprocess-based targets (local, container, compose, script) ---
    if target_type == "local":
        full_cmd = ["bash", "-c", cmd]
    elif target_type == "container":
        target_ref = c_name if c_mode == "exec" else c_image
        full_cmd = [c_tool, c_mode] + c_args + [target_ref, "bash", "-c", cmd]
    elif target_type == "compose":
        full_cmd = [compose_tool] + compose_args + [c_mode, compose_service, "bash", "-c", cmd]
    elif target_type == "script":
        script_path = cfg.get("script")
        if not script_path:
            raise ValueError("Target type 'script' requires a 'script' path in config.")
        full_cmd = ["cd", basedir, "bash", script_path]
    else:
        raise ValueError(f"Unknown target type: {target_type}")

    _logger.debug(f"full_cmd: {full_cmd}")
    result = subprocess.run(full_cmd, input=input_data, capture_output=True, text=True, cwd=basedir)
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.returncode,
    }

@tool
def read_file(path: str):
    """Read a file from the target project environment."""
    return _run_cmd(f"cat {shlex.quote(path)}")

@tool
def write_file(path: str, content: str):
    """Write or overwrite a file in the target project environment."""
    cmd = f"python3 -c 'import sys; open(sys.argv[1], \"w\").write(sys.stdin.read())' {shlex.quote(path)}"
    res = _run_cmd(cmd, input_data=content)
    return {
        "success": res["exit_code"] == 0,
        "stderr": res["stderr"]
    }

@tool
def list_files(path: str = "."):
    """List files in the target project directory."""
    return _run_cmd(f"ls -F {shlex.quote(path)}")

@tool
def build_project(command: str = "make"):
    """Run a build command (like make, npm build, etc) in the project environment."""
    return _run_cmd(command)

abstract_tools = [read_file, write_file, list_files, build_project]
