"""Agent Builder - Standalone script for LangGraph deployment.

This module creates an agent builder that helps users create and configure
entrance agents through conversational interaction.
"""
import uuid
import json
from datetime import datetime
from dotenv import load_dotenv

from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from deepagents import create_deep_agent

from src.agent_builder.prompts import (
    AGENT_BUILDER_WORKFLOW_INSTRUCTIONS,
    WEB_SEARCH_AGENT_INSTRUCTIONS,
    CONFIG_MANAGER_AGENT_INSTRUCTIONS,
    SUBAGENT_DELEGATION_INSTRUCTIONS,
)
from src.agent_builder.tools import (
    web_search,
    fetch_webpage_content,
    think_tool,
    ask_user_to_provide_info,
    ask_user_to_confirm_build,
)
from src.agent_builder.models import AVAILABLE_TOOLS, AgentConfig
from src.agent_builder.middleware import AgentConfigMiddleware
from src.agent_builder.agent_single_create import create_agent_from_config
from src.utils.logger import logger

_ = load_dotenv()

# Limits
max_concurrent_units = 2
max_iterations = 5

# Get current date
current_date = datetime.now().strftime("%Y-%m-%d")


# Generate available tools list dynamically
def generate_available_tools_list():
    """Generate formatted list of available tools from AVAILABLE_TOOLS."""
    tools_list = []
    for idx, tool in enumerate(AVAILABLE_TOOLS, 1):
        tool_name = tool["name"]
        description = tool["description"]
        config_required = tool.get("config_required", [])

        config_info = f"Config required: {', '.join(config_required)}" if config_required else "No config required"

        tools_list.append(f'{idx}. **{tool_name}**\n   - {description}\n   - {config_info}')

    return "\n\n".join(tools_list)


# Combine orchestrator instructions
INSTRUCTIONS = (
    AGENT_BUILDER_WORKFLOW_INSTRUCTIONS
    + "\n\n"
    + "=" * 80
    + "\n\n"
    + SUBAGENT_DELEGATION_INSTRUCTIONS.format(
        max_concurrent_units=max_concurrent_units,
        max_iterations=max_iterations,
    )
)

# Create web-search sub-agent
web_search_agent = {
    "name": "web-search-agent",
    "description": "Delegate web search tasks to find reference information, design patterns, and best practices for agent building. Use this agent when you need inspiration or examples for agent design, prompts, or skill structures.",
    "system_prompt": WEB_SEARCH_AGENT_INSTRUCTIONS.format(date=current_date),
    "tools": [web_search, fetch_webpage_content, think_tool],
}

# Create config-manager sub-agent with AgentConfigMiddleware
config_manager_agent_instance = create_deep_agent(
    model=init_chat_model(model="openai:o3"),
    system_prompt=CONFIG_MANAGER_AGENT_INSTRUCTIONS.replace(
        "[[AVAILABLE_TOOLS_LIST]]", generate_available_tools_list()
    ),
    tools=[],
    middleware=[AgentConfigMiddleware()],
)

config_manager_agent = {
    "name": "config-manager-agent",
    "description": "Delegate configuration generation and management tasks. Use this agent when you need to create or modify agent configuration. This agent handles building configurations incrementally and generating mock conversation examples.",
    "runnable": config_manager_agent_instance,
}

model = init_chat_model(model="openai:o3")


def _format_interrupt_payload(payload) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    except TypeError:
        return str(payload)


