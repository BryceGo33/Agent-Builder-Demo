import streamlit as st
import uuid
import logging
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
)
from src.agent_builder.models import AVAILABLE_TOOLS, AgentConfig
from src.agent_builder.middleware import AgentConfigMiddleware
from src.agent_builder.agent_single_create import create_agent_from_config

_ = load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('streamlit_app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Agent Builder Demo",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 2rem;
        color: #1f77b4;
    }
    .section-header {
        font-size: 1.5rem;
        font-weight: bold;
        margin-bottom: 1rem;
        color: #2c3e50;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .user-message {
        background-color: #e3f2fd;
        margin-left: 2rem;
    }
    .agent-message {
        background-color: #f5f5f5;
        margin-right: 2rem;
    }
    .mock-conversation {
        background-color: #fff9e6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #ffc107;
        margin-bottom: 0.5rem;
    }
    .stButton button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "builder_messages" not in st.session_state:
    st.session_state.builder_messages = [
        {
            "role": "assistant",
            "content": "👋 欢迎使用 Agent Builder！\n\n我可以帮你创建定制化的 AI Agent。请告诉我你想要创建什么样的 Agent，比如：\n- 预约助手\n请描述你的需求，我会帮你一步步构建！！"
        }
    ]
if "entrance_messages" not in st.session_state:
    st.session_state.entrance_messages = []
if "mock_conversations" not in st.session_state:
    st.session_state.mock_conversations = []
if "agent_config" not in st.session_state:
    st.session_state.agent_config = None
if "entrance_agent" not in st.session_state:
    st.session_state.entrance_agent = None
if "builder_agent" not in st.session_state:
    st.session_state.builder_agent = None
if "builder_config" not in st.session_state:
    st.session_state.builder_config = {"configurable": {"thread_id": str(uuid.uuid4())}}
if "entrance_config" not in st.session_state:
    st.session_state.entrance_config = {"configurable": {"thread_id": str(uuid.uuid4())}}
if "builder_waiting_interrupt" not in st.session_state:
    st.session_state.builder_waiting_interrupt = False
if "interrupt_data" not in st.session_state:
    st.session_state.interrupt_data = None
if "pending_builder_input" not in st.session_state:
    st.session_state.pending_builder_input = None
if "pending_entrance_input" not in st.session_state:
    st.session_state.pending_entrance_input = None


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


def initialize_builder_agent():
    """Initialize the agent builder."""
    if st.session_state.builder_agent is not None:
        return st.session_state.builder_agent

    current_date = datetime.now().strftime("%Y-%m-%d")
    max_concurrent_units = 2
    max_iterations = 5

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

    web_search_agent = {
        "name": "web-search-agent",
        "description": "Delegate web search tasks to find reference information, design patterns, and best practices for agent building.",
        "system_prompt": WEB_SEARCH_AGENT_INSTRUCTIONS.format(date=current_date),
        "tools": [web_search, fetch_webpage_content, think_tool],
    }

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
        "description": "Delegate configuration generation and management tasks.",
        "runnable": config_manager_agent_instance,
    }

    model = init_chat_model(model="openai:o3")
    checkpointer = InMemorySaver()

    agent = create_deep_agent(
        model=model,
        checkpointer=checkpointer,
        tools=[ask_user_to_provide_info],
        system_prompt=INSTRUCTIONS,
        subagents=[web_search_agent, config_manager_agent],
        middleware=[AgentConfigMiddleware()],
    )

    st.session_state.builder_agent = agent
    return agent


