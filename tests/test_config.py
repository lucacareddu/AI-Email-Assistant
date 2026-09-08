import importlib
import os
from unittest.mock import patch

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


def _reload_config():
    """importlib.reload(config_module) re-runs config.py top to bottom,
    including its `from dotenv import load_dotenv` line - which reload
    re-executes too, rebinding the name fresh each time. Patching
    "app.config.load_dotenv" therefore doesn't survive a reload (the
    re-executed import immediately overwrites the patch with the real
    function again, before it's ever called); patching "dotenv.load_dotenv"
    at the source does, since that fresh rebind picks up the patched
    version too. Without this, load_dotenv() would silently refill any var a
    test just popped from os.environ straight back out of the real project
    .env file."""
    with patch("dotenv.load_dotenv"):
        importlib.reload(config_module)


def _reload_with(env: dict):
    for key in _PROVIDER_KEYS:
        os.environ.pop(key, None)
    os.environ.update(_REQUIRED_BASE)
    os.environ.update(env)
    _reload_config()
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
        _reload_config()


def test_raises_when_chat_model_missing():
    for key in _PROVIDER_KEYS:
        os.environ.pop(key, None)
    os.environ.update(_REQUIRED_BASE)
    os.environ["GEMINI_API_KEY"] = "gem"
    os.environ["GEMINI_EMBEDDING_MODEL"] = "gemini-embedding-001"
    # GEMINI_CHAT_MODEL deliberately left unset
    with pytest.raises(RuntimeError, match="GEMINI_CHAT_MODEL"):
        _reload_config()
