"""
calendar_api — Google Calendar OAuth2 integration & slot management.

Public API:
    get_available_slots(date_str)           Sync
    create_appointment(...)                 Sync
    async_get_available_slots(date_str)     Async (asyncio.to_thread)
    async_create_appointment(...)           Async (asyncio.to_thread)
"""

from calendar_api.service import (
    async_create_appointment,
    async_get_available_slots,
    create_appointment,
    get_available_slots,
)

__all__ = [
    "get_available_slots",
    "create_appointment",
    "async_get_available_slots",
    "async_create_appointment",
]
