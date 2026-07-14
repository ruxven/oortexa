import os
import subprocess
import shlex
import yaml
from io import StringIO
from typing import Annotated, Literal, Optional, Protocol, Dict, Any
from langchain_core.tools import tool
from fabric import Connection
import logging

_logger = logging.getLogger("oortexa")

class Target(Protocol):
    def run(self, cmd: str, input_data: Optional[str] = None) -> Dict[str, Any]:
        ...

class BaseTarget:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        # Use the relative path from the config root if it's not an absolute path inside the container
        self.script_path = config.get("script")
        self.basedir = config.get("basedir")

    def _prepare_cmd(self, cmd: str) -> str:
        # If cmd is 'make' and a script is defined, prioritize the script.
        # This allows polymorphic behavior where build_project() invokes the script.
        if cmd == "make" and self.script_path:
            return f"bash {self.script_path}"
        return cmd

class LocalTarget(BaseTarget):
    def run(self, cmd: str, input_data: Optional[str] = None) -> Dict[str, Any]:
        exec_cmd = self._prepare_cmd(cmd)
        full_cmd = ["bash", "-c", exec_cmd]
        
        # Ensure basedir exists locally before running subprocess, or default to None
        cwd = self.basedir
        if cwd and not os.path.isabs(cwd):
            # If relative, it's relative to the app's current directory
            cwd = os.path.abspath(cwd)
            
        _logger.debug(f"Local run: {full_cmd} (cwd: {cwd})")
        
        # If the directory doesn't exist locally (which is common for container-only paths), 
        # we shouldn't attempt to use it as the subprocess CWD.
        actual_cwd = cwd if cwd and os.path.exists(cwd) else None
        
        res = subprocess.run(full_cmd, input=input_data, capture_output=True, text=True, cwd=actual_cwd)
        return {"stdout": res.stdout, "stderr": res.stderr, "exit_code": res.returncode}

class SSHTarget(BaseTarget):
    def run(self, cmd: str, input_data: Optional[str] = None) -> Dict[str, Any]:
        exec_cmd = self._prepare_cmd(cmd)
        if self.basedir:
            exec_cmd = f"cd {self.basedir} && {exec_cmd}"
        
        ssh_cfg = self.config.get("ssh", {})
        conn = ToolContext._get_ssh_connection(ssh_cfg)
        _logger.debug(f"SSH run: {exec_cmd}")
        res = conn.run(exec_cmd, hide=True, warn=True, in_stream=StringIO(input_data) if input_data else None)
        return {"stdout": res.stdout, "stderr": res.stderr, "exit_code": res.exited}

class ContainerWrapper:
    def __init__(self, inner: Target, config: Dict[str, Any]):
        self.inner = inner
        self.config = config # store full config for base path access
        self.cfg = config.get("container", {})
        self.c_tool = self.cfg.get("tool", config.get("tool", "podman"))
        self.c_name = self.cfg.get("name", "oortexa-worker")
        self.c_mode = self.cfg.get("mode", "exec")
        self.c_image = self.cfg.get("image", "fedora:latest")
        self.c_args = self.cfg.get("args", [])

    def run(self, cmd: str, input_data: Optional[str] = None) -> Dict[str, Any]:
        # Perform script replacement BEFORE wrapping.
        # This ensures that if cmd='make' and script='./build.sh', we wrap 'bash ./build.sh'
        if cmd == "make" and self.config.get("script"):
            exec_cmd = f"bash {self.config.get('script')}"
        else:
            exec_cmd = cmd

        target_ref = self.c_name if self.c_mode == "exec" else self.c_image
        wrapped_cmd = f"{self.c_tool} {self.c_mode} {' '.join(self.c_args)} {target_ref} bash -c {shlex.quote(exec_cmd)}"
        return self.inner.run(wrapped_cmd, input_data)

class ComposeWrapper:
    def __init__(self, inner: Target, config: Dict[str, Any]):
        self.inner = inner
        self.config = config
        self.tool = config.get("tool", "docker-compose")
        self.mode = config.get("container", {}).get("mode", "exec")
        self.service = config.get("service")
        compose_file = config.get("file")
        self.prefix = f"{self.tool} -f {compose_file}" if compose_file else self.tool

    def run(self, cmd: str, input_data: Optional[str] = None) -> Dict[str, Any]:
        if cmd == "make" and self.config.get("script"):
            exec_cmd = f"bash {self.config.get('script')}"
        else:
            exec_cmd = cmd

        wrapped = f"{self.prefix} {self.mode} {self.service} bash -c {shlex.quote(exec_cmd)}"
        return self.inner.run(wrapped, input_data)

class ToolContext:
    _config = {}
    _ssh_connections: dict = {}
    _target_cache: Optional[Target] = None

    @classmethod
    def load_config(cls, config_path: str = None):
        cls._target_cache = None
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
    def get_target(cls) -> Target:
        if cls._target_cache:
            return cls._target_cache

        active = os.environ.get("OORTEXA_TARGET", cls._config.get("active_target", "local"))
        targets = cls._config.get("targets", {})
        cfg = targets.get(active, cls._config.get("target", {"type": "local"}))
        
        t_type = cfg.get("type", "local")
        
        # Transport
        if t_type.startswith("ssh"):
            base = SSHTarget(cfg)
        else:
            base = LocalTarget(cfg)

        # Execution Layer
        if "container" in t_type or t_type == "container":
            cls._target_cache = ContainerWrapper(base, cfg)
        elif "compose" in t_type or t_type == "compose":
            cls._target_cache = ComposeWrapper(base, cfg)
        else:
            cls._target_cache = base
            
        return cls._target_cache

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
    target = ToolContext.get_target()
    return target.run(cmd, input_data)

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
