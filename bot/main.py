"""
Telegram Bot — aiogram 3.x entry point.

Handles incoming messages, routes them through the LangGraph agent,
and sends the AI response back to the user.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from langchain_core.messages import HumanMessage

from agent.graph import agent_graph
from utils.config import TELEGRAM_BOT_TOKEN

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ── Bot & Router ──────────────────────────────────────────
bot = Bot(token=TELEGRAM_BOT_TOKEN)
router = Router()

# Telegram message length limit
TG_MAX_LENGTH = 4096


# ══════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════


def _extract_ai_text(result: dict) -> str:
    """
    Extract the final AI response text from the LangGraph result.

    The result dict contains {"messages": [...]}, and we want the
    content of the last AI message (skipping tool messages).
    """
    messages = result.get("messages", [])

    # Walk backwards to find the last non-tool AI message
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.content and msg.type == "ai":
            # Skip messages that are purely tool calls with no user-facing text
            if not msg.tool_calls or msg.content.strip():
                return msg.content

    return "I'm sorry, I couldn't process that. Please try again."


async def _send_long_message(message: types.Message, text: str) -> None:
    """
    Send a message, splitting into chunks if it exceeds Telegram's
    4096-character limit.
    """
    if len(text) <= TG_MAX_LENGTH:
        await message.answer(text)
        return

    # Split on newlines to avoid breaking mid-word
    chunks: list[str] = []
    current_chunk = ""
    for line in text.split("\n"):
        if len(current_chunk) + len(line) + 1 > TG_MAX_LENGTH:
            chunks.append(current_chunk)
            current_chunk = line
        else:
            current_chunk = f"{current_chunk}\n{line}" if current_chunk else line

    if current_chunk:
        chunks.append(current_chunk)

    for chunk in chunks:
        await message.answer(chunk)


# ══════════════════════════════════════════════════════════
#  Handlers
# ══════════════════════════════════════════════════════════


@router.message(CommandStart())
async def handle_start(message: types.Message) -> None:
    """Handle /start command — greet the user."""
    await message.answer(
        "👋 Welcome! I'm your appointment scheduling assistant.\n\n"
        "I can help you book a 1-hour appointment. Just tell me:\n"
        "• The date and time you'd like\n"
        "• Your full name\n"
        "• The topic / reason\n"
        "• Your phone number\n\n"
        "Let's get started! When would you like to schedule your appointment?"
    )


@router.message()
async def handle_message(message: types.Message) -> None:
    """
    Handle any text message — invoke the LangGraph agent and reply.

    The Telegram chat_id is used as the LangGraph thread_id so each
    user gets an isolated, persistent conversation state.
    """
    if not message.text:
        await message.answer("Please send a text message.")
        return

    user_id = str(message.chat.id)
    logger.info("User %s: %s", user_id, message.text[:100])

    try:
        # Invoke the LangGraph agent with the user's message
        result = await agent_graph.ainvoke(
            {"messages": [HumanMessage(content=message.text)]},
            config={"configurable": {"thread_id": user_id}},
        )

        ai_text = _extract_ai_text(result)
        logger.info("Agent → User %s: %s", user_id, ai_text[:100])

        await _send_long_message(message, ai_text)

    except Exception:
        logger.exception("Error processing message from user %s", user_id)
        await message.answer(
            "⚠️ Something went wrong while processing your request. "
            "Please try again in a moment."
        )


# ══════════════════════════════════════════════════════════
#  Entry Point
# ══════════════════════════════════════════════════════════


async def main() -> None:
    """Start the bot with long-polling."""
    logger.info("Bot is starting...")

    dp = Dispatcher()
    dp.include_router(router)

    # Delete any pending webhook and start polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
