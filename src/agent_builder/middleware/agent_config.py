"""Agent Configuration Middleware for managing agent building state."""

from typing import Any, Dict, Annotated, List
import re

from langchain.agents.middleware.types import AgentMiddleware, AgentState
from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.types import Command
from pydantic import ValidationError
from typing_extensions import TypedDict, NotRequired

from src.agent_builder.models import AgentConfig


def _agent_config_reducer(old: AgentConfig | Dict[str, Any] | None, new: AgentConfig | Dict[str, Any] | None) -> AgentConfig | Dict[str, Any] | None:
    """Reducer for updating agent configuration state."""
    if new is None:
        return old

    if isinstance(new, AgentConfig):
        return new

    # If new is a dictionary
    current_data = {}
    if old is not None:
        if isinstance(old, AgentConfig):
            current_data = old.model_dump()
        elif isinstance(old, dict):
            current_data = old

    # Merge update
    merged_data = {**current_data, **new}

    # Try to convert to AgentConfig if possible
    try:
        return AgentConfig(**merged_data)
    except ValidationError:
        # If validation fails (partial state), return as dictionary
        return merged_data


def _mock_conversations_reducer(old: List[BaseMessage] | None, new: List[BaseMessage] | None) -> List[BaseMessage]:
    """Reducer for updating mock conversations state."""
    if new is not None:
        return new
    return old or []


class AgentConfigState(AgentState):
    """State schema for agent configuration middleware."""

    agent_config: Annotated[NotRequired[AgentConfig], _agent_config_reducer]
    """The agent configuration dictionary."""

    mock_conversations: Annotated[NotRequired[List[BaseMessage]], _mock_conversations_reducer]
    """Markdown string containing mock conversation examples. never include the tool names in conversation"""


@tool
def write_agent_config(config: Dict[str, Any], runtime: ToolRuntime) -> Command | str:
    """Write a complete agent configuration with schema validation.

    This tool validates the entire configuration against the AgentConfig schema
    before writing it to state. Use this when you have a complete configuration ready.

    Args:
        config: Complete agent configuration dictionary matching AgentConfig schema.
            Required fields:
            - name (str, 1-10 chars): Agent name
            - description (str, 1-500 chars): Agent description
            - system_prompt (str, min 10 chars): System prompt
            - skills (list, exactly 1 item): List containing ONE skill object with:
                - name (str, 1-50 chars): Skill name, as just one skill, the name could same as agent name
                - when_to_use (str, 10-500 chars): When to use this skill
                - prompt (str, min 10 chars): Skill-specific prompt
                - tools (list): List of tool objects, each with 'name' and 'config'

    Returns:
        Success message or validation error details.

    Example:
        ```python
        write_agent_config({
            "name": "Hotel Booking Agent",
            "description": "Helps users book hotel rooms",
            "system_prompt": "You are a professional hotel booking assistant...",
            "skills": [
                {
                    "name": "Hotel Booking Agent",
                    "when_to_use": "When user wants to book a hotel room",
                    "prompt": "Book a hotel room...",
                    "tools": [{"name": "book_room", "config": {}}]
                }
            ]
        })
        ```
    """
    try:
        # Validate against AgentConfig schema
        validated_config = AgentConfig(**config)

        return Command(
            update={
                "agent_config": validated_config,
                "messages": [ToolMessage(
                    content=f"Agent configuration written successfully: {validated_config.name}",
                    tool_call_id=runtime.tool_call_id
                )]
            },
            goto="agent"
        )
    except ValidationError as e:
        # Return validation errors to the agent
        error_messages = []
        for error in e.errors():
            field = " -> ".join(str(x) for x in error["loc"])
            error_messages.append(f"  - {field}: {error['msg']}")

        return "Configuration validation failed:\n" + "\n".join(error_messages)


@tool
def update_agent_config(updates: Dict[str, Any], runtime: ToolRuntime) -> Command | str:
    """Update agent configuration incrementally.

    This tool allows you to build and modify the agent configuration step by step.
    You can update the entire configuration or just specific fields.

    Args:
        updates: Dictionary containing configuration updates. Can include:
            - name: Agent name (str)
            - description: Agent description (str)
            - system_prompt: System prompt (str)
            - skills: List of skill objects

    Returns:
        Confirmation message with the updated fields.

    Examples:
        Update only name:
        ```python
        update_agent_config({"name": "Hotel Booking Agent"})
        ```

        Update name and description:
        ```python
        update_agent_config({
            "name": "Hotel Agent",
            "description": "Helps users book hotel rooms"
        })
        ```

        Add complete configuration:
        ```python
        update_agent_config({
            "name": "Hotel Agent",
            "description": "Booking assistant",
            "system_prompt": "You are a professional...",
            "skills": [...]
        })
        ```
    """
    # Validate that updates is a dictionary
    if not isinstance(updates, dict):
        return "Error: updates must be a dictionary"

    # Return Command to update state
    updated_fields = ", ".join(updates.keys())
    return Command(
        update={
            "agent_config": updates,
            "messages": [ToolMessage(
                content=f"Agent configuration updated: {updated_fields}",
                tool_call_id=runtime.tool_call_id
            )]
        },
        goto="agent"  # Continue to agent node
    )


