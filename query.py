import os
from typing import Dict, List

import chromadb
from dotenv import load_dotenv
from groq import Groq
from sentence_transformers import SentenceTransformer


load_dotenv()

CHROMA_DIR = "data/chroma_db"
COLLECTION_NAME = "dmv_weekend_guide"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
LLM_MODEL_NAME = "llama-3.3-70b-versatile"


embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)


def retrieve_chunks(question: str, k: int = 5) -> List[Dict]:
    query_embedding = embedding_model.encode(
        question,
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

    chunks = []

    for doc, metadata, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append(
            {
                "text": doc,
                "metadata": metadata,
                "distance": distance,
            }
        )

    return chunks


def format_context(chunks: List[Dict]) -> str:
    context_parts = []

    for i, chunk in enumerate(chunks, 1):
        metadata = chunk["metadata"]

        source_title = metadata.get("title", "Unknown source")
        filename = metadata.get("filename", "Unknown file")
        url = metadata.get("url", "")
        distance = chunk["distance"]

        context_parts.append(
            f"""[Source {i}]
Title: {source_title}
Filename: {filename}
URL: {url}
Distance: {distance:.4f}

Text:
{chunk["text"]}
"""
        )

    return "\n\n".join(context_parts)


def get_sources(chunks: List[Dict]) -> List[str]:
    sources = []

    seen = set()

    for chunk in chunks:
        metadata = chunk["metadata"]

        title = metadata.get("title", "Unknown source")
        filename = metadata.get("filename", "Unknown file")
        url = metadata.get("url", "")
        distance = chunk["distance"]

        source_string = f"{title} ({filename}) — distance: {distance:.4f}"

        if url:
            source_string += f"\n{url}"

        if source_string not in seen:
            seen.add(source_string)
            sources.append(source_string)

    return sources


def generate_answer(question: str, chunks: List[Dict]) -> str:
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("Missing GROQ_API_KEY. Add it to your .env file.")

    client = Groq(api_key=api_key)

    context = format_context(chunks)

    system_prompt = """
You are the DMV Weekend Guide, a retrieval-grounded assistant for student weekend activities in DC, Virginia, and Maryland.

You must follow these rules:
1. Answer using only the provided retrieved context.
2. Do not use outside knowledge.
3. If the context does not contain enough information, say: "I don't have enough information in the provided documents to answer that."
4. Cite sources by source number, such as [Source 1] or [Source 2].
5. Keep the answer practical and student-focused.
6. If comparing options, organize the answer clearly.
"""

    user_prompt = f"""
Question:
{question}

Retrieved context:
{context}

Answer the question using only the retrieved context.
"""

    response = client.chat.completions.create(
        model=LLM_MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content


def ask(question: str, k: int = 5) -> Dict:
    chunks = retrieve_chunks(question, k=k)

    # Optional guardrail:
    # If all retrieved chunks are weak matches, do not ask the LLM to guess.
    best_distance = min(chunk["distance"] for chunk in chunks)

    if best_distance > 0.65:
        return {
            "answer": "I don't have enough information in the provided documents to answer that.",
            "sources": get_sources(chunks),
            "chunks": chunks,
        }

    answer = generate_answer(question, chunks)

    return {
        "answer": answer,
        "sources": get_sources(chunks),
        "chunks": chunks,
    }


if __name__ == "__main__":
    while True:
        question = input("\nAsk a question, or type 'exit': ")

        if question.lower().strip() in {"exit", "quit"}:
            break

        result = ask(question)

        print("\nANSWER")
        print("=" * 80)
        print(result["answer"])

        print("\nSOURCES")
        print("=" * 80)
        for source in result["sources"]:
            print(f"- {source}")