import httpx

from app.config import settings


def embed(texts: list[str]) -> list[list[float]]:
    """Embeds one or more texts via Gemini's batchEmbedContents endpoint."""
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
        print(f"Gemini API error {response.status_code}: {response.text}")
    response.raise_for_status()
    return [item["values"] for item in response.json()["embeddings"]]