@tool
def read_agent_config() -> Dict[str, Any]:
    """Read the current agent configuration state.

    Returns:
        Current agent configuration dictionary, or empty dict if not yet created.

    Example:
        ```python
        config = read_agent_config()
        print(config.get("name"))  # Get agent name
        print(config.get("skills"))  # Get skills list
        ```
    """
    # This will be populated by the middleware with actual state access
    # The middleware will inject the current state value
    # In reality, this returns AgentConfig object if available, but for tool usage it will be serialized
    return {}


def parse_mock_conversations(conversation: str) -> List[BaseMessage]:
    """Parse markdown mock conversations into list of messages."""
    messages = []
    lines = conversation.split('\n')
    current_role = None
    current_content = []

    # Regex to match **Role:** pattern, capturing Role and Content
    # Supports "User", "Agent", "用户", or specific agent names
    role_pattern = re.compile(r'\*\*(.*?):\*\*\s*(.*)', re.IGNORECASE)

    for line in lines:
        line = line.strip()
        if not line:
            if current_role and current_content:
                content = "\n".join(current_content)
                if current_role.lower() in ['user', '用户']:
                    messages.append(HumanMessage(content=content))
                else:
                    # Assume anything else is the Agent
                    messages.append(AIMessage(content=content))
                current_content = []
            continue

        match = role_pattern.match(line)

        if match:
            # Save previous message if exists
            if current_role and current_content:
                content = "\n".join(current_content)
                if current_role.lower() in ['user', '用户']:
                    messages.append(HumanMessage(content=content))
                else:
                    messages.append(AIMessage(content=content))

            current_role = match.group(1).strip()
            current_content = [match.group(2).strip()]
        else:
            if current_role:
                current_content.append(line)

    # Add last message
    if current_role and current_content:
        content = "\n".join(current_content)
        if current_role.lower() in ['user', '用户']:
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))

    return messages


@tool
def update_mock_conversation(conversation: str, runtime: ToolRuntime) -> Command | str:
    """Update mock conversation examples.

    Args:
        conversation: Markdown-formatted mock conversation text. Never include the tool names in conversation

    Returns:
        Confirmation message.

    Example:
        ```python
        update_mock_conversation('''
        # Mock Conversations for Hotel Agent

        ## Scenario 1: Simple Booking
        **User:** I need a hotel room in Tokyo
        **Agent:** I'd be happy to help...
        ''')
        ```
    """
    if not isinstance(conversation, str):
        return "Error: conversation must be a string"

    messages = parse_mock_conversations(conversation)

    return Command(
        update={
            "mock_conversations": messages,
            "messages": [ToolMessage(
                content=f"Mock conversations updated ({len(messages)} messages parsed)",
                tool_call_id=runtime.tool_call_id
            )]
        },
        goto="agent"
    )


AGENT_CONFIG_SYSTEM_PROMPT = """## Agent Configuration Management

You are now in the agent configuration management mode. You can use the following tools to manage your agent configuration:

- `write_agent_config`: Write complete agent configuration (validates against AgentConfig schema)
- `update_agent_config`: Update the agent configuration (supports incremental updates)
- `read_agent_config`: Read the current configuration state
- `update_mock_conversation`: Update mock conversation examples. Never include the tool names in conversation

Please select a tool to proceed.
"""


class AgentConfigMiddleware(AgentMiddleware):
    """Middleware for managing agent configuration during the building process.

    This middleware provides tools for incrementally building and managing
    agent configurations, replacing the file-based approach with state management.

    Features:
    - Incremental configuration updates
    - Schema validation support
    - Mock conversation management
    - State-based storage (not file-based)
    """

    tools = [write_agent_config, update_agent_config, read_agent_config, update_mock_conversation]
    system_prompt = AGENT_CONFIG_SYSTEM_PROMPT
    state_schema = AgentConfigState

    def __init__(self, system_prompt: str | None = None):
        """Initialize the middleware.

        Args:
            system_prompt: Optional custom system prompt to append to the default.
        """
        if system_prompt:
            self.system_prompt = AGENT_CONFIG_SYSTEM_PROMPT + "\n\n" + system_prompt
