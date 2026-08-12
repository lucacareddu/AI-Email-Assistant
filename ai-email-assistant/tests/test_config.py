import importlib
import os

import pytest

import app.config as config_module

_REQUIRED_BASE = {
    "GMAIL_CLIENT_ID": "x",
    "GMAIL_CLIENT_SECRET": "x",
    "GMAIL_REFRESH_TOKEN": "x",
    "GMAIL_SENDER": "a@b.com",
    "WEBHOOK_TOKEN": "x",
    "USE_POSTGRES": "false",
    "USE_REDIS": "false",
}

_PROVIDER_KEYS = [
    "GITHUB_TOKEN", "GEMINI_API_KEY",
    "GITHUB_CHAT_MODEL", "GITHUB_EMBEDDING_MODEL",
    "GEMINI_CHAT_MODEL", "GEMINI_EMBEDDING_MODEL",
]


def _reload_with(env: dict):
    for key in _PROVIDER_KEYS:
        os.environ.pop(key, None)
    os.environ.update(_REQUIRED_BASE)
    os.environ.update(env)
    importlib.reload(config_module)
    return config_module.settings


@pytest.fixture(autouse=True)
def _restore_valid_settings_after_each_test():
    """Leaves app.config in a valid state for whatever test runs next,
    regardless of what this file's tests do to the environment."""
    yield
    _reload_with({
        "GEMINI_API_KEY": "test-gemini-key",
        "GEMINI_CHAT_MODEL": "gemini-2.5-flash",
        "GEMINI_EMBEDDING_MODEL": "gemini-embedding-001",
    })


def test_github_wins_when_both_are_set():
    settings = _reload_with({
        "GITHUB_TOKEN": "gh", "GITHUB_CHAT_MODEL": "gpt-4o-mini", "GITHUB_EMBEDDING_MODEL": "text-embedding-3-small",
        "GEMINI_API_KEY": "gem", "GEMINI_CHAT_MODEL": "gemini-2.5-flash", "GEMINI_EMBEDDING_MODEL": "gemini-embedding-001",
    })
    assert settings.llm_provider == "github"
    assert settings.chat_model == "gpt-4o-mini"
    assert settings.embedding_model == "text-embedding-3-small"


def test_gemini_used_when_github_token_absent():
    settings = _reload_with({
        "GEMINI_API_KEY": "gem", "GEMINI_CHAT_MODEL": "gemini-2.5-flash", "GEMINI_EMBEDDING_MODEL": "gemini-embedding-001",
    })
    assert settings.llm_provider == "gemini"
    assert settings.chat_model == "gemini-2.5-flash"


def test_raises_when_neither_provider_key_set():
    for key in _PROVIDER_KEYS:
        os.environ.pop(key, None)
    os.environ.update(_REQUIRED_BASE)
    with pytest.raises(RuntimeError):
        importlib.reload(config_module)


def test_raises_when_active_provider_model_var_missing():
    for key in _PROVIDER_KEYS:
        os.environ.pop(key, None)
    os.environ.update(_REQUIRED_BASE)
    os.environ["GITHUB_TOKEN"] = "gh"
    os.environ["GITHUB_EMBEDDING_MODEL"] = "text-embedding-3-small"
    # GITHUB_CHAT_MODEL deliberately left unset
    with pytest.raises(RuntimeError, match="GITHUB_CHAT_MODEL"):
        importlib.reload(config_module)