def process_builder_message(user_input, chat_container=None):
    """Process a message in the agent builder with streaming support."""
    logger.info(f"Processing builder message: {user_input}")
    agent = initialize_builder_agent()

    try:
        # Check if we're responding to an interrupt
        if st.session_state.builder_waiting_interrupt:
            logger.info("Resuming from interrupt")
            msg = {"role": "system", "content": "📤 Resuming from interrupt..."}
            st.session_state.builder_messages.append(msg)
            if chat_container:
                display_message_in_container(chat_container, msg)

            # Resume from interrupt
            for chunk in agent.stream(
                Command(resume=user_input),
                config=st.session_state.builder_config,
                stream_mode="updates"
            ):
                process_stream_chunk_realtime(chunk, chat_container)

            st.session_state.builder_waiting_interrupt = False
            st.session_state.interrupt_data = None
        else:
            logger.info("Starting agent builder stream")
            msg = {"role": "system", "content": "🤖 Agent Builder is processing..."}
            st.session_state.builder_messages.append(msg)
            if chat_container:
                display_message_in_container(chat_container, msg)

            # Stream the agent execution
            for chunk in agent.stream(
                {"messages": [{"role": "user", "content": user_input}]},
                config=st.session_state.builder_config,
                stream_mode="updates"
            ):
                process_stream_chunk_realtime(chunk, chat_container)

        # Check for interrupts
        state = agent.get_state(st.session_state.builder_config)
        logger.info(f"Agent state - next: {state.next}")

        # Update state information
        update_state_from_agent(state)

        # Check for interrupts - look for tasks with interrupts
        has_interrupt = False
        if state.tasks and len(state.tasks) > 0:
            task = state.tasks[0]
            if hasattr(task, 'interrupts') and len(task.interrupts) > 0:
                has_interrupt = True

        if has_interrupt:
            logger.info("Interrupt detected")
            st.session_state.builder_waiting_interrupt = True

            # Extract interrupt payload
            interrupt_parts = ["⚠️ INTERRUPT - User Input Required"]

            task = state.tasks[0]
            interrupt_item = task.interrupts[0]
            logger.info(f"Interrupt item type: {type(interrupt_item)}")

            # Get payload from .value attribute
            if hasattr(interrupt_item, 'value'):
                payload = interrupt_item.value
                logger.info(f"Payload content: {payload}")

                if payload and isinstance(payload, dict):
                    # Format the interrupt payload structure
                    interrupt_parts.append("\n\nInterrupt payload:")
                    interrupt_parts.append("\n{")
                    if "tool" in payload:
                        interrupt_parts.append(f'\n    "tool": "{payload["tool"]}",')
                    if "confirm_message" in payload:
                        interrupt_parts.append(f'\n    "confirm_message": "{payload["confirm_message"]}",')
                    if "agent_config" in payload:
                        interrupt_parts.append('\n    "agent_config": <AgentConfig object>,')
                    interrupt_parts.append("\n}")
                    logger.info(f"Formatted interrupt payload successfully")
                else:
                    interrupt_parts.append("\n\n(No payload data available)")
                    logger.warning("Payload is not a dict")
            else:
                interrupt_parts.append("\n\n(No .value attribute found)")
                logger.warning("No .value attribute in interrupt item")

            interrupt_msg = "".join(interrupt_parts)
            msg = {"role": "assistant", "content": interrupt_msg}
            st.session_state.builder_messages.append(msg)
            logger.info(f"Final interrupt message: {interrupt_msg}")
        else:
            # Get final message
            if state.values.get("messages"):
                final_msg = state.values["messages"][-1].content
                if final_msg and final_msg not in [msg["content"] for msg in st.session_state.builder_messages[-3:]]:
                    st.session_state.builder_messages.append({"role": "assistant", "content": final_msg})

            # Only show completion if entrance agent was created
            if st.session_state.entrance_agent is not None:
                st.session_state.builder_messages.append({"role": "system", "content": "✅ Agent Builder completed!"})
                logger.info("Agent builder completed")

    except Exception as e:
        logger.error(f"Error in builder: {str(e)}", exc_info=True)
        st.session_state.builder_messages.append({"role": "assistant", "content": f"❌ Error: {str(e)}"})


def display_message_in_container(container, msg):
    """Display a single message in the given container."""
    with container:
        if msg["role"] == "user":
            css_class = "user-message"
            role_icon = "👤"
        elif msg["role"] == "system":
            css_class = "agent-message"
            role_icon = "ℹ️"
        else:
            css_class = "agent-message"
            role_icon = "🤖"

        content = msg["content"].replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        st.markdown(
            f'<div class="chat-message {css_class}">{role_icon} <strong>{msg["role"].title()}:</strong><br>{content}</div>',
            unsafe_allow_html=True
        )


