"""Sets up a complete, valid fake environment before pytest collects any test
module - app/config.py raises at import time if required vars are missing,
so this has to run before any `from app...` import happens anywhere."""
import os

os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
os.environ.setdefault("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
os.environ.setdefault("USE_POSTGRES", "false")
os.environ.setdefault("USE_REDIS", "false")
os.environ.setdefault("GMAIL_CLIENT_ID", "test-client-id")
os.environ.setdefault("GMAIL_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GMAIL_REFRESH_TOKEN", "test-refresh-token")
os.environ.setdefault("GMAIL_SENDER", "test@example.com")
os.environ.setdefault("WEBHOOK_TOKEN", "test-webhook-token")
os.environ.setdefault("CHROMA_PATH", "/tmp/test_chroma_db")
