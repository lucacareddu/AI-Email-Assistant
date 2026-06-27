"""Centralised configuration, loaded from environment variables (.env in dev)."""
import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


class Settings:
    # Gemini API (Google AI Studio)
    gemini_api_key: str = _require("GEMINI_API_KEY")
    chat_model: str = os.environ.get("CHAT_MODEL", "gemini-2.5-flash")
    embedding_model: str = os.environ.get("EMBEDDING_MODEL", "gemini-embedding-001")
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/models"

    # Postgres (set USE_POSTGRES=false to use in-memory storage instead - no
    # DB needed, but data is lost on restart)
    use_postgres: bool = os.environ.get("USE_POSTGRES", "true").lower() == "true"
    database_url: str = _require("DATABASE_URL") if use_postgres else ""

    # Gmail API (direct send of the approved reply via OAuth2 refresh token)
    gmail_client_id: str = _require("GMAIL_CLIENT_ID")
    gmail_client_secret: str = _require("GMAIL_CLIENT_SECRET")
    gmail_refresh_token: str = _require("GMAIL_REFRESH_TOKEN")
    gmail_sender: str = _require("GMAIL_SENDER")

    # Shared secret checked against the X-Webhook-Token header sent by n8n
    webhook_token: str = _require("WEBHOOK_TOKEN")

    # RAG
    documents_path: str = os.environ.get("DOCUMENTS_PATH", "./documents")
    chroma_path: str = os.environ.get("CHROMA_PATH", "./chroma_db")


settings = Settings()
