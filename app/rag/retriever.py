import chromadb

from app.config import settings
from app.rag.embeddings import embed

_client = chromadb.PersistentClient(path=settings.chroma_path)


def similarity_search(query: str, k: int = 4) -> list[str]:
    collection = _client.get_or_create_collection("documents")
    if collection.count() == 0:
        return []

    query_embedding = embed([query])[0]
    results = collection.query(query_embeddings=[query_embedding], n_results=k)
    return results["documents"][0] if results["documents"] else []
