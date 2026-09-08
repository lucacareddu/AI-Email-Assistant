"""Run this ONCE, locally, to get a Gmail refresh token for .env.

It opens a browser, you log into the Gmail account you want to send from and
approve access, and it prints back the refresh token to paste into .env. The
token doesn't expire (until you revoke access), so this is a one-time step.

Setup (5 minutes, one-time):
1. https://console.cloud.google.com/ -> create/select a project.
2. APIs & Services -> Library -> enable "Gmail API".
3. APIs & Services -> Credentials -> Create Credentials -> OAuth client ID.
   - If prompted, configure the consent screen first: User type "External",
     fill the required fields, and add your own Gmail address under
     "Test users" (this avoids needing Google's app review for personal use).
   - Application type: "Desktop app". This matters - it's the type that
     works with the local-browser flow below without extra configuration.
4. Copy the generated Client ID and Client Secret.

Usage:
    pip install google-auth-oauthlib
    GMAIL_CLIENT_ID=... GMAIL_CLIENT_SECRET=... python -m app.services.refresh_token

Client ID/secret are read from GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET only -
no fallback baked into this file, so nothing here is a credential to leak.
"""
import os

from google_auth_oauthlib.flow import InstalledAppFlow

# Minimal scope: only allows sending mail, nothing else (not reading inbox,
# not full account access).
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


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
    # Opens your browser, you log in + approve, then this captures the result
    # on a local port automatically - no manual code copy/paste needed.
    credentials = flow.run_local_server(port=0)

    print("\nDone. Put these in your .env:\n")
    print(f"GMAIL_CLIENT_ID={client_id}")
    print(f"GMAIL_CLIENT_SECRET={client_secret}")
    print(f"GMAIL_REFRESH_TOKEN={credentials.refresh_token}")


if __name__ == "__main__":
    main()
