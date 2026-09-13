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


def send_reply(to: str, subject: str, body: str, message_id: str | None = None, thread_id: str | None = None) -> str:
    """message_id/thread_id (from the original Gmail message) thread the reply into the
    existing conversation instead of landing as a new, unrelated email."""
    message = MIMEText(body)
    message["to"] = to
    message["from"] = settings.gmail_sender
    message["subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    if message_id:
        message["In-Reply-To"] = message_id
        message["References"] = message_id

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    send_body = {"raw": raw}
    if thread_id:
        send_body["threadId"] = thread_id

    result = _client().users().messages().send(userId="me", body=send_body).execute()
    return result["id"]
