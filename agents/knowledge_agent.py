"""KnowledgeAgent: query -> KnowledgeResult via ChromaDB RAG with citations.

Uses the persisted Chroma collection built by knowledge_base/build_db.py.
Follows CLAUDE.md ChromaDB 0.5.x notes: PersistentClient with telemetry off,
get_or_create_collection, SentenceTransformer embedding function.
Never raises across the boundary.
"""
import os

from schema import QueryInput, KnowledgeResult

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_PERSIST = os.environ.get(
    "CHROMA_PERSIST_DIR", os.path.join(_ROOT, "data", "chroma_db"))
_COLLECTION = "safety_manual"
_MODEL = "all-MiniLM-L6-v2"


def _get_embedding_function():
    try:
        from chromadb.utils.embedding_functions import (
            SentenceTransformerEmbeddingFunction,
        )
        return SentenceTransformerEmbeddingFunction(model_name=_MODEL)
    except Exception:
        return None


def _get_client(persist_dir: str):
    import chromadb
    try:
        from chromadb.config import Settings
        return chromadb.PersistentClient(
            path=persist_dir, settings=Settings(anonymized_telemetry=False))
    except Exception:
        return chromadb.PersistentClient(path=persist_dir)


class KnowledgeAgent:
    def __init__(self, persist_dir: str = _DEFAULT_PERSIST,
                 collection_name: str = _COLLECTION):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self._collection = None
        self._init_error = None
        try:
            client = _get_client(persist_dir)
            ef = _get_embedding_function()
            if ef is not None:
                self._collection = client.get_or_create_collection(
                    collection_name, embedding_function=ef)
            else:
                self._collection = client.get_or_create_collection(collection_name)
        except Exception as e:  # noqa: BLE001
            self._init_error = str(e)

    def query(self, query_input: QueryInput, n_results: int = 3) -> KnowledgeResult:
        if self._init_error is not None:
            return KnowledgeResult(
                answer="Knowledge base unavailable.",
                sources=[], confidence=0.0, error=self._init_error)
        try:
            count = self._collection.count()
            if count == 0:
                return KnowledgeResult(
                    answer=("Knowledge base is empty. Run "
                            "knowledge_base/build_db.py to ingest documents."),
                    sources=[], confidence=0.0,
                    error="empty_collection")

            res = self._collection.query(
                query_texts=[query_input.query_text],
                n_results=min(n_results, count),
            )
            docs = (res.get("documents") or [[]])[0]
            metas = (res.get("metadatas") or [[]])[0]
            dists = (res.get("distances") or [[]])[0]

            if not docs:
                return KnowledgeResult(
                    answer="No relevant passages found.",
                    sources=[], confidence=0.0)

            sources = []
            for doc, meta, dist in zip(docs, metas, dists):
                excerpt = doc.strip().replace("\n", " ")
                if len(excerpt) > 300:
                    excerpt = excerpt[:300] + "..."
                sources.append({
                    "filename": str((meta or {}).get("filename", "unknown")),
                    "page": str((meta or {}).get("page", "?")),
                    "excerpt": excerpt,
                })

            # Confidence from best cosine distance (lower distance -> higher conf).
            best = min(dists) if dists else 1.0
            confidence = max(0.0, min(1.0, 1.0 - float(best)))
            if confidence <= 0.0:
                confidence = 0.35  # non-zero floor when we do have matches

            top = docs[0].strip().replace("\n", " ")
            answer = (f"Based on the safety manual: {top[:500]}"
                      + ("..." if len(top) > 500 else ""))

            return KnowledgeResult(
                answer=answer,
                sources=sources,
                confidence=round(confidence, 3),
            )
        except Exception as e:  # noqa: BLE001
            return KnowledgeResult(
                answer="Knowledge query failed.",
                sources=[], confidence=0.0, error=str(e))


if __name__ == "__main__":
    r = KnowledgeAgent().query(
        QueryInput(query_text="confined space entry requirements"))
    print("conf:", r.confidence, "sources:", len(r.sources))
    print(r.answer)