def _log_state(state_values: dict, title: str = "Current State"):
    """Log formatted state information."""
    logger.info("=" * 80)
    logger.info(f"📊 {title}")
    logger.info("=" * 80)

    # Log agent_config
    if "agent_config" in state_values and state_values["agent_config"]:
        config_data = state_values["agent_config"]
        if isinstance(config_data, AgentConfig):
            config_data = config_data.model_dump()

        logger.info("⚙️  Agent Config:")
        logger.info(f"  - Name: {config_data.get('name', 'N/A')}")
        logger.info(f"  - Description: {config_data.get('description', 'N/A')}")
        if "skills" in config_data:
            logger.info(f"  - Skills: {len(config_data['skills'])} skill(s)")
            for idx, skill in enumerate(config_data['skills'], 1):
                logger.info(f"    {idx}. {skill.get('name', 'N/A')}")
    else:
        logger.info("⚙️  Agent Config: Not set")

    # Log mock_conversations
    if "mock_conversations" in state_values and state_values["mock_conversations"]:
        mock_conv = state_values["mock_conversations"]
        if isinstance(mock_conv, list):
            logger.info(f"💭 Mock Conversations: {len(mock_conv)} messages")
            if mock_conv:
                first_msg = mock_conv[0]
                content = getattr(first_msg, "content", str(first_msg))
                logger.info(f"  Preview (first msg): {content[:150]}...")
        else:
            logger.info(f"💭 Mock Conversations: {len(mock_conv)} characters")
            logger.info(f"  Preview: {mock_conv[:150]}...")
    else:
        logger.info("💭 Mock Conversations: Not set")

    # Log todos
    if "todos" in state_values and state_values["todos"]:
        todos = state_values["todos"]
        logger.info(f"✅ TODOs: {len(todos)} item(s)")
        for todo in todos:
            status_icon = "✓" if todo.get("status") == "completed" else "⏳" if todo.get("status") == "in_progress" else "○"
            logger.info(f"  {status_icon} {todo.get('content', 'N/A')}")
    else:
        logger.info("✅ TODOs: None")

    # Log files (from FilesystemMiddleware)
    if "files" in state_values and state_values["files"]:
        files_dict = state_values["files"]
        logger.info(f"📁 Files: {len(files_dict)} file(s)")
        for file_path, file_data in files_dict.items():
            if isinstance(file_data, dict):
                content_preview = file_data.get("content", "")[:100] if file_data.get("content") else "N/A"
                logger.info(f"  - {file_path}: {len(file_data.get('content', ''))} characters")
                logger.info(f"    Preview: {content_preview}...")
            else:
                logger.info(f"  - {file_path}")
    else:
        logger.info("📁 Files: None")

    # Log message count
    if "messages" in state_values and state_values["messages"]:
        logger.info(f"\n💬 Messages: {len(state_values['messages'])} message(s)")

    logger.info("=" * 80)


