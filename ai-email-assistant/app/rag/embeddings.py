import json
import logging

import httpx
from azure.ai.inference import EmbeddingsClient
from azure.core.credentials import AzureKeyCredential

from app.config import settings
from app.services import cache

logger = logging.getLogger("graph")

_github_embeddings_client = None


def _get_github_embeddings_client() -> EmbeddingsClient:
    global _github_embeddings_client
    if _github_embeddings_client is None:
        _github_embeddings_client = EmbeddingsClient(
            endpoint=settings.github_endpoint,
            credential=AzureKeyCredential(settings.github_token),
        )
    return _github_embeddings_client


def _embed_github(texts: list[str]) -> list[list[float]]:
    response = _get_github_embeddings_client().embed(input=texts, model=settings.embedding_model)
    return [item.embedding for item in response.data]


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
    """Embeds via whichever LLM provider is configured (GitHub Models takes
    priority over Gemini if both are set - see app/config.py).

    Results are cached (Redis or in-memory, see app/services/cache.py) keyed
    by text+model, so re-ingesting unchanged document chunks doesn't re-call
    the embeddings API for them.
    """
    keys = [cache.embedding_cache_key(text, settings.embedding_model) for text in texts]
    cached_values = [cache.cache_get(key) for key in keys]

    missing_idx = [i for i, value in enumerate(cached_values) if value is None]
    if missing_idx:
        missing_texts = [texts[i] for i in missing_idx]
        fresh = (
            _embed_github(missing_texts)
            if settings.llm_provider == "github"
            else _embed_gemini(missing_texts)
        )
        for idx, vector in zip(missing_idx, fresh):
            serialized = json.dumps(vector)
            cache.cache_set(keys[idx], serialized)
            cached_values[idx] = serialized

    logger.info(
        "embed(): %d cache hit(s), %d miss(es) out of %d text(s)",
        len(texts) - len(missing_idx), len(missing_idx), len(texts),
    )
    return [json.loads(value) for value in cached_values]
