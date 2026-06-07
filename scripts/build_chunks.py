from pathlib import Path
import json
import re
import html
import random
from typing import Dict, List

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter


DOCUMENTS_DIR = Path("documents")
DATA_DIR = Path("data")

RAW_DOCS_PATH = DATA_DIR / "raw_docs.json"
CLEANED_DOCS_PATH = DATA_DIR / "cleaned_docs.json"
CHUNKS_PATH = DATA_DIR / "chunks.json"

CHUNK_SIZE = 650
CHUNK_OVERLAP = 125


def parse_document_file(file_path: Path) -> Dict:
    """
    Loads one .txt document and extracts simple metadata from the top of the file.

    Expected optional metadata lines:
    Title: ...
    URL: ...
    Category: ...
    Region: ...
    """

    text = file_path.read_text(encoding="utf-8", errors="ignore")

    metadata = {
        "filename": file_path.name,
        "title": file_path.stem.replace("_", " ").title(),
        "url": "",
        "category": "",
        "region": "",
    }

    lines = text.splitlines()
    body_start_index = 0

    for i, line in enumerate(lines[:10]):
        clean_line = line.strip()

        if clean_line.lower().startswith("title:"):
            metadata["title"] = clean_line.split(":", 1)[1].strip()
            body_start_index = i + 1

        elif clean_line.lower().startswith("url:"):
            metadata["url"] = clean_line.split(":", 1)[1].strip()
            body_start_index = i + 1

        elif clean_line.lower().startswith("category:"):
            metadata["category"] = clean_line.split(":", 1)[1].strip()
            body_start_index = i + 1

        elif clean_line.lower().startswith("region:"):
            metadata["region"] = clean_line.split(":", 1)[1].strip()
            body_start_index = i + 1

    body = "\n".join(lines[body_start_index:]).strip()

    return {
        "metadata": metadata,
        "raw_text": body,
    }


def clean_text(text: str) -> str:
    """
    Cleans copied website text.
    Removes common HTML artifacts, extra whitespace, and repeated boilerplate.
    """

    # Decode things like &amp;, &nbsp;, &#39;
    text = html.unescape(text)

    # Remove HTML tags if any were copied
    text = re.sub(r"<[^>]+>", " ", text)

    # Remove common website/navigation boilerplate
    boilerplate_patterns = [
        r"Skip to main content",
        r"Share this page",
        r"Read more",
        r"Subscribe.*",
        r"Sign up.*",
        r"Follow us.*",
        r"Cookie.*",
        r"Privacy Policy",
        r"Terms of Use",
        r"Advertisement",
        r"Menu",
        r"Search",
    ]

    for pattern in boilerplate_patterns:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    # Normalize whitespace
    text = text.replace("\xa0", " ")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    # Remove very short repeated-looking lines
    lines = []
    for line in text.splitlines():
        line = line.strip()

        if not line:
            lines.append("")
            continue

        # Drop extremely short nav-like lines
        if len(line) <= 2:
            continue

        lines.append(line)

    cleaned = "\n".join(lines).strip()

    return cleaned


def load_documents() -> List[Dict]:
    """
    Loads all .txt files from the documents folder.
    """

    if not DOCUMENTS_DIR.exists():
        raise FileNotFoundError(
            f"Could not find {DOCUMENTS_DIR}. Create a documents/ folder first."
        )

    files = sorted(DOCUMENTS_DIR.glob("*.txt"))

    if not files:
        raise FileNotFoundError(
            "No .txt files found in documents/. Add your source documents first."
        )

    docs = []

    for file_path in files:
        parsed = parse_document_file(file_path)
        docs.append(parsed)

    return docs


def save_json(data, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def chunk_documents(cleaned_docs: List[Dict]) -> List[Dict]:
    """
    Splits cleaned documents into chunks and preserves metadata.
    """

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", "? ", "! ", " ", ""],
    )

    all_chunks = []

    for doc in cleaned_docs:
        metadata = doc["metadata"]
        cleaned_text = doc["cleaned_text"]

        chunks = splitter.split_text(cleaned_text)

        for i, chunk in enumerate(chunks):
            chunk = chunk.strip()

            if len(chunk) == 0:
                continue

            all_chunks.append(
                {
                    "chunk_id": f"{metadata['filename']}::chunk_{i}",
                    "text": chunk,
                    "metadata": {
                        **metadata,
                        "chunk_index": i,
                    },
                }
            )

    return all_chunks


def print_document_preview(cleaned_docs: List[Dict]) -> None:
    """
    Prints one cleaned document so you can manually inspect it.
    """

    print("\n" + "=" * 80)
    print("CLEANED DOCUMENT PREVIEW")
    print("=" * 80)

    doc = cleaned_docs[0]

    print(f"Title: {doc['metadata']['title']}")
    print(f"Source: {doc['metadata']['url']}")
    print("-" * 80)
    print(doc["cleaned_text"][:2500])
    print("-" * 80)


def print_random_chunks(chunks: List[Dict], n: int = 5) -> None:
    """
    Prints random chunks for inspection.
    """

    print("\n" + "=" * 80)
    print(f"RANDOM CHUNK INSPECTION: {n} CHUNKS")
    print("=" * 80)

    sample_size = min(n, len(chunks))
    sampled_chunks = random.sample(chunks, sample_size)

    for chunk in sampled_chunks:
        print("\n" + "-" * 80)
        print(f"Chunk ID: {chunk['chunk_id']}")
        print(f"Title: {chunk['metadata']['title']}")
        print(f"URL: {chunk['metadata']['url']}")
        print(f"Category: {chunk['metadata']['category']}")
        print(f"Region: {chunk['metadata']['region']}")
        print(f"Length: {len(chunk['text'])} characters")
        print("-" * 80)
        print(chunk["text"])


def main() -> None:
    print("Loading raw documents...")
    raw_docs = load_documents()
    save_json(raw_docs, RAW_DOCS_PATH)

    print(f"Loaded {len(raw_docs)} raw documents.")
    print(f"Saved raw documents to {RAW_DOCS_PATH}")

    cleaned_docs = []

    for doc in raw_docs:
        cleaned = clean_text(doc["raw_text"])

        cleaned_docs.append(
            {
                "metadata": doc["metadata"],
                "cleaned_text": cleaned,
            }
        )

    save_json(cleaned_docs, CLEANED_DOCS_PATH)

    print(f"Cleaned {len(cleaned_docs)} documents.")
    print(f"Saved cleaned documents to {CLEANED_DOCS_PATH}")

    print_document_preview(cleaned_docs)

    print("\nChunking documents...")
    chunks = chunk_documents(cleaned_docs)
    save_json(chunks, CHUNKS_PATH)

    print(f"Created {len(chunks)} total chunks.")
    print(f"Saved chunks to {CHUNKS_PATH}")

    print_random_chunks(chunks, n=5)




if __name__ == "__main__":
    main()