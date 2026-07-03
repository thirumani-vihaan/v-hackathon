"""Build the ChromaDB knowledge base from PDFs in knowledge_base/raw/.

Chunks each PDF page, embeds with all-MiniLM-L6-v2, and persists to CHROMA_PERSIST_DIR.
Idempotent: clears and rebuilds the collection each run.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_ROOT, ".env"))
except Exception:
    pass

RAW_DIR = os.path.join(_ROOT, "knowledge_base", "raw")
PERSIST_DIR = os.environ.get(
    "CHROMA_PERSIST_DIR", os.path.join(_ROOT, "data", "chroma_db"))
COLLECTION = "safety_manual"
MODEL = "all-MiniLM-L6-v2"

# Ensure HF cache goes to the project.
_cache = os.environ.get("HF_HOME", os.path.join(_ROOT, "data", "hf_cache"))
os.makedirs(_cache, exist_ok=True)
os.environ.setdefault("HF_HOME", _cache)
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", _cache)


def _chunk_text(text: str, max_chars: int = 800, overlap: int = 120):
    text = " ".join(text.split())
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


def _get_client():
    import chromadb
    try:
        from chromadb.config import Settings
        return chromadb.PersistentClient(
            path=PERSIST_DIR, settings=Settings(anonymized_telemetry=False))
    except Exception:
        return chromadb.PersistentClient(path=PERSIST_DIR)


def _get_ef():
    try:
        from chromadb.utils.embedding_functions import (
            SentenceTransformerEmbeddingFunction,
        )
        return SentenceTransformerEmbeddingFunction(model_name=MODEL)
    except Exception:
        return None


def build():
    os.makedirs(PERSIST_DIR, exist_ok=True)
    from pypdf import PdfReader

    pdfs = [os.path.join(RAW_DIR, f) for f in os.listdir(RAW_DIR)
            if f.lower().endswith(".pdf")] if os.path.isdir(RAW_DIR) else []
    if not pdfs:
        print(f"[build_db] no PDFs found in {RAW_DIR}")
        return 0

    client = _get_client()
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    ef = _get_ef()
    if ef is not None:
        col = client.get_or_create_collection(COLLECTION, embedding_function=ef)
    else:
        col = client.get_or_create_collection(COLLECTION)

    ids, docs, metas = [], [], []
    total = 0
    for pdf_path in pdfs:
        filename = os.path.basename(pdf_path)
        reader = PdfReader(pdf_path)
        for page_idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            for c_idx, chunk in enumerate(_chunk_text(text)):
                ids.append(f"{filename}-p{page_idx}-c{c_idx}")
                docs.append(chunk)
                metas.append({"filename": filename, "page": str(page_idx)})
                total += 1

    if docs:
        # add in batches to be safe
        B = 100
        for i in range(0, len(docs), B):
            col.add(ids=ids[i:i + B], documents=docs[i:i + B],
                    metadatas=metas[i:i + B])
    print(f"[build_db] ingested {total} chunks from {len(pdfs)} PDF(s) "
          f"into '{COLLECTION}' at {PERSIST_DIR}")
    return total


if __name__ == "__main__":
    n = build()
    sys.exit(0 if n > 0 else 1)
