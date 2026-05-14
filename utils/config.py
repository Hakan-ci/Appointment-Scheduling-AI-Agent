"""
Centralized configuration — loads .env and exposes typed settings.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# ── Telegram ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ── OpenAI ────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# ── Google Calendar ───────────────────────────────────────
GOOGLE_CALENDAR_ID: str = os.getenv("GOOGLE_CALENDAR_ID", "")
GOOGLE_CREDENTIALS_PATH: str = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
GOOGLE_TOKEN_PATH: str = os.getenv("GOOGLE_TOKEN_PATH", "token.json")

# ── Timezone ──────────────────────────────────────────────
TIMEZONE: str = "Europe/Istanbul"

# ── Business Hours ────────────────────────────────────────
BUSINESS_HOUR_START: int = 9   # 09:00
BUSINESS_HOUR_END: int = 18   # 18:00
SLOT_DURATION_MINUTES: int = 60
