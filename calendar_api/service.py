"""
Google Calendar API service layer.

Provides synchronous functions for slot availability and appointment creation,
plus async wrappers that delegate to `asyncio.to_thread` so they never block
the aiogram event loop.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Any

import pytz
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from utils.config import (
    BUSINESS_HOUR_END,
    BUSINESS_HOUR_START,
    GOOGLE_CALENDAR_ID,
    GOOGLE_CREDENTIALS_PATH,
    GOOGLE_TOKEN_PATH,
    SLOT_DURATION_MINUTES,
    TIMEZONE,
)

# ── Constants ─────────────────────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/calendar"]
TZ = pytz.timezone(TIMEZONE)


# ══════════════════════════════════════════════════════════
#  Internal helpers
# ══════════════════════════════════════════════════════════


def _load_credentials() -> Credentials:
    """
    Load credentials from token.json, auto-refreshing if expired.
    Saves the refreshed token back to disk so subsequent calls stay valid.
    """
    if not os.path.exists(GOOGLE_TOKEN_PATH):
        raise FileNotFoundError(
            f"'{GOOGLE_TOKEN_PATH}' not found. "
            "Run `python -m calendar_api.auth_setup` first."
        )

    creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_PATH, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(GOOGLE_TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return creds


def _build_service():
    """Build and return a Google Calendar API service object."""
    creds = _load_credentials()
    return build("calendar", "v3", credentials=creds)


def _generate_all_slots(date_obj: datetime) -> list[datetime]:
    """
    Generate every possible 1-hour slot start time for the given date
    between BUSINESS_HOUR_START and BUSINESS_HOUR_END (exclusive end).

    Example: 09:00, 10:00, 11:00, … 17:00  (last slot is 17:00–18:00)
    """
    slots: list[datetime] = []
    current = TZ.localize(
        date_obj.replace(hour=BUSINESS_HOUR_START, minute=0, second=0, microsecond=0)
    )
    end_boundary = TZ.localize(
        date_obj.replace(hour=BUSINESS_HOUR_END, minute=0, second=0, microsecond=0)
    )

    while current + timedelta(minutes=SLOT_DURATION_MINUTES) <= end_boundary:
        slots.append(current)
        current += timedelta(minutes=SLOT_DURATION_MINUTES)

    return slots


def _parse_date(date_str: str) -> datetime:
    """Parse a YYYY-MM-DD string into a naive datetime at midnight."""
    return datetime.strptime(date_str, "%Y-%m-%d")


# ══════════════════════════════════════════════════════════
#  Public synchronous API
# ══════════════════════════════════════════════════════════


def get_available_slots(date_str: str) -> list[str]:
    """
    Return ONLY the available 1-hour appointment slots for the given date.

    Parameters
    ----------
    date_str : str
        Date in 'YYYY-MM-DD' format.

    Returns
    -------
    list[str]
        Available slot start times as 'HH:MM' strings (e.g. ['09:00', '11:00']).
        Empty list if no slots are available or the date is in the past.
    """
    date_obj = _parse_date(date_str)
    now_istanbul = datetime.now(TZ)

    # Reject dates in the past
    if date_obj.date() < now_istanbul.date():
        return []

    all_slots = _generate_all_slots(date_obj)

    # If querying today, remove slots that have already passed
    if date_obj.date() == now_istanbul.date():
        all_slots = [s for s in all_slots if s > now_istanbul]

    if not all_slots:
        return []

    # Query Google Calendar for existing events on that day
    service = _build_service()
    time_min = all_slots[0].isoformat()
    time_max = (all_slots[-1] + timedelta(minutes=SLOT_DURATION_MINUTES)).isoformat()

    events_result = service.events().list(
        calendarId=GOOGLE_CALENDAR_ID,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = events_result.get("items", [])

    # Build a list of busy intervals from existing events
    busy_intervals: list[tuple[datetime, datetime]] = []
    for event in events:
        start = event["start"].get("dateTime")
        end = event["end"].get("dateTime")
        if start and end:
            busy_start = datetime.fromisoformat(start).astimezone(TZ)
            busy_end = datetime.fromisoformat(end).astimezone(TZ)
            busy_intervals.append((busy_start, busy_end))

    # Filter: keep only slots that don't overlap with any busy interval
    available: list[str] = []
    for slot_start in all_slots:
        slot_end = slot_start + timedelta(minutes=SLOT_DURATION_MINUTES)
        is_busy = any(
            slot_start < busy_end and slot_end > busy_start
            for busy_start, busy_end in busy_intervals
        )
        if not is_busy:
            available.append(slot_start.strftime("%H:%M"))

    return available


def create_appointment(
    date_str: str,
    time_str: str,
    full_name: str,
    topic: str,
    phone_number: str,
) -> dict[str, Any]:
    """
    Create a 1-hour appointment on Google Calendar.

    Parameters
    ----------
    date_str : str
        Date in 'YYYY-MM-DD' format.
    time_str : str
        Start time in 'HH:MM' format (Europe/Istanbul).
    full_name : str
        Full name of the person booking.
    topic : str
        Subject / reason for the appointment.
    phone_number : str
        Contact phone number.

    Returns
    -------
    dict
        The created Google Calendar event resource with 'id' and 'htmlLink'.
    """
    date_obj = _parse_date(date_str)
    hour, minute = map(int, time_str.split(":"))

    start_dt = TZ.localize(
        date_obj.replace(hour=hour, minute=minute, second=0, microsecond=0)
    )
    end_dt = start_dt + timedelta(minutes=SLOT_DURATION_MINUTES)

    event_body = {
        "summary": f"Appointment — {full_name}",
        "description": (
            f"👤 Name: {full_name}\n"
            f"📋 Topic: {topic}\n"
            f"📞 Phone: {phone_number}\n"
            f"🤖 Booked via Telegram Scheduling Agent"
        ),
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": TIMEZONE,
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": TIMEZONE,
        },
    }

    service = _build_service()
    created_event = (
        service.events()
        .insert(calendarId=GOOGLE_CALENDAR_ID, body=event_body)
        .execute()
    )

    return {
        "status": "confirmed",
        "event_id": created_event.get("id"),
        "link": created_event.get("htmlLink"),
        "start": start_dt.strftime("%Y-%m-%d %H:%M"),
        "end": end_dt.strftime("%Y-%m-%d %H:%M"),
    }


# ══════════════════════════════════════════════════════════
#  Async wrappers  (safe for aiogram / async LangChain)
# ══════════════════════════════════════════════════════════


async def async_get_available_slots(date_str: str) -> list[str]:
    """Non-blocking wrapper around `get_available_slots`."""
    return await asyncio.to_thread(get_available_slots, date_str)


async def async_create_appointment(
    date_str: str,
    time_str: str,
    full_name: str,
    topic: str,
    phone_number: str,
) -> dict[str, Any]:
    """Non-blocking wrapper around `create_appointment`."""
    return await asyncio.to_thread(
        create_appointment, date_str, time_str, full_name, topic, phone_number
    )
