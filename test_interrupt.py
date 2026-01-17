"""Test script to understand interrupt data structure."""
import uuid
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt
from langchain_core.tools import tool
from deepagents import create_deep_agent

load_dotenv()

# Define a simple interrupt tool
@tool
def ask_user_to_provide_info(confirm_message: str):
    """Ask user to provide information

    Args:
        confirm_message: Message to ask user

    Returns:
        interrupt
    """
    return interrupt(
        {
            "tool": "ask_user_to_provide_info",
            "confirm_message": confirm_message,
        }
    )

# Create a simple agent with interrupt tool
model = init_chat_model(model="openai:gpt-4o-mini")
checkpointer = InMemorySaver()

agent = create_deep_agent(
    model=model,
    checkpointer=checkpointer,
    tools=[ask_user_to_provide_info],
    system_prompt="You are a test agent. When user asks for help, use ask_user_to_provide_info to ask them for more details.",
)

config = {"configurable": {"thread_id": str(uuid.uuid4())}}

print("=" * 80)
print("Testing interrupt data structure")
print("=" * 80)

# Invoke agent with a message that should trigger interrupt
try:
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "I need help"}]},
        config=config
    )
    print("\n✅ Agent completed without interrupt")
    print(f"Result: {result}")
except Exception as e:
    print(f"\n❌ Error during invoke: {e}")

# Get state to check for interrupt
state = agent.get_state(config)

print("\n" + "=" * 80)
print("State Analysis")
print("=" * 80)
print(f"state.next: {state.next}")
print(f"Has __interrupt__: {'__interrupt__' in state.next if state.next else False}")

if state.tasks:
    print(f"\nNumber of tasks: {len(state.tasks)}")
    for i, task in enumerate(state.tasks):
        print(f"\n--- Task {i} ---")
        print(f"Task type: {type(task)}")
        print(f"Task attributes: {dir(task)}")

        if hasattr(task, 'interrupts'):
            print(f"Has interrupts: True")
            print(f"Number of interrupts: {len(task.interrupts)}")

            for j, interrupt_item in enumerate(task.interrupts):
                print(f"\n  --- Interrupt {j} ---")
                print(f"  Interrupt type: {type(interrupt_item)}")
                print(f"  Interrupt attributes: {[attr for attr in dir(interrupt_item) if not attr.startswith('_')]}")

                # Try different ways to access payload
                if hasattr(interrupt_item, 'value'):
                    print(f"  Has .value: {interrupt_item.value}")
                if hasattr(interrupt_item, 'data'):
                    print(f"  Has .data: {interrupt_item.data}")
                if hasattr(interrupt_item, 'payload'):
                    print(f"  Has .payload: {interrupt_item.payload}")

                # Try to access as dict
                if isinstance(interrupt_item, dict):
                    print(f"  Is dict: {interrupt_item}")

                # Try to convert to dict
                if hasattr(interrupt_item, '__dict__'):
                    print(f"  __dict__: {interrupt_item.__dict__}")
        else:
            print(f"Has interrupts: False")
else:
    print("\n⚠️ No tasks in state")

print("\n" + "=" * 80)
print("Values in state")
print("=" * 80)
if state.values:
    print(f"State values keys: {state.values.keys()}")
    if 'messages' in state.values:
        print(f"Number of messages: {len(state.values['messages'])}")
        for msg in state.values['messages']:
            print(f"  - {msg.type}: {msg.content[:100] if hasattr(msg, 'content') else 'N/A'}")
