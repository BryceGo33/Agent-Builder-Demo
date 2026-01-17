from typing import List, Literal, Dict, Any
from typing_extensions import TypedDict, NotRequired
from pydantic import BaseModel, Field


class ConfirmInfo(TypedDict):
    """Confirm option configuration."""

    confirm_message: str
    """The confirm message to show to the user, e.g, `Do you want to start to build workflow or add more details?`."""

    confirm_type: Literal["single_choice", "multiple_choice", "text"]
    """The confirm type, e.g, `single_choice`, `multiple_choice`, `text`."""

    options: NotRequired[List[str]] = []
    """The confirm options, e.g, `build workflow`, `add details`."""


class Tool(BaseModel):
    """Tool configuration for a skill."""

    name: str = Field(..., description="Tool name")
    config: Dict[str, Any] = Field(default_factory=dict, description="Tool configuration parameters")


class Skill(BaseModel):
    """Skill is also a single agent."""

    name: str = Field(..., min_length=1, max_length=50, description="Skill name")
    when_to_use: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Usage scenario description, used for skill routing judgment"
    )
    prompt: str = Field(..., min_length=10, description="Skill-specific prompt")
    tools: List[Tool] = Field(default_factory=list, description="Bound tool list")


class AgentConfig(BaseModel):
    """Agent configuration schema."""

    name: str = Field(..., min_length=1, max_length=100, description="Agent name")
    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Agent function description"
    )
    system_prompt: str = Field(
        ...,
        min_length=10,
        description="System prompt defining agent role and behavior"
    )
    skills: List[Skill] = Field(..., min_items=1, max_items=1, description="Skill list. Current only support just one skill")


# Available system tools for agent building
AVAILABLE_TOOLS = [
    {
        "tool_id": "sms",
        "name": "send_sms",
        "description": "Send SMS to user (voice scenario)",
        "config_required": []
    },
    {
        "tool_id": "email",
        "name": "send_email",
        "description": "Send email to user",
        "config_required": []
    },
    {
        "tool_id": "google_calendar",
        "name": "google_calendar",
        "description": "Read and write Google Calendar (requires calendar configuration at skill level)",
        "config_required": ["calendar_id"]
    },
    {
        "tool_id": "google_sheet",
        "name": "google_sheet",
        "description": "Read and write Google Sheets (requires sheet configuration at skill level)",
        "config_required": ["sheet_id"]
    },
    {
        "tool_id": "shopify",
        "name": "shopify",
        "description": "Product recommendation from Shopify",
        "config_required": []
    },
    {
        "tool_id": "amazon",
        "name": "amazon",
        "description": "Get product information from Amazon",
        "config_required": []
    },
    {
        "tool_id": "rakuten",
        "name": "rakuten",
        "description": "E-commerce platform integration",
        "config_required": []
    },
    {
        "tool_id": "logistics_tracking",
        "name": "logistics_tracking",
        "description": "Track logistics and shipping information",
        "config_required": []
    },
    {
        "tool_id": "knowledge_search",
        "name": "knowledge_search",
        "description": "Knowledge-based reply (special: toggle switch in agent interface)",
        "config_required": []
    },
    {
        "tool_id": "transfer",
        "name": "transfer_to_human",
        "description": "Transfer to human agent",
        "config_required": []
    },
]
