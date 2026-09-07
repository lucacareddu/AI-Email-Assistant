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

_PROVIDER_KEYS = ["GEMINI_API_KEY", "GEMINI_CHAT_MODEL", "GEMINI_EMBEDDING_MODEL"]


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


def test_loads_gemini_settings():
    settings = _reload_with({
        "GEMINI_API_KEY": "gem", "GEMINI_CHAT_MODEL": "gemini-2.5-flash", "GEMINI_EMBEDDING_MODEL": "gemini-embedding-001",
    })
    assert settings.chat_model == "gemini-2.5-flash"
    assert settings.embedding_model == "gemini-embedding-001"


def test_raises_when_gemini_api_key_missing():
    for key in _PROVIDER_KEYS:
        os.environ.pop(key, None)
    os.environ.update(_REQUIRED_BASE)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        importlib.reload(config_module)


def test_raises_when_chat_model_missing():
    for key in _PROVIDER_KEYS:
        os.environ.pop(key, None)
    os.environ.update(_REQUIRED_BASE)
    os.environ["GEMINI_API_KEY"] = "gem"
    os.environ["GEMINI_EMBEDDING_MODEL"] = "gemini-embedding-001"
    # GEMINI_CHAT_MODEL deliberately left unset
    with pytest.raises(RuntimeError, match="GEMINI_CHAT_MODEL"):
        importlib.reload(config_module)
