# OORTExA — Orchestrated Operations for Remote Tasking & Execution Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python >=3.10](https://img.shields.io/badge/python-%3E%3D3.10-blue)](pyproject.toml)

OORTExA is a Python-based execution framework for collaborative development.
It provides an abstracted toolset that moves execution to where the code lives.
Whether that's local, inside a container, or on a remote machine via SSH—while maintaining persistent sessions.

---

## Architecture

OORTExA separates execution from intelligence:

- **The Core Tools**: A set of abstracted file and shell operations (`bash`, `ls`, `read`, `write`, `grep`, `glob`) that run against a configured **Target**.
- **MCP Server**: The interface that exposes these tools to external AI agents (like `opencode` or Claude).
- **Internal Orchestrator**: A built-in LangGraph application used for setup validation and self-contained tasking using multi-role LLMs.

---

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

---

## Quickstart: Validating your Configuration

Use the internal LangGraph application to validate your environment. This self-contained orchestrator uses the `roles` and `targets` defined in your YAML to perform a "smoke test."

First, run the example setup to generate oortexa.yml

```bash
bash rc.setup_example local
```

Each of the examples contains a setup script which will ask for model information and target specific information.

Once the configuration file is generated, validate the setup via the internal LangGraph orchestrator:

```bash
bash rc.run_example local
# which will run:
python3 -m oortexa --config examples/local/oortexa.yml \
  --prompt "Build the project & report the result."
```

If debugging, do:

```bash
# Optional for viewing trace on LangSmith
export LANGSMITH_TRACING=true
export LANGSMITH_ENDPOINT=https://api.smith.langchain.com
export LANGSMITH_API_KEY=lsv2_...
export LANGSMITH_PROJECT="my_cool_project"

python3 -m oortexa --config examples/local/oortexa.yml \
  --prompt "Build the project & report the result." \
  --debug
```

---

## Production: MCP Server & Persistence

The primary way to use OORTExA is as an MCP (Model Context Protocol) server. This exposes the execution environment to external agents.

### 1. Standard Mode (OORTExA as a Tool)
For local development where persistent state between chat turns isn't critical:
```bash
python3 -m oortexa.mcp --config examples/local/oortexa.yml
```

#### Standard Mode MCP Configuration

```json
{
  "mcpServers": {
    "oortexa": {
      "command": "/usr/bin/python3",
      "args": [
        "-m",
        "oortexa.mcp",
        "--config",
        "/path/to/examples/ssh/oortexa.yml"
      ],
    }
  }
}
```

### 2. Persistent Mode (Daemon + Bridge)
Recommended for remote SSH or containerized workflows. The **Daemon** holds the connection open, while the **Bridge** handles MCP requests.

**Step 1: Start the Daemon** (manages persistence)
```bash
python3 -m oortexa.mcp --daemon --config examples/ssh/oortexa.yml
```

**Step 2: Connect the Bridge** (configured in your MCP client)
```bash
python3 -m oortexa.mcp --bridge
```

#### Persistent Mode MCP Configuration

```json
{
  "mcpServers": {
    "oortexa": {
      "command": "/usr/bin/python3",
      "args": [
        "-m",
        "oortexa.mcp",
        "--bridge"
      ],
    }
  }
}
```

---

## OORTExA Remote Skill

The skill for using the OORTExA MCP tools is located in `skills/oortexa_remote/SKILL.md` and is focused strictly on the tools the model can invoke using the MCP.

---

## Configuration Reference: `oortexa.yml`

### `targets` (Universal)
Defines **where** the tools operate.
This is used by the LangGraph App, MCP Server, and Daemon.
Multiple targets can be defined in one configuration file, but only one is active.
The active target is selected by the `active_target` attribute or the environment variable `OORTEXA_TARGET`

| Target Type | Mechanism |
|---|---|
| `local` | Executes direct bash commands via `subprocess.run`. |
| `container` | Wraps commands in `podman exec` or `docker run`. |
| `ssh` | Connects via `fabric` to run commands on a remote host. |
| `ssh+container` | Connects via fabric to run commands inside a container on a remote host |
| `compose` | Manages execution inside `docker-compose` services. |

### `roles` (Internal App Only)
Defines **who** is thinking. This section is strictly for the internal `python3 -m oortexa` application and is ignored by the MCP server/bridge.

| Role Type | Description |
|---|---|
| `orchestrator` | Creates a plan and delegates tasks to the executor to use tools. |
| `executor` | Uses tools and reports the output. |
| `analyst` | Reviews output from the executor and reports the outcome. |

Retrospectives are written by the analyst role using the `oortexa_write_retrospective` tool to the location specified by the `retropective_dir` attribute.

Each role has a set of attributes:
| Attribute Name | Description |
|---|---|
| `model` | Model identifier in provider |
| `base_url` | Provider endpoint |
| `api_key` | Endpoint API key, can be blank if using a local model |
| `prompts` | A list of strings or file paths or directories containing system prompt text |

---
