"""
Semantic memory storage — persists and retrieves documents across agent runs.
"""

from typing import Any

import chromadb

from core.config import CHROMA_DIR


def get_chroma_client() -> chromadb.PersistentClient:
    """Return a ChromaDB client pointing to the project's vector store."""
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def get_collection(name: str = "idamp_memory") -> chromadb.Collection:
    """Get or create a ChromaDB collection (without embeddings)."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"}  # No embeddings used; just document storage
    )


def store_document(doc_id: str, text: str, metadata: dict | None = None) -> None:
    """Upsert a document into memory. Silently continues on error."""
    try:
        collection = get_collection()
        collection.upsert(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata or {}],
        )
    except Exception:
        pass


def query_memory(query_text: str, n_results: int = 5) -> list[dict]:
    """Retrieve documents from memory. Returns empty list on error."""
    try:
        collection = get_collection()
        results = collection.get(limit=n_results)
        return [
            {
                "id": doc_id,
                "document": doc,
                "metadata": meta,
            }
            for doc_id, doc, meta in zip(
                results["ids"],
                results["documents"],
                results["metadatas"],
            )
        ]
    except Exception:
        return []
