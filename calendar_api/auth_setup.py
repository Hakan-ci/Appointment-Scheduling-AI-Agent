"""
One-time OAuth2 setup script.

Run this locally ONCE to authorize the app with your Google account.
It opens a browser window for consent, then saves the refresh token
to 'token.json' so the bot can authenticate headlessly from then on.

Usage:
    python -m calendar_api.auth_setup
"""

import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

# Add project root to path so we can import utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH

# Full read/write access to Google Calendar
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def run_oauth_flow() -> None:
    """Run the interactive OAuth2 consent flow and persist the token."""

    if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
        print(
            f"ERROR: '{GOOGLE_CREDENTIALS_PATH}' not found.\n"
            "Download it from Google Cloud Console → APIs & Services → Credentials → "
            "OAuth 2.0 Client IDs → Download JSON, then place it in the project root."
        )
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(
        GOOGLE_CREDENTIALS_PATH, scopes=SCOPES
    )

    # Opens a local HTTP server on port 0 (auto-pick) and launches the browser
    credentials = flow.run_local_server(port=0)

    # Persist the token (includes refresh_token) for headless use
    with open(GOOGLE_TOKEN_PATH, "w") as token_file:
        token_file.write(credentials.to_json())

    print(f"✅ Authorization successful! Token saved to '{GOOGLE_TOKEN_PATH}'.")


if __name__ == "__main__":
    run_oauth_flow()
