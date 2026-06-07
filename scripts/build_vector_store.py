from pathlib import Path
import json
from typing import Dict, List

import chromadb
from sentence_transformers import SentenceTransformer


CHUNKS_PATH = Path("data/chunks.json")
CHROMA_DIR = "data/chroma_db"
COLLECTION_NAME = "dmv_weekend_guide"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


def load_chunks() -> List[Dict]:
    if not CHUNKS_PATH.exists():
        raise FileNotFoundError(
            f"Could not find {CHUNKS_PATH}. Run python scripts/build_chunks.py first."
        )

    with CHUNKS_PATH.open("r", encoding="utf-8") as f:
        chunks = json.load(f)

    if not chunks:
        raise ValueError("data/chunks.json is empty.")

    return chunks


def prepare_metadata(chunk: Dict) -> Dict:
    metadata = chunk.get("metadata", {})

    return {
        "chunk_id": str(chunk.get("chunk_id", "")),
        "filename": str(metadata.get("filename", "")),
        "title": str(metadata.get("title", "")),
        "url": str(metadata.get("url", "")),
        "category": str(metadata.get("category", "")),
        "region": str(metadata.get("region", "")),
        "chunk_index": int(metadata.get("chunk_index", 0)),
    }


def build_vector_store() -> None:
    chunks = load_chunks()

    print(f"Loaded {len(chunks)} chunks from {CHUNKS_PATH}")
    print(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    texts = [chunk["text"] for chunk in chunks]
    ids = [chunk["chunk_id"] for chunk in chunks]
    metadatas = [prepare_metadata(chunk) for chunk in chunks]

    print("Embedding chunks...")
    embeddings = model.encode(
        texts,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    client = chromadb.PersistentClient(path=CHROMA_DIR)

    existing = [collection.name for collection in client.list_collections()]
    if COLLECTION_NAME in existing:
        print(f"Deleting old collection: {COLLECTION_NAME}")
        client.delete_collection(COLLECTION_NAME)

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    print("Saving chunks to ChromaDB...")
    collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings.tolist(),
        metadatas=metadatas,
    )

    print(f"Stored {collection.count()} chunks in ChromaDB.")


def retrieve(query: str, k: int = 5) -> None:
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    query_embedding = model.encode(
        query,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_collection(name=COLLECTION_NAME)

    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )

    print("\n" + "=" * 100)
    print(f"QUERY: {query}")
    print("=" * 100)

    docs = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for i, (doc, metadata, distance) in enumerate(zip(docs, metadatas, distances), 1):
        print("\n" + "-" * 100)
        print(f"Result {i}")
        print(f"Distance: {distance:.4f}")
        print(f"Title: {metadata.get('title')}")
        print(f"Filename: {metadata.get('filename')}")
        print(f"URL: {metadata.get('url')}")
        print("-" * 100)
        print(doc)


def test_retrieval() -> None:
    test_queries = [
        "Is Burke Lake Park good for beginner boating or kayaking?",
        "What indoor activities are good near Northern Virginia during a heat wave?",
        "Is Great Falls Park crowded on weekends?",
        "What are good free things to do in DC this weekend?",
        "Where can I rent kayaks or paddleboards in Fairfax County?",
    ]

    for query in test_queries:
        retrieve(query, k=5)


if __name__ == "__main__":
    build_vector_store()
    test_retrieval()