import base64
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import settings


def _client():
    creds = Credentials(
        token=None,
        refresh_token=settings.gmail_refresh_token,
        client_id=settings.gmail_client_id,
        client_secret=settings.gmail_client_secret,
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("gmail", "v1", credentials=creds)


def send_reply(to: str, subject: str, body: str) -> str:
    message = MIMEText(body)
    message["to"] = to
    message["from"] = settings.gmail_sender
    message["subject"] = f"Re: {subject}"

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    result = _client().users().messages().send(userId="me", body={"raw": raw}).execute()
    return result["id"]
