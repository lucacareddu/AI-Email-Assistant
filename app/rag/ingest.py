"""Builds/updates the local vector store from the PDFs in documents/.

Usage:
    python -m app.rag.ingest
"""
import glob
import os

import chromadb
from pypdf import PdfReader

from app.config import settings
from app.rag.embeddings import embed

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def _read_pdf(path: str) -> str:
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _chunk(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start = end - CHUNK_OVERLAP
    return [c.strip() for c in chunks if c.strip()]


def main():
    client = chromadb.PersistentClient(path=settings.chroma_path)
    collection = client.get_or_create_collection("documents")

    pdf_paths = glob.glob(os.path.join(settings.documents_path, "*.pdf"))
    if not pdf_paths:
        print(f"Nessun PDF trovato in {settings.documents_path}")
        return

    for path in pdf_paths:
        filename = os.path.basename(path)
        chunks = _chunk(_read_pdf(path))
        if not chunks:
            continue

        embeddings = embed(chunks)
        ids = [f"{filename}-{i}" for i in range(len(chunks))]
        metadatas = [{"source": filename} for _ in chunks]

        collection.upsert(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)
        print(f"Indicizzati {len(chunks)} chunk da {filename}")


if __name__ == "__main__":
    main()