if __name__ == "__main__":
    # query = input("请输入问题：")
    query = "帮我生成一个餐厅预约的agent，餐厅如下：https://tabelog.com/cn/tokyo/A1306/A130602/13042979/"
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    checkpointer = InMemorySaver()

    # Create the agent builder
    # Note: AgentConfigMiddleware is added to main agent so it can receive
    # and handle state updates from config_manager_agent subagent
    agent = create_deep_agent(
        model=model,
        checkpointer=checkpointer,
        tools=[
            ask_user_to_provide_info,
            ask_user_to_confirm_build,
        ],
        system_prompt=INSTRUCTIONS,
        subagents=[web_search_agent, config_manager_agent],
        middleware=[AgentConfigMiddleware()],
    )

    logger.info("=" * 80)
    logger.info("🚀 Starting Agent Builder")
    logger.info("=" * 80)
    logger.info(f"Query: {query}")

    # Use streaming to get detailed updates
    for chunk in agent.stream({"messages": [{"role": "user", "content": query}]}, config=config):
        logger.info("\n" + "=" * 80)
        logger.info(f"📦 Chunk received from: {list(chunk.keys())}")
        logger.info("=" * 80)

        for node_name, node_output in chunk.items():
            logger.info(f"🔹 Node: {node_name}")

            if not node_output:
                logger.info("  (No output)")
                continue

            # Log messages
            if "messages" in node_output:
                messages = node_output["messages"]
                if isinstance(messages, list) and messages:
                    last_msg = messages[-1]
                    logger.info(f"  💬 Message Type: {type(last_msg).__name__}")
                    if hasattr(last_msg, "content") and last_msg.content:
                        logger.info(f"  📝 Content: {last_msg.content}")
                    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                        logger.info(f"  🔧 Tool Calls: {len(last_msg.tool_calls)}")
                        for tc in last_msg.tool_calls:
                            logger.info(f"    - {tc.get('name', 'unknown')}: {str(tc.get('args', {}))}")
                elif messages:
                    # Fallback for non-list message updates (e.g. Overwrite)
                    logger.info(f"  💬 Message Update: {type(messages).__name__}")

            # Log agent_config state updates
            if "agent_config" in node_output:
                config_data = node_output["agent_config"]
                if hasattr(config_data, "model_dump"):
                    config_data = config_data.model_dump()

                logger.info("  ⚙️  Agent Config Updated:")
                if config_data:
                    logger.info(f"    - Name: {config_data.get('name', 'N/A')}")
                    logger.info(f"    - Description: {config_data.get('description', 'N/A')}")
                    if "skills" in config_data:
                        logger.info(f"    - Skills: {len(config_data['skills'])} skill(s)")

            # Log mock_conversations state updates
            if "mock_conversations" in node_output:
                mock_conv = node_output["mock_conversations"]
                if mock_conv:
                    if isinstance(mock_conv, list):
                        logger.info(f"  💭 Mock Conversations Updated: {len(mock_conv)} messages")
                    else:
                        logger.info(f"  💭 Mock Conversations Updated: {len(mock_conv)} characters")

            # Log todos
            if "todos" in node_output:
                todos_list = node_output["todos"]
                if todos_list:
                    logger.info(f"  ✅ TODOs: {len(todos_list)} item(s)")
                    for todo in todos_list:
                        status_icon = "✓" if todo.get("status") == "completed" else "⏳" if todo.get("status") == "in_progress" else "○"
                        logger.info(f"    {status_icon} {todo.get('content', 'N/A')}")

            # Check for interrupts
            if "__interrupt__" in node_output:
                logger.info("  ⚠️  Interrupt detected")

    # Log state after each chunk
    current_state = agent.get_state(config)
    _log_state(current_state.values, "State After Chunk")

    # Handle any final interrupts
    final_state = agent.get_state(config)
    while final_state.next:
        if hasattr(final_state, "tasks") and final_state.tasks:
            interrupt_item = final_state.tasks[0]
            payload = getattr(interrupt_item, "interrupts", [{}])[0] if hasattr(interrupt_item, "interrupts") else {}

            print("\n" + "=" * 80)
            print("⚠️  INTERRUPT - User Input Required")
            print("=" * 80)
            print(_format_interrupt_payload(payload))

            user_input = input("\n> ")

            # Continue streaming with resume command
            # This resumes execution from the interrupt point with the user's input
            resume_command = Command(resume=user_input)

            for chunk in agent.stream(resume_command, config=config):
                logger.info("\n" + "=" * 80)
                logger.info(f"📦 Chunk received from: {list(chunk.keys())}")
                logger.info("=" * 80)

                for node_name, node_output in chunk.items():
                    logger.info(f"🔹 Node: {node_name}")

                    if not node_output:
                        logger.info("  (No output)")
                        continue

                    # Log messages
                    if "messages" in node_output:
                        messages = node_output["messages"]
                        if isinstance(messages, list) and messages:
                            last_msg = messages[-1]
                            logger.info(f"  💬 Message Type: {type(last_msg).__name__}")
                            if hasattr(last_msg, "content") and last_msg.content:
                                logger.info(f"  📝 Content: {last_msg.content}")
                            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                                logger.info(f"  🔧 Tool Calls: {len(last_msg.tool_calls)}")
                                for tc in last_msg.tool_calls:
                                    logger.info(f"    - {tc.get('name', 'unknown')}: {str(tc.get('args', {}))}")
                        elif messages:
                            # Fallback for non-list message updates (e.g. Overwrite)
                            logger.info(f"  💬 Message Update: {type(messages).__name__}")

                    # Log agent_config state updates
                    if "agent_config" in node_output:
                        config_data = node_output["agent_config"]
                        logger.info("  ⚙️  Agent Config Updated:")
                        if config_data:
                            logger.info(f"    - Name: {config_data.get('name', 'N/A')}")
                            logger.info(f"    - Description: {config_data.get('description', 'N/A')}")
                            if "skills" in config_data:
                                logger.info(f"    - Skills: {len(config_data['skills'])} skill(s)")

                    # Log mock_conversations state updates
                    if "mock_conversations" in node_output:
                        mock_conv = node_output["mock_conversations"]
                        if mock_conv:
                            logger.info(f"  💭 Mock Conversations Updated: {len(mock_conv)} characters")

                    # Log todos
                    if "todos" in node_output:
                        todos_list = node_output["todos"]
                        if todos_list:
                            logger.info(f"  ✅ TODOs: {len(todos_list)} item(s)")
                            for todo in todos_list:
                                status_icon = "✓" if todo.get("status") == "completed" else "⏳" if todo.get("status") == "in_progress" else "○"
                                logger.info(f"    {status_icon} {todo.get('content', 'N/A')}")

                    # Check for interrupts
                    if "__interrupt__" in node_output:
                        logger.info("  ⚠️  Interrupt detected")

            # Log state after each chunk in resume loop
            current_state = agent.get_state(config)
            _log_state(current_state.values, "State After Resume Chunk")

            final_state = agent.get_state(config)

    logger.info("\n" + "=" * 80)
    logger.info("✅ Agent Builder Completed")
    logger.info("=" * 80)
    _log_state(current_state.values, "Completed State")

    # Print final results to console
    print("\n" + "=" * 80)
    print("✅ Agent Builder Completed")
    print("=" * 80)

    if final_state.values.get("agent_config"):
        print("\n📋 Final Agent Configuration:")
        config_data = final_state.values["agent_config"]
        if hasattr(config_data, "model_dump"):
            config_data = config_data.model_dump()
        print(json.dumps(config_data, indent=2, ensure_ascii=False))

    if final_state.values.get("mock_conversations"):
        print("\n💭 Final Mock Conversations:")
        mock_conv = final_state.values["mock_conversations"]
        if isinstance(mock_conv, list):
            for msg in mock_conv:
                role = "User" if msg.type == "human" else "Agent"
                print(f"**{role}:** {msg.content}\n")
        else:
            print(mock_conv)

    if final_state.values.get("messages"):
        print("\n💬 Final Message:")
        print(final_state.values["messages"][-1].content)

    # Create dynamic agent from the built configuration
    if final_state.values.get("agent_config"):
        print("\n" + "=" * 80)
        print("🔨 Creating Dynamic Agent from Configuration")
        print("=" * 80)

        agent_config = final_state.values["agent_config"]
        dynamic_agent = create_agent_from_config(agent_config)

        print("\n✅ Dynamic Agent Created Successfully!")

        # Start interactive conversation with the dynamic agent
        print("\n" + "=" * 80)
        print("💬 Starting Interactive Conversation")
        print("=" * 80)
        agent_name = agent_config.name if hasattr(agent_config, 'name') else agent_config.get('name')
        print(f"You are now chatting with: {agent_name}")
        print("Type 'exit' or 'quit' to end the conversation")
        print("=" * 80 + "\n")

        # Create a new thread for the dynamic agent conversation
        dynamic_config = {"configurable": {"thread_id": str(uuid.uuid4())}}

        while True:
            try:
                user_input = input("You: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print(f"\n👋 Ending conversation with {agent_name}. Goodbye!")
                    break

                # Invoke the dynamic agent
                print(f"\n{agent_name}: ", end="", flush=True)
                result = dynamic_agent.invoke(
                    {"messages": [{"role": "user", "content": user_input}]},
                    config=dynamic_config
                )

                # Print the agent's response
                response = result["messages"][-1].content
                print(response + "\n")

            except KeyboardInterrupt:
                print(f"\n\n👋 Conversation interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")
                logger.error(f"Error in dynamic agent conversation: {e}", exc_info=True)
