# OORTExA — Orchestrated Operations for Remote Tasking and Execution Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python >=3.10](https://img.shields.io/badge/python-%3E%3D3.10-blue)](pyproject.toml)

A **LangGraph**-based orchestration framework for collaborative development workflows using heterogeneous LLMs and containerized execution environments.

---

## Architecture

OORTExA uses a tripartite graph architecture:

- **Orchestrator Node** — High-level reasoning model that plans strategy and routes tasks.
- **Tool-calling Executor Node** — Engineering-focused model that performs actions using abstracted tools.
- **Analyst Node** — Summarizes results and performs final verification.

---

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

---

## Quickstart

Try the included local example:

```bash
# Run the example setup to generate oortexa.yml (prompts for model/endpoint)
bash rc.run_example local

# Or manually:
python3 -m oortexa --config examples/local/oortexa.yml \
  --prompt "Build the project and report any issues."
```

The example builds a small C program (`examples/local/local_demo.c`) using `clang` via the `oortexa_bash` tool.

---

## Configuration

OORTExA is configured via a `oortexa.yml` file. It supports heterogeneous LLM providers and multiple execution targets.

### Heterogeneous LLM Setup

Each role can specify its own model, endpoint, and API key. Local models (e.g., via LM Studio) can handle tool execution while cloud models (e.g., OpenAI) handle orchestration.

```yaml
roles:
  orchestrator:
    model: "gpt-4o"
    base_url: "https://api.openai.com/v1"
    api_key: "${OPENAI_API_KEY}"       # Use env vars instead of inline keys
    prompts: ["prompts/orchestrator/"]
  executor:
    model: "llama-3.1"
    base_url: "http://localhost:1234/v1"
    api_key: "lm-studio"
    prompts: ["You are a tool executor..."]
  analyst:
    model: "meta-llama/llama-3.1-70b-instruct"
    base_url: "http://remote-server:8000/v1"
    prompts: ["analyst_prompts/"]
```

### Execution Targets

The `targets` section defines where tools actually run. Switch between them by setting `active_target` or the `OORTEXA_TARGET` env var.

```yaml
active_target: "local"

targets:
  local:
    type: "local"

  container:
    type: "container"
    tool: "podman"                    # podman or docker
    mode: "exec"                      # "exec" (persistent) or "run" (transient)
    image: "fedora:latest"
    name: "oortexa-worker"
    args: ["-i", "--rm"]

  ssh_remote:
    type: "ssh"
    ssh:
      host: "192.168.1.50"
      user: "dev-user"
      identity: "~/.ssh/id_rsa"      # Optional

  ssh_container:
    type: "ssh+container"
    ssh:
      host: "my-remote-box"
      user: "root"
    container:
      tool: "docker"
      image: "node:18"
      mode: "exec"
      name: "app-container"
```

Supported target types: `local`, `ssh`, `container`, `ssh+container`, `compose`, `script`, `ssh+script`.

---

## Usage

```bash
python3 -m oortexa \
  --config oortexa.yml \
  --prompt "Add unit tests for the abstract_tools.py module."
```

Prompts can also be file paths:

```bash
python3 -m oortexa --config oortexa.yml --prompt ./task.txt
```

Enable verbose LLM debugging:

```bash
python3 -m oortexa --config oortexa.yml --prompt "..." --debug
```

---

## Features

- **Heterogeneous Provider Support** — Use different LLM APIs for different roles in the graph.
- **Flexible System Prompts** — Prompts can be literal strings, file paths, or directories (loaded in sorted order).
- **Cross-platform SSH Execution** — Native SSH and `plink.exe` support.
- **Containerized Tooling** — Seamless execution inside local or remote containers via Podman/Docker.
- **Local Execution Mode** — Run tools directly on the host system.
- **Environment Overrides** — Switch targets via `OORTEXA_TARGET` env var without touching config files.

---

## Project Status

This project is in early development. APIs may change as we iterate.

---

## Contributing

Contributions are welcome! Please open an issue or pull request on [GitHub](https://github.com/ruxven/oortexa).

---

## License

MIT — see [LICENSE](LICENSE).