def process_stream_chunk_realtime(chunk, chat_container=None):
    """Process a single chunk from the agent stream and display in real-time."""
    for node_name, node_output in chunk.items():
        logger.info(f"Processing chunk from node: {node_name}")

        if not node_output:
            continue

        # Determine role based on node name
        role = "assistant" if node_name == "__interrupt__" else "system"

        # Build status message
        status_parts = [f"🔹 Executing: {node_name}"]

        # Check for messages
        if "messages" in node_output:
            messages = node_output["messages"]
            if isinstance(messages, list) and messages:
                last_msg = messages[-1]
                if hasattr(last_msg, "content") and last_msg.content:
                    content_preview = last_msg.content[:150]
                    status_parts.append(f"\n📝 Message: {content_preview}...")
                if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                    tool_names = [tc.get("name", "unknown") for tc in last_msg.tool_calls]
                    status_parts.append(f"\n🔧 Tool Calls: {', '.join(tool_names)}")
                    logger.info(f"Tool calls: {tool_names}")

        # Check for todos
        if "todos" in node_output:
            todos = node_output["todos"]
            if todos:
                status_parts.append(f"\n✅ TODOs: {len(todos)} items")
                todo_preview = "\n".join([f"  - [{t.get('status', 'pending')}] {t.get('content', 'N/A')}" for t in todos])
                status_parts.append(f"\n{todo_preview}")
                logger.info(f"TODOs updated: {len(todos)} items")

        # Check for agent_config updates
        if "agent_config" in node_output:
            status_parts.append("\n⚙️ Agent config updated")
            logger.info("Agent config updated")

        # Check for mock_conversations updates
        if "mock_conversations" in node_output:
            status_parts.append("\n💭 Mock conversations updated")
            logger.info("Mock conversations updated")

        # Add to permanent chat history immediately
        status_msg = "".join(status_parts)
        msg = {"role": role, "content": status_msg}
        st.session_state.builder_messages.append(msg)

        # Display in real-time in the chat container
        if chat_container:
            display_message_in_container(chat_container, msg)


def update_state_from_agent(state):
    """Update session state from agent state."""
    logger.info("Updating state from agent")

    # Update agent config
    if state.values.get("agent_config"):
        logger.info("Agent config found in state")
        new_config = state.values["agent_config"]

        # Check if config has changed by comparing serialized versions
        old_config_dict = None
        if st.session_state.agent_config is not None:
            if hasattr(st.session_state.agent_config, "model_dump"):
                old_config_dict = st.session_state.agent_config.model_dump()
            else:
                old_config_dict = st.session_state.agent_config

        new_config_dict = new_config.model_dump() if hasattr(new_config, "model_dump") else new_config

        config_changed = (
            old_config_dict is None or
            old_config_dict != new_config_dict
        )

        logger.info(f"Config changed: {config_changed}")
        logger.info(f"Old config exists: {old_config_dict is not None}")
        logger.info(f"New config name: {new_config_dict.get('name') if isinstance(new_config_dict, dict) else 'N/A'}")
        if old_config_dict:
            logger.info(f"Old config name: {old_config_dict.get('name') if isinstance(old_config_dict, dict) else 'N/A'}")

            # Detailed comparison
            if isinstance(old_config_dict, dict) and isinstance(new_config_dict, dict):
                logger.info("Comparing config dictionaries:")
                logger.info(f"  Old config keys: {sorted(old_config_dict.keys())}")
                logger.info(f"  New config keys: {sorted(new_config_dict.keys())}")

                # Check each key
                all_keys = set(old_config_dict.keys()) | set(new_config_dict.keys())
                for key in sorted(all_keys):
                    old_val = old_config_dict.get(key)
                    new_val = new_config_dict.get(key)
                    if old_val != new_val:
                        logger.info(f"  Key '{key}' differs:")
                        logger.info(f"    Old: {str(old_val)[:200]}")
                        logger.info(f"    New: {str(new_val)[:200]}")

        if config_changed and old_config_dict:
            logger.info("Config differences detected - will recreate entrance agent")

        st.session_state.agent_config = new_config

        # Create or recreate entrance agent if config changed
        if config_changed:
            try:
                action = "Creating" if st.session_state.entrance_agent is None else "Recreating"
                logger.info(f"{action} entrance agent")
                st.session_state.entrance_agent = create_agent_from_config(st.session_state.agent_config)

                # Clear entrance messages when recreating agent
                if action == "Recreating":
                    logger.info("Clearing entrance messages due to agent recreation")
                    st.session_state.entrance_messages = []

                message = "✅ Entrance Agent has been created! You can now chat with it in the right panel." if action == "Creating" else "✅ Entrance Agent has been updated with new configuration! Previous chat history has been cleared."
                st.session_state.builder_messages.append({
                    "role": "system",
                    "content": message
                })
                logger.info("Entrance agent created successfully")
            except Exception as e:
                logger.error(f"Failed to create entrance agent: {str(e)}", exc_info=True)
                st.session_state.builder_messages.append({
                    "role": "system",
                    "content": f"⚠️ Failed to create entrance agent: {str(e)}"
                })
        else:
            logger.info("Config unchanged, skipping entrance agent recreation")

    # Update mock conversations
    if state.values.get("mock_conversations"):
        mock_conv = state.values["mock_conversations"]
        logger.info(f"Mock conversations found: {len(mock_conv) if isinstance(mock_conv, list) else 'unknown'}")
        if isinstance(mock_conv, list) and len(mock_conv) > 0:
            st.session_state.mock_conversations = [
                {"role": "User" if msg.type == "human" else "Agent", "content": msg.content}
                for msg in mock_conv
            ]
            logger.info(f"Mock conversations updated: {len(st.session_state.mock_conversations)} messages")

    # Update todos for display
    if state.values.get("todos"):
        todos = state.values["todos"]
        logger.info(f"TODOs found: {len(todos)} items")
        if todos and len(st.session_state.builder_messages) > 0:
            # Add todos info to last message if it's a system message
            todo_summary = "\n\n📋 Current TODOs:\n" + "\n".join(
                [f"- [{t.get('status', 'pending')}] {t.get('content', 'N/A')}" for t in todos[:5]]
            )
            if st.session_state.builder_messages[-1].get("role") == "system":
                st.session_state.builder_messages[-1]["content"] += todo_summary


