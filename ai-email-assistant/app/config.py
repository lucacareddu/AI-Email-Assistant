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
    # --- GitHub Models (LLM) ---
    github_token: str = os.environ.get("GITHUB_TOKEN", "")
    # GitHub Models via the Azure AI Inference SDK (raw HTTP to this endpoint
    # wasn't working reliably - the SDK handles auth/redirects correctly).
    github_endpoint: str = os.environ.get("GITHUB_ENDPOINT", "https://models.inference.ai.azure.com")

    # --- Gemini API (Google AI Studio) ---
    gemini_api_key: str = os.environ.get("GEMINI_API_KEY", "")
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/models"

    if not github_token and not gemini_api_key:
        raise RuntimeError("Set GITHUB_TOKEN or GEMINI_API_KEY (or both) in .env")

    # If both are set, GitHub Models takes priority.
    llm_provider: str = "github" if github_token else "gemini"
    print(
        f"[config] LLM provider: {llm_provider} "
        f"(GITHUB_TOKEN {'set' if github_token else 'NOT set'}, "
        f"GEMINI_API_KEY {'set' if gemini_api_key else 'NOT set'})"
    )

    # Model names come entirely from env vars - no hardcoded fallback model
    # name here. Only the active provider's vars are required; the other
    # provider's are irrelevant if you're not using it.
    if llm_provider == "github":
        chat_model: str = _require("GITHUB_CHAT_MODEL")
        embedding_model: str = _require("GITHUB_EMBEDDING_MODEL")
    else:
        chat_model: str = _require("GEMINI_CHAT_MODEL")
        embedding_model: str = _require("GEMINI_EMBEDDING_MODEL")

    # --- Postgres (set USE_POSTGRES=false to use in-memory storage instead -
    # no DB needed, but data is lost on restart) ---
    use_postgres: bool = os.environ.get("USE_POSTGRES", "true").lower() == "true"
    database_url: str = _require("DATABASE_URL") if use_postgres else ""

    # --- Redis (set USE_REDIS=false to use an in-memory cache instead - no
    # Redis needed, but the cache is lost on restart / not shared across
    # processes). Used to cache embeddings, so re-ingesting unchanged
    # document chunks doesn't re-call the embeddings API for them.
    use_redis: bool = os.environ.get("USE_REDIS", "true").lower() == "true"
    redis_url: str = _require("REDIS_URL") if use_redis else ""

    # --- Gmail API (direct send of the approved reply via OAuth2 refresh token) ---
    gmail_client_id: str = _require("GMAIL_CLIENT_ID")
    gmail_client_secret: str = _require("GMAIL_CLIENT_SECRET")
    gmail_refresh_token: str = _require("GMAIL_REFRESH_TOKEN")
    gmail_sender: str = _require("GMAIL_SENDER")

    # --- Shared secret n8n sends - both the header name and its value are
    # configurable, not hardcoded ---
    webhook_header_name: str = os.environ.get("WEBHOOK_NAME", "X-Webhook-Token")
    webhook_token: str = _require("WEBHOOK_TOKEN")

    # --- RAG ---
    documents_path: str = os.environ.get("DOCUMENTS_PATH", "./documents")
    chroma_path: str = os.environ.get("CHROMA_PATH", "./chroma_db")

    # Note: TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN, N8N_BLOCK_ENV_ACCESS_IN_NODE
    # are read by n8n itself (via $env.* expressions in the workflow JSON),
    # not by this Python backend - listed in .env only because it's shared
    # with the n8n instance, nothing to load here for them.


settings = Settings()
