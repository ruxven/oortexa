import argparse
import os
import re
import json
import uuid
import asyncio
import yaml
from glob import glob
from typing import Annotated, TypedDict, List, Dict, Any, Union, Literal
from langchain_openai import ChatOpenAI
from langchain_core.globals import set_debug
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from oortexa.abstract_tools import abstract_tools, ToolContext

import logging

_logger = logging.getLogger("oortexa")


# State
class GraphState(TypedDict):
    messages: Annotated[List[BaseMessage], lambda x, y: x + y]
    config: Dict[str, Any]


def get_model(state: GraphState, role: str):
    role_cfg = state["config"].get("roles", {}).get(role, {})
    model_name = role_cfg.get("model")
    base_url = role_cfg.get("base_url")
    api_key = role_cfg.get("api_key")

    # Allow fallback to env for key if config is empty
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY", "no-key-required")

    return ChatOpenAI(model=model_name, base_url=base_url, api_key=api_key)


def load_role_prompts(role: str, state: GraphState) -> str:
    role_cfg = state["config"].get("roles", {}).get(role, {})
    prompt_sources = role_cfg.get("prompts", [])
    config_path = state["config"].get("_config_path")
    config_dir = os.path.dirname(config_path) if config_path else None

    full_prompts = []
    for source in prompt_sources:
        # Determine effective path
        if config_dir and not os.path.isabs(source):
            eff_path = os.path.join(config_dir, source)
        else:
            eff_path = source

        if not os.path.exists(eff_path):
            full_prompts.append(source)  # Literal
            continue

        if os.path.isfile(eff_path):
            with open(eff_path, "r") as f:
                full_prompts.append(f.read())
        elif os.path.isdir(eff_path):
            files = sorted(glob(os.path.join(eff_path, "*")))
            for fpath in files:
                if os.path.isfile(fpath):
                    with open(fpath, "r") as f:
                        full_prompts.append(f.read())

    return "\n\n".join(full_prompts)


# Nodes
def orchestrator(state: GraphState):
    model = get_model(state, "orchestrator")
    system_content = load_role_prompts("orchestrator", state)

    msgs = state["messages"]
    if system_content and not any(isinstance(m, SystemMessage) for m in msgs):
        msgs = [SystemMessage(content=system_content)] + msgs

    response = model.invoke(msgs)
    return {"messages": [response]}


def _parse_tool_calls_from_text(text: str):
    """Parse tool calls from model text output when native tool calling isn't supported."""
    if not text:
        return []

    text_clean = text.strip()
    tool_calls = []

    # Try to find JSON with tool/name + args first
    json_pattern = r"\{[^{}]*\}"
    for jm in re.findall(json_pattern, text_clean):
        try:
            parsed = json.loads(jm)
            if isinstance(parsed, dict):
                name = parsed.get("tool") or parsed.get("name")
                if name:
                    args = parsed.get("args", {}) or parsed.get("arguments", {})
                    if isinstance(args, str):
                        args = json.loads(args)
                    tool_calls.append(
                        {
                            "name": name,
                            "args": args,
                            "id": f"call_{uuid.uuid4().hex[:12]}",
                            "type": "tool_call",
                        }
                    )
                    return tool_calls
        except json.JSONDecodeError:
            pass

    # Fallback: match tool name from available tools
    for tool in abstract_tools:
        tool_name = tool.name
        if tool_name.lower() in text_clean.lower():
            tool_calls.append(
                {
                    "name": tool_name,
                    "args": {},
                    "id": f"call_{uuid.uuid4().hex[:12]}",
                    "type": "tool_call",
                }
            )
            break

    return tool_calls


def tool_calling_executor(state: GraphState):
    # Try to parse tool calls from the last message (orchestrator's instruction) directly
    last_msg = state["messages"][-1]
    if isinstance(last_msg, AIMessage) and last_msg.content:
        parsed = _parse_tool_calls_from_text(last_msg.content)
        if parsed:
            return {"messages": [AIMessage(content="", tool_calls=parsed)]}

    # Fallback: use LLM to generate tool calls
    model = get_model(state, "executor").bind_tools(abstract_tools)
    system_content = load_role_prompts("executor", state)

    msgs = state["messages"]
    if system_content and not any(isinstance(m, SystemMessage) for m in msgs):
        msgs = [SystemMessage(content=system_content)] + msgs

    response = model.invoke(msgs)

    if not response.tool_calls:
        parsed = _parse_tool_calls_from_text(response.content)
        if parsed:
            response = AIMessage(content=response.content, tool_calls=parsed)

    return {"messages": [response]}


def analyzer(state: GraphState):
    model = get_model(state, "analyst")  # Role name matches config: 'analyst'
    system_content = load_role_prompts("analyst", state)

    prompt = "Summarize the actions taken and results achieved."
    msgs = state["messages"] + [HumanMessage(content=prompt)]

    if system_content and not any(isinstance(m, SystemMessage) for m in msgs):
        msgs = [SystemMessage(content=system_content)] + msgs

    response = model.invoke(msgs)
    return {"messages": [response]}


def should_continue(state: GraphState) -> Literal["tools", "analyzer"]:
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return "analyzer"


def create_workflow():
    workflow = StateGraph(GraphState)
    workflow.add_node("orchestrator", orchestrator)
    workflow.add_node("executor", tool_calling_executor)
    workflow.add_node("tools", ToolNode(abstract_tools))
    workflow.add_node("analyzer", analyzer)

    workflow.add_edge(START, "orchestrator")
    workflow.add_edge("orchestrator", "executor")
    workflow.add_conditional_edges(
        "executor", should_continue, {"tools": "tools", "analyzer": "analyzer"}
    )
    workflow.add_edge("tools", "executor")
    workflow.add_edge("analyzer", END)

    return workflow.compile()


async def main():
    parser = argparse.ArgumentParser(description="OORTExA LangGraph runner")
    parser.add_argument("--prompt", type=str, required=True, help="User task prompt")
    parser.add_argument(
        "--config",
        type=str,
        default="oortexa.yml",
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable LangChain debug logging for LLM calls",
    )
    args = parser.parse_args()
    if args.debug:
        set_debug(True)
        logging.basicConfig(level=logging.DEBUG)

    if not os.path.exists(args.config):
        print(f"Error: Config file {args.config} not found.")
        return

    # Load YAML Configuration
    ToolContext.load_config(args.config)
    with open(args.config, "r") as f:
        full_config = yaml.safe_load(f)
    full_config["_config_path"] = args.config

    app = create_workflow()

    human_message_content = args.prompt
    if os.path.isfile(human_message_content):
        with open(human_message_content, "r") as fr:
            human_message_content = fr.read()

    initial_state = {
        "messages": [HumanMessage(content=human_message_content)],
        "config": full_config,
    }

    async for event in app.astream(initial_state):
        for node, values in event.items():
            print(f"--- Node: {node} ---")
            if "messages" in values:
                last_msg = values["messages"][-1]
                if isinstance(last_msg, AIMessage):
                    print(f"AI: {last_msg.content}")
                    if last_msg.tool_calls:
                        print(f"Tool Calls: {last_msg.tool_calls}")
                elif isinstance(last_msg, HumanMessage):
                    print(f"User: {last_msg.content}")
                elif isinstance(last_msg, SystemMessage):
                    print(f"System: {last_msg.content}")


if __name__ == "__main__":
    asyncio.run(main())
