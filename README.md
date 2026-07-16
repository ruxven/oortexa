# OORTExA — Orchestrated Operations for Remote Tasking & Execution Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python >=3.10](https://img.shields.io/badge/python-%3E%3D3.10-blue)](pyproject.toml)

OORTExA is a Python-based orchestration framework for collaborative development. It doesn't rely on a single monolithic model; instead, it uses LangGraph to coordinate three distinct roles across heterogeneous LLMs & execution environments.

---

## Architecture

OORTExA uses a tripartite graph architecture to separate reasoning from action:

- **Orchestrator Node**: A high-level model that plans strategy & routes tasks.
- **Tool-calling Executor Node**: An engineering-focused model that performs actions using abstracted tools.
- **Analyst Node**: Summarizes results & performs final verification.

---

## Installation

Standard installation requires Python 3.10 or higher. You'll need LangGraph & Fabric for core orchestration:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

---

## Quickstart

The included local example runs a build script that prints the working directory and basic kernel information (i.e., `pwd` and `uname`).
Running the example setup script will ask a few questions to generate the `oortexa.yml` file from the template `oortexa.yml.base`.

```bash
# Run the example setup to generate oortexa.yml
bash rc.setup_example local

# Once the example is configured, Execute task:
python3 -m oortexa --config examples/local/oortexa.yml \
  --prompt "Build the project & report any issues."
```

---

## Configuration

Control OORTExA via `oortexa.yml`. Each node in the graph can point to a different provider, cost center, or capability profile.

### Heterogeneous LLM Setup

You don't have to use expensive cloud models for every step.
Local models running via LM Studio at `http://localhost:1234` can handle file operations while a larger GPT-4o instance manages the high-level plan.

```yaml
roles:
  orchestrator:
    model: "gpt-4o"
    base_url: "https://api.openai.com/v1"
    api_key: "${OPENAI_API_KEY}"
    prompts: ["prompts/orchestrator/"]
  executor:
    model: "llama-3.1"
    base_url: "http://localhost:1234/v1"
    api_key: "lm-studio"
    prompts: ["You are a tool executor..."]
```

### Execution Targets

OORTExA moves tool execution to where the code lives.
Setting the `active_target` or the `OORTEXA_TARGET` environment variable switches the entire toolset from local execution to containerized or remote SSH environments.

| Target Type | Mechanism |
|---|---|
| `local` | Executes direct bash commands via `subprocess.run`. |
| `container` | Wraps commands in `podman exec` or `docker run` using the specified image. |
| `ssh` | Connects via `fabric` to run commands on a remote host. |
| `ssh+container` | Tunnels container commands through an SSH connection. |
| `compose` | Manages execution inside `docker-compose` or `podman-compose` services. |

---

## Usage

```bash
python3 -m oortexa --config oortexa.yml --prompt "Add unit tests for abstract_tools.py."
```

Enable verbose debugging if the LLM isn't following the plan:

```bash
python3 -m oortexa --config oortexa.yml --prompt "..." --debug
```

---

## Features

- **Heterogeneous Provider Support**: Mix & match LLM APIs for different roles.
- **Flexible System Prompts**: Load prompts from literal strings, files, or sorted directories.
- **Native Container Support**: Handles Podman & Docker without separate logic.
- **Environment Overrides**: Use `OORTEXA_TARGET` to ignore the YAML target config.

---

## Project Status

OORTExA is in early development. APIs will change as the orchestration logic matures.

