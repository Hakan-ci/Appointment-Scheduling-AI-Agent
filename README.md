# 🗓️ Telegram Appointment Scheduling AI Agent

A production-ready, modular AI-powered appointment scheduling bot built with **Python**, **LangGraph**, **GPT-4o-mini**, and **Google Calendar API**. Users interact naturally via Telegram to check availability and book 1-hour appointments — fully hands-free.

---

## ✨ Features

- **Natural Language Scheduling** — Understands free-form messages in any language via GPT-4o-mini
- **Google Calendar Integration** — Real-time availability checks and automatic event creation via OAuth2
- **Anti-Hallucination Design** — The LLM only ever sees available slots, never raw calendar data
- **Stateful Conversations** — LangGraph + MemorySaver preserves context across async Telegram messages
- **Smart Conflict Handling** — Automatically proposes 2 alternative slots when a requested time is booked
- **Explicit Confirmation** — Always asks for user approval before finalizing a booking
- **Timezone-Strict** — All datetime logic is anchored to `Europe/Istanbul` (configurable)
- **Async-Safe** — Synchronous Google API calls are wrapped with `asyncio.to_thread` to never block the event loop

---

## 🏗️ Architecture

```
User (Telegram)
      │
      ▼
┌──────────────┐     ┌─────────────────────────────────────────────┐
│  aiogram Bot │────▶│              LangGraph Agent                │
│  (bot/)      │◀────│  ┌─────────┐    ┌───────────┐              │
└──────────────┘     │  │  Agent  │◀──▶│   Tools   │              │
                     │  │  Node   │    │   Node    │              │
                     │  │ (GPT-4o │    │           │              │
                     │  │  -mini) │    │ ┌───────┐ │              │
                     │  └─────────┘    │ │Check  │ │              │
                     │                 │ │ Slots │ │              │
                     │  MemorySaver    │ ├───────┤ │              │
                     │  (per user)     │ │ Book  │ │              │
                     │                 │ │ Appt  │ │              │
                     │                 │ └───────┘ │              │
                     │                 └─────┬─────┘              │
                     └───────────────────────┼────────────────────┘
                                             │
                                             ▼
                                   ┌──────────────────┐
                                   │  Google Calendar  │
                                   │       API         │
                                   └──────────────────┘
```

---

## 📁 Project Structure

```
Appointment-Scheduling-AI-Agent/
│
├── agent/                      # LangGraph state machine & LLM orchestration
│   ├── __init__.py
│   ├── graph.py                # State definition, nodes, conditional edges, compiled graph
│   └── tools.py                # Pydantic input schemas & LangChain tool definitions
│
├── bot/                        # Telegram bot (aiogram 3.x)
│   ├── __init__.py
│   └── main.py                 # Dispatcher, handlers, message routing
│
├── calendar_api/               # Google Calendar OAuth2 integration
│   ├── __init__.py
│   ├── auth_setup.py           # One-time OAuth2 browser consent flow
│   └── service.py              # Slot availability logic & appointment creation
│
├── utils/                      # Shared configuration & helpers
│   ├── __init__.py
│   └── config.py               # Centralized settings loaded from .env
│
├── .env.example                # Template for required environment variables
├── .gitignore                  # Ignores venv, .env, credentials.json, token.json
├── requirements.txt            # Pinned Python dependencies
├── run.py                      # Top-level entry point
└── README.md
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Bot Interface** | [aiogram 3.x](https://docs.aiogram.dev/) | Async Telegram bot framework |
| **LLM** | [GPT-4o-mini](https://platform.openai.com/docs/models) via LangChain | Natural language understanding & response generation |
| **State Machine** | [LangGraph](https://langchain-ai.github.io/langgraph/) | Cyclic agent graph with persistent checkpointing |
| **Calendar** | [Google Calendar API v3](https://developers.google.com/calendar) | Availability checks & event creation |
| **Auth** | [google-auth-oauthlib](https://google-auth.readthedocs.io/) | OAuth2 with automatic token refresh |
| **Validation** | [Pydantic](https://docs.pydantic.dev/) | Strict input schemas for LLM tools |
| **Timezone** | [pytz](https://pythonhosted.org/pytz/) | Europe/Istanbul timezone enforcement |

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- A **Telegram Bot Token** from [@BotFather](https://t.me/BotFather)
- An **OpenAI API Key** from [platform.openai.com](https://platform.openai.com/api-keys)
- A **Google Cloud Project** with the Calendar API enabled and OAuth 2.0 credentials

### 1. Clone & Set Up Environment

```bash
git clone https://github.com/your-username/Appointment-Scheduling-AI-Agent.git
cd Appointment-Scheduling-AI-Agent

python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your actual credentials:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
GOOGLE_CALENDAR_ID=your_email@gmail.com
```

### 3. Set Up Google Calendar OAuth2

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable the **Google Calendar API**
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
5. Select **Desktop App**, download the JSON file
6. Rename it to `credentials.json` and place it in the project root

Then run the one-time authorization flow:

```bash
python -m calendar_api.auth_setup
```

A browser window will open — sign in and authorize Calendar access. This generates `token.json` (auto-refreshes on subsequent runs).

### 4. Start the Bot

```bash
python run.py
```

You should see:

```
Bot is starting...
Start polling
Run polling for bot @your_bot_name ...
```

Open Telegram, search for your bot, and send `/start`!

---

## 💬 Usage Example

```
User:  /start
Bot:   👋 Welcome! I'm your appointment scheduling assistant...

User:  I'd like to book an appointment for tomorrow at 2pm
Bot:   Let me check availability for tomorrow...
       ✅ 14:00 is available! I'll need a few more details:
       - Your full name
       - The topic/reason for the appointment
       - Your phone number

User:  John Doe, project review, +90 555 123 4567
Bot:   Here's a summary of your appointment:
       📅 Date: 2026-05-15
       🕐 Time: 14:00 – 15:00
       👤 Name: John Doe
       📋 Topic: Project Review
       📞 Phone: +90 555 123 4567

       Shall I go ahead and book this?

User:  Yes
Bot:   ✅ Appointment successfully booked!
       📅 Date & Time: 2026-05-15 14:00 – 2026-05-15 15:00
       🔗 Calendar Link: https://calendar.google.com/...
```

---

## 🔧 Configuration

All settings are centralized in `utils/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `TIMEZONE` | `Europe/Istanbul` | All datetime operations use this timezone |
| `BUSINESS_HOUR_START` | `9` | First available slot (09:00) |
| `BUSINESS_HOUR_END` | `18` | End boundary (last slot: 17:00–18:00) |
| `SLOT_DURATION_MINUTES` | `60` | Each appointment is 1 hour |

---

## 🔒 Security Notes

- **`credentials.json`** and **`token.json`** are in `.gitignore` — never committed
- **`.env`** is in `.gitignore` — API keys stay local
- OAuth2 tokens auto-refresh; no manual re-authorization needed after initial setup
- The bot only accesses Calendar events for availability checks — no data is exposed to the LLM





<p align="center">
  Built with using LangGraph, GPT-4o-mini & Google Calendar API
</p>