def process_entrance_message(user_input):
    """Process a message in the entrance agent."""
    logger.info(f"Processing entrance message: {user_input}")

    if st.session_state.entrance_agent is None:
        st.error("Please create an agent first using the Agent Builder.")
        return

    try:
        logger.info("Invoking entrance agent")
        result = st.session_state.entrance_agent.invoke(
            {"messages": [{"role": "user", "content": user_input}]},
            config=st.session_state.entrance_config
        )

        agent_response = result["messages"][-1].content
        logger.info(f"Entrance agent response: {agent_response[:100]}...")
        st.session_state.entrance_messages.append({"role": "assistant", "content": agent_response})

    except Exception as e:
        logger.error(f"Error in entrance agent: {str(e)}", exc_info=True)
        st.session_state.entrance_messages.append({"role": "assistant", "content": f"❌ Error: {str(e)}"})


# Main UI
st.markdown('<div class="main-header">🤖 Agent Builder Demo</div>', unsafe_allow_html=True)

# Create three-column layout
col_left, col_right = st.columns([1, 1])

with col_left:
    st.markdown('<div class="section-header">💬 Agent Builder</div>', unsafe_allow_html=True)

    # Chat container
    builder_chat_container = st.container(height=600)
    with builder_chat_container:
        for msg in st.session_state.builder_messages:
            if msg["role"] == "user":
                css_class = "user-message"
                role_icon = "👤"
            elif msg["role"] == "system":
                css_class = "agent-message"
                role_icon = "ℹ️"
            else:
                css_class = "agent-message"
                role_icon = "🤖"

            # Escape HTML in content but preserve newlines
            content = msg["content"].replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            st.markdown(
                f'<div class="chat-message {css_class}">{role_icon} <strong>{msg["role"].title()}:</strong><br>{content}</div>',
                unsafe_allow_html=True
            )

        # Streaming messages will be added directly to the container above

    # Input area with restart button
    col_input, col_restart = st.columns([4, 1])

    with col_input:
        with st.form(key="builder_form", clear_on_submit=True):
            builder_input = st.text_input(
                "Your message:",
                placeholder="Describe the agent you want to build...",
                key="builder_input"
            )
            submit_builder = st.form_submit_button("Send")

            if submit_builder and builder_input:
                # Add user message immediately and rerun to show it
                st.session_state.builder_messages.append({"role": "user", "content": builder_input})
                st.session_state.pending_builder_input = builder_input
                st.rerun()

    with col_restart:
        st.write("")  # Add spacing to align with input
        if st.button("🔄 Restart", key="restart_builder", use_container_width=True):
            # Clear builder conversation
            st.session_state.builder_messages = []
            st.session_state.pending_builder_input = None
            st.session_state.builder_waiting_interrupt = False
            st.session_state.interrupt_data = None
            # Generate new thread_id for fresh conversation
            st.session_state.builder_config = {"configurable": {"thread_id": str(uuid.uuid4())}}
            st.rerun()

    # Agent Configuration Display
    st.markdown("---")
    if st.session_state.agent_config:
        with st.expander("⚙️ 生成的 Agent 配置", expanded=False):
            config_data = st.session_state.agent_config
            if hasattr(config_data, "model_dump"):
                config_data = config_data.model_dump()
            st.json(config_data)
    else:
        st.caption("💡 Agent 配置将在生成后显示在这里")

    # Process pending input AFTER displaying chat (so user sees their message first)
    if st.session_state.pending_builder_input:
        user_input = st.session_state.pending_builder_input
        st.session_state.pending_builder_input = None

        # Process message and let it add messages to session state
        process_builder_message(user_input, builder_chat_container)
        st.rerun()

