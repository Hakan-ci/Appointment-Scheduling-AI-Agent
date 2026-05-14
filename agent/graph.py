"""
LangGraph agent graph — cyclic state machine for appointment scheduling.

Architecture:
    START → agent_node ←→ tool_node → END
                ↑               |
                └───────────────┘

The graph uses MemorySaver so conversation state persists across
asynchronous Telegram messages, keyed by the user's chat_id.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from langchain_core.messages import AnyMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

import pytz

from agent.tools import all_tools
from utils.config import OPENAI_API_KEY, TIMEZONE


# ══════════════════════════════════════════════════════════
#  State Definition
# ══════════════════════════════════════════════════════════


class AgentState(TypedDict):
    """
    Graph state shared across all nodes.

    The `add_messages` reducer appends new messages to the list
    instead of overwriting, preserving full conversation history.
    """

    messages: Annotated[list[AnyMessage], add_messages]


# ══════════════════════════════════════════════════════════
#  LLM Setup
# ══════════════════════════════════════════════════════════

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    api_key=OPENAI_API_KEY,
)

# Bind tools so the LLM can generate tool_calls in its responses
llm_with_tools = llm.bind_tools(all_tools)


# ══════════════════════════════════════════════════════════
#  System Prompt (dynamic timezone-aware)
# ══════════════════════════════════════════════════════════

SYSTEM_PROMPT_TEMPLATE = """You are a professional and friendly appointment scheduling assistant. Your job is to help users book 1-hour appointments.

**Current Date & Time (Europe/Istanbul):** {current_datetime}

## RULES — follow these strictly:

1. **Appointment slots** are 1 hour long, available between 09:00 and 18:00 (Europe/Istanbul timezone), Monday to Friday.
2. You must collect ALL of the following before booking:
   - **Date** (must be a future date)
   - **Time** (must be an available slot — always verify with `check_available_slots`)
   - **Full Name**
   - **Topic / Reason** for the appointment
   - **Phone Number**
3. **ALWAYS** call `check_available_slots` before confirming a time. NEVER guess availability.
4. If the requested slot is NOT available, propose **2 alternative available slots** from the same day (or suggest another day if the day is fully booked).
5. Before finalizing the booking, **summarize all details** and ask the user for **explicit confirmation** (e.g., "Shall I go ahead and book this?").
6. **ONLY** call `book_appointment` after receiving the user's explicit "yes" / confirmation.
7. Be concise, polite, and professional. Use emojis sparingly for warmth.
8. If the user provides information in any language, respond in the SAME language.
9. Do NOT fabricate information. If you are unsure, ask the user.

## PLACEHOLDER NOTE
This is a placeholder system prompt. The exact prompt text will be provided by the user later and will replace this section.
"""


def _build_system_message() -> SystemMessage:
    """
    Build the system prompt with the current date/time injected dynamically.
    Called on every agent invocation so the LLM always knows "now".
    """
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    current_dt_str = now.strftime("%A, %Y-%m-%d %H:%M %Z")

    return SystemMessage(
        content=SYSTEM_PROMPT_TEMPLATE.format(current_datetime=current_dt_str)
    )


# ══════════════════════════════════════════════════════════
#  Graph Nodes
# ══════════════════════════════════════════════════════════


async def agent_node(state: AgentState) -> dict:
    """
    LLM processing node.

    Prepends a fresh system message (with current time) to the
    conversation history, invokes the LLM, and returns its response.
    """
    system_msg = _build_system_message()
    messages = [system_msg] + state["messages"]

    response = await llm_with_tools.ainvoke(messages)

    return {"messages": [response]}


# Pre-built node that automatically executes any tool_calls
tool_node = ToolNode(all_tools)


# ══════════════════════════════════════════════════════════
#  Conditional Edge
# ══════════════════════════════════════════════════════════


def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    """
    Route after the agent node:
      - If the last message has tool_calls → go to tool_node
      - Otherwise → END (return response to user)
    """
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    return "__end__"


# ══════════════════════════════════════════════════════════
#  Graph Compilation
# ══════════════════════════════════════════════════════════

# Checkpointer persists state across async Telegram messages
checkpointer = MemorySaver()


def build_graph() -> StateGraph:
    """
    Construct and compile the agent graph.

    Returns the compiled graph ready for `.ainvoke()`.
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    # Entry point
    graph.set_entry_point("agent")

    # Conditional edge: agent → tools or END
    graph.add_conditional_edges("agent", should_continue)

    # After tools execute, loop back to agent for follow-up
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=checkpointer)


# Singleton compiled graph — imported by the Telegram bot
agent_graph = build_graph()
