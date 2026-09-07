import hashlib
import logging

from app.config import settings

logger = logging.getLogger("graph")


if settings.use_redis:
    import redis

    _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)

    def cache_get(key: str) -> str | None:
        return _client.get(key)

    def cache_set(key: str, value: str, ttl_seconds: int = 60 * 60 * 24 * 7) -> None:
        _client.set(key, value, ex=ttl_seconds)

else:
    # USE_REDIS=false - plain in-memory dict, no Redis needed. Cache is lost
    # on every restart and not shared across processes; fine for a demo.
    logger.warning("USE_REDIS=false: using in-memory cache, lost on restart")

    _store: dict[str, str] = {}

    def cache_get(key: str) -> str | None:
        return _store.get(key)

    def cache_set(key: str, value: str, ttl_seconds: int = 0) -> None:
        _store[key] = value


def embedding_cache_key(text: str, model: str) -> str:
    digest = hashlib.sha256(f"{model}:{text}".encode()).hexdigest()
    return f"embedding:{digest}"
