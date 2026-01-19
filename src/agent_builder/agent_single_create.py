import uuid
import re
from langchain_core.tools import tool
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from src.utils.logger import logger
from src.agent_builder.models import AgentConfig


def sanitize_tool_name(name: str) -> str:
    """Sanitize tool name to match OpenAI's requirements.

    OpenAI requires tool names to match pattern: ^[a-zA-Z0-9_-]+$

    Args:
        name: Original name (may contain spaces, Chinese characters, etc.)

    Returns:
        Sanitized name containing only letters, numbers, underscores, and hyphens
    """
    # Convert to lowercase and replace spaces with underscores
    sanitized = name.lower().replace(" ", "_")

    # Remove all characters that are not alphanumeric, underscore, or hyphen
    sanitized = re.sub(r'[^a-z0-9_-]', '', sanitized)

    # If the result is empty or starts with a number, prefix with "skill_"
    if not sanitized or sanitized[0].isdigit():
        sanitized = f"skill_{sanitized}"

    # Ensure it's not empty after cleaning
    if not sanitized:
        sanitized = "skill_tool"

    return sanitized


def create_agent_from_config(agent_config: AgentConfig):
    """Create a dynamic agent using Agent as a Tool pattern.

    The skill is wrapped as a tool that the main agent can invoke.

    Args:
        agent_config: The AgentConfig object containing agent and skill definitions

    Returns:
        A configured agent with skill agent wrapped as a tool
    """
    logger.info("\n" + "=" * 80)
    logger.info("🔨 Creating Dynamic Agent from Configuration (Agent as a Tool)")
    logger.info("=" * 80)

    # Extract config data
    if isinstance(agent_config, AgentConfig):
        config_data = agent_config.model_dump()
    else:
        config_data = agent_config

    agent_name = config_data.get("name")
    agent_description = config_data.get("description")
    system_prompt = config_data.get("system_prompt")
    skills = config_data.get("skills", [])

    logger.info(f"📝 Agent Name: {agent_name}")
    logger.info(f"📝 Agent Description: {agent_description}")
    logger.info(f"📝 Skills Count: {len(skills)}")

    # Create skill agent tools
    skill_agent_tools = []

    def create_mock_tool(tool_name: str, tool_config: dict):
        """Create a mock tool that returns a simulated response.

        Note: tool_name should come from AVAILABLE_TOOLS and already be valid,
        but we sanitize it anyway for safety.
        """
        @tool
        def mock_tool(query: str) -> str:
            """Mock tool that simulates tool execution.

            Args:
                query: The query or parameters for this tool

            Returns:
                Mock response from the tool
            """
            return f"[Mock Response from {tool_name}] Successfully processed: {query}"

        # Sanitize tool name to ensure it matches OpenAI's requirements
        mock_tool.name = sanitize_tool_name(tool_name)
        mock_tool.description = f"Tool: {tool_name}. Config: {tool_config}"
        return mock_tool

    def create_skill_agent_tool(skill_name: str, skill_when_to_use: str, skill_prompt: str, skill_tools_config: list):
        """Factory function to create skill agent tool with proper closure."""
        # Create mock tools for the skill agent
        mock_tools = []
        for tool_config in skill_tools_config:
            tool_name = tool_config.get("name")
            tool_cfg = tool_config.get("config", {})
            mock_tool = create_mock_tool(tool_name, tool_cfg)
            mock_tools.append(mock_tool)
            logger.info(f"        - Created mock tool: {tool_name}")

        # Create the skill agent with mock tools
        skill_agent = create_agent(
            model=init_chat_model(model="openai:gpt-4o"),
            tools=mock_tools,
            system_prompt=skill_prompt,
        )

        # Wrap skill agent as a tool
        @tool
        def skill_tool(query: str) -> str:
            """Skill agent tool that processes user queries.

            Args:
                query: The user's question or request

            Returns:
                The skill agent's response
            """
            result = skill_agent.invoke({"messages": [{"role": "user", "content": query}]})
            return result["messages"][-1].content

        # Update tool metadata
        skill_tool.name = sanitize_tool_name(skill_name)
        skill_tool.description = f"Use this tool when: {skill_when_to_use}"

        return skill_tool

    for skill in skills:
        skill_name = skill.get("name")
        skill_when_to_use = skill.get("when_to_use")
        skill_prompt = skill.get("prompt")
        skill_tools_config = skill.get("tools", [])

        logger.info(f"\n  🔧 Creating Skill Agent as Tool: {skill_name}")
        logger.info(f"     - When to use: {skill_when_to_use}")
        logger.info(f"     - Tools config: {len(skill_tools_config)} tool(s)")

        # Create skill agent tool using factory function
        skill_agent_tool = create_skill_agent_tool(skill_name, skill_when_to_use, skill_prompt, skill_tools_config)

        skill_agent_tools.append(skill_agent_tool)
        logger.info(f"     ✅ Skill agent wrapped as tool: {skill_agent_tool.name}")

    # Create the main agent with skill agent tools
    logger.info(f"\n🚀 Creating main agent: {agent_name}")
    logger.info(f"   - Available tools: {[t.name for t in skill_agent_tools]}")

    dynamic_agent = create_agent(
        model=init_chat_model(model="openai:gpt-4o"),
        tools=skill_agent_tools,
        system_prompt=system_prompt,
        checkpointer=InMemorySaver(),
    )

    logger.info("✅ Dynamic agent created successfully!")
    logger.info("=" * 80)

    return dynamic_agent


if __name__ == "__main__":
    # Test the function
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
