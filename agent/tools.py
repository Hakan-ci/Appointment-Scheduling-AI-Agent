"""
LangChain tools backed by the Google Calendar service layer.

Each tool has a Pydantic input schema with strict validation and detailed
docstrings so the LLM understands *when* and *how* to invoke them.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from calendar_api.service import async_create_appointment, async_get_available_slots


# ══════════════════════════════════════════════════════════
#  Pydantic Input Schemas
# ══════════════════════════════════════════════════════════


class CheckAvailableSlotsInput(BaseModel):
    """Input schema for checking available appointment slots."""

    date: str = Field(
        ...,
        description=(
            "The date to check for available appointment slots. "
            "Must be in 'YYYY-MM-DD' format (e.g. '2026-05-15'). "
            "Cannot be a date in the past."
        ),
    )


class BookAppointmentInput(BaseModel):
    """Input schema for booking an appointment on Google Calendar."""

    date: str = Field(
        ...,
        description="Appointment date in 'YYYY-MM-DD' format (e.g. '2026-05-15').",
    )
    time: str = Field(
        ...,
        description=(
            "Appointment start time in 'HH:MM' 24-hour format (e.g. '14:00'). "
            "Must be one of the available slots returned by check_available_slots."
        ),
    )
    full_name: str = Field(
        ...,
        description="Full name of the person booking the appointment.",
    )
    topic: str = Field(
        ...,
        description="Subject or reason for the appointment.",
    )
    phone_number: str = Field(
        ...,
        description="Contact phone number of the person booking.",
    )


# ══════════════════════════════════════════════════════════
#  LangChain Tool Definitions
# ══════════════════════════════════════════════════════════


@tool("check_available_slots", args_schema=CheckAvailableSlotsInput)
async def check_available_slots(date: str) -> str:
    """
    Check which 1-hour appointment slots are available on a given date.

    Use this tool WHENEVER the user asks about availability or wants to
    book an appointment. Always call this BEFORE booking to verify the
    requested slot is actually free.

    Returns a list of available time slots in 'HH:MM' format,
    or a message indicating no slots are available.
    """
    slots = await async_get_available_slots(date)

    if not slots:
        return (
            f"No available appointment slots on {date}. "
            "Please ask the user to choose a different date."
        )

    slots_formatted = ", ".join(slots)
    return (
        f"Available 1-hour appointment slots on {date}: {slots_formatted}. "
        "Each slot is 1 hour long (e.g. 09:00 means 09:00–10:00)."
    )


@tool("book_appointment", args_schema=BookAppointmentInput)
async def book_appointment(
    date: str,
    time: str,
    full_name: str,
    topic: str,
    phone_number: str,
) -> str:
    """
    Book a 1-hour appointment on Google Calendar.

    Use this tool ONLY after:
    1. You have confirmed the slot is available via check_available_slots.
    2. You have collected ALL required information: date, time, full_name,
       topic, and phone_number.
    3. The user has given EXPLICIT confirmation to proceed with the booking.

    Do NOT call this tool without the user's final confirmation.
    """
    result: dict[str, Any] = await async_create_appointment(
        date_str=date,
        time_str=time,
        full_name=full_name,
        topic=topic,
        phone_number=phone_number,
    )

    if result.get("status") == "confirmed":
        return (
            f"✅ Appointment successfully booked!\n"
            f"📅 Date & Time: {result['start']} – {result['end']}\n"
            f"🔗 Calendar Link: {result['link']}"
        )

    return "❌ Failed to book the appointment. Please try again."


# ── Collect all tools for the agent ───────────────────────
all_tools = [check_available_slots, book_appointment]
