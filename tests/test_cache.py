from app.services import cache


def test_cache_roundtrip():
    key = cache.embedding_cache_key("hello world", "test-model")
    assert cache.cache_get(key) is None
    cache.cache_set(key, "stored-value")
    assert cache.cache_get(key) == "stored-value"


def test_cache_key_is_deterministic_and_model_specific():
    k1 = cache.embedding_cache_key("same text", "model-a")
    k2 = cache.embedding_cache_key("same text", "model-a")
    k3 = cache.embedding_cache_key("same text", "model-b")
    assert k1 == k2
    assert k1 != k3
