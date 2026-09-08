"""Run once, locally, to mint a Gmail refresh token for .env.

Setup: console.cloud.google.com -> enable Gmail API -> OAuth client ID
(type "Desktop app") -> copy Client ID/Secret.

Usage:
    pip install google-auth-oauthlib
    GMAIL_CLIENT_ID=... GMAIL_CLIENT_SECRET=... python -m app.services.refresh_token
"""
import os

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]  # send-only


def main():
    client_id = os.environ.get("GMAIL_CLIENT_ID")
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit(
            "Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET (from step 4 above) "
            "before running this, e.g.:\n"
            "  GMAIL_CLIENT_ID=... GMAIL_CLIENT_SECRET=... python -m app.services.refresh_token"
        )

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost:5678/rest/oauth2-credential/callback"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    credentials = flow.run_local_server(port=0)  # opens browser, captures result locally

    print("\nDone. Put these in your .env:\n")
    print(f"GMAIL_CLIENT_ID={client_id}")
    print(f"GMAIL_CLIENT_SECRET={client_secret}")
    print(f"GMAIL_REFRESH_TOKEN={credentials.refresh_token}")


if __name__ == "__main__":
    main()