with col_right:
    # Top: Mock Conversations
    st.markdown('<div class="section-header">📝 Mock Conversations</div>', unsafe_allow_html=True)
    mock_container = st.container(height=250)
    with mock_container:
        if st.session_state.mock_conversations:
            for msg in st.session_state.mock_conversations:
                role_icon = "👤" if msg["role"] == "User" else "🤖"
                st.markdown(
                    f'<div class="mock-conversation">{role_icon} <strong>{msg["role"]}:</strong><br>{msg["content"]}</div>',
                    unsafe_allow_html=True
                )
        else:
            st.info("Mock conversations will appear here after agent creation.")

    st.markdown("---")

    # Bottom: Entrance Agent Chat
    st.markdown('<div class="section-header">🎯 Entrance Agent Chat</div>', unsafe_allow_html=True)

    if st.session_state.agent_config:
        agent_name = st.session_state.agent_config.name if hasattr(st.session_state.agent_config, 'name') else st.session_state.agent_config.get('name')
        st.caption(f"Chatting with: **{agent_name}**")

    entrance_chat_container = st.container(height=250)
    with entrance_chat_container:
        if st.session_state.entrance_agent is None:
            st.info("Create an agent using the Agent Builder first.")
        else:
            for msg in st.session_state.entrance_messages:
                css_class = "user-message" if msg["role"] == "user" else "agent-message"
                role_icon = "👤" if msg["role"] == "user" else "🎯"
                st.markdown(
                    f'<div class="chat-message {css_class}">{role_icon} <strong>{msg["role"].title()}:</strong><br>{msg["content"]}</div>',
                    unsafe_allow_html=True
                )

    # Input area with restart button
    col_input, col_restart = st.columns([4, 1])

    with col_input:
        with st.form(key="entrance_form", clear_on_submit=True):
            entrance_input = st.text_input(
                "Your message:",
                placeholder="Chat with your agent...",
                key="entrance_input",
                disabled=st.session_state.entrance_agent is None
            )
            submit_entrance = st.form_submit_button("Send", disabled=st.session_state.entrance_agent is None)

            if submit_entrance and entrance_input:
                # Add user message immediately and rerun to show it
                st.session_state.entrance_messages.append({"role": "user", "content": entrance_input})
                st.session_state.pending_entrance_input = entrance_input
                st.rerun()

    with col_restart:
        st.write("")  # Add spacing to align with input
        if st.button("🔄 Restart", key="restart_entrance", use_container_width=True, disabled=st.session_state.entrance_agent is None):
            # Clear entrance agent conversation
            st.session_state.entrance_messages = []
            st.session_state.pending_entrance_input = None
            # Generate new thread_id for fresh conversation
            st.session_state.entrance_config = {"configurable": {"thread_id": str(uuid.uuid4())}}
            st.rerun()

    # Process pending input AFTER displaying chat
    if st.session_state.pending_entrance_input:
        user_input = st.session_state.pending_entrance_input
        st.session_state.pending_entrance_input = None
        process_entrance_message(user_input)
        st.rerun()

# Sidebar with agent config
with st.sidebar:
    st.header("📋 Agent Configuration")
    if st.session_state.agent_config:
        config_data = st.session_state.agent_config
        if hasattr(config_data, "model_dump"):
            config_data = config_data.model_dump()
        st.json(config_data)
    else:
        st.info("Agent configuration will appear here after creation.")

    if st.button("🔄 Reset All", type="secondary"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
