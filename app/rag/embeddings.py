import json
import logging

import httpx

from app.config import settings
from app.services import cache

logger = logging.getLogger("graph")


def _embed_gemini(texts: list[str]) -> list[list[float]]:
    model_path = f"models/{settings.embedding_model}"
    response = httpx.post(
        f"{settings.gemini_base_url}/{settings.embedding_model}:batchEmbedContents",
        headers={
            "x-goog-api-key": settings.gemini_api_key,
            "Content-Type": "application/json",
        },
        json={
            "requests": [
                {"model": model_path, "content": {"parts": [{"text": text}]}}
                for text in texts
            ]
        },
        timeout=30,
    )
    if response.status_code >= 400:
        logger.error("Gemini API error %s: %s", response.status_code, response.text)
    response.raise_for_status()
    return [item["values"] for item in response.json()["embeddings"]]


def embed(texts: list[str]) -> list[list[float]]:
    """Embeds via the Gemini API, cached by text+model (see services/cache.py)."""
    keys = [cache.embedding_cache_key(text, settings.embedding_model) for text in texts]
    cached_values = [cache.cache_get(key) for key in keys]

    missing_idx = [i for i, value in enumerate(cached_values) if value is None]
    if missing_idx:
        missing_texts = [texts[i] for i in missing_idx]
        fresh = _embed_gemini(missing_texts)
        for idx, vector in zip(missing_idx, fresh):
            serialized = json.dumps(vector)
            cache.cache_set(keys[idx], serialized)
            cached_values[idx] = serialized

    logger.info(
        "embed(): %d cache hit(s), %d miss(es) out of %d text(s)",
        len(texts) - len(missing_idx), len(missing_idx), len(texts),
    )
    return [json.loads(value) for value in cached_values]
