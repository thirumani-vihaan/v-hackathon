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


def _extract_units(path: str):
    """Return [(unit_label, text)] for a source file. PDFs split by page; text/markdown
    split by heading so each section carries a meaningful citation label."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(path)
        return [(str(i), page.extract_text() or "")
                for i, page in enumerate(reader.pages, start=1)]
    # .txt / .md — split on markdown headings into logical sections
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    units, label, buf = [], "1", []
    for line in raw.splitlines():
        if line.lstrip().startswith("#"):
            if buf:
                units.append((label, "\n".join(buf)))
                buf = []
            label = line.lstrip("# ").strip()[:60] or label
        else:
            buf.append(line)
    if buf:
        units.append((label, "\n".join(buf)))
    return units or [("1", raw)]


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

    exts = (".pdf", ".txt", ".md")
    sources = [os.path.join(RAW_DIR, f) for f in os.listdir(RAW_DIR)
               if f.lower().endswith(exts)] if os.path.isdir(RAW_DIR) else []
    if not sources:
        print(f"[build_db] no source documents found in {RAW_DIR}")
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
    for src_path in sources:
        filename = os.path.basename(src_path)
        for unit_label, text in _extract_units(src_path):
            for c_idx, chunk in enumerate(_chunk_text(text)):
                ids.append(f"{filename}-{unit_label[:24]}-c{c_idx}-{total}")
                docs.append(chunk)
                metas.append({"filename": filename, "page": str(unit_label)})
                total += 1

    if docs:
        # add in batches to be safe
        B = 100
        for i in range(0, len(docs), B):
            col.add(ids=ids[i:i + B], documents=docs[i:i + B],
                    metadatas=metas[i:i + B])
    print(f"[build_db] ingested {total} chunks from {len(sources)} document(s) "
          f"into '{COLLECTION}' at {PERSIST_DIR}")
    return total


if __name__ == "__main__":
    n = build()
    sys.exit(0 if n > 0 else 1)
