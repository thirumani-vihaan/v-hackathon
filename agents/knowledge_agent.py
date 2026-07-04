"""KnowledgeAgent: query -> KnowledgeResult via ChromaDB RAG, grounded by Gemini.

Behavior (no keyword mapping, ever):
  1. Always retrieve top-k chunks from Chroma for ANY question.
  2. If the corpus has matches: synthesize ONE Gemini answer grounded strictly in
     the retrieved context. If Gemini is unavailable, fall back to a deterministic
     extractive answer from the top chunk. Sources carry filename/page/excerpt.
  3. If the corpus is empty / no match:
       - key present  -> general Gemini safety answer, source labelled
         "General Safety (Gemini)", confidence 0.45
       - key missing  -> honest "no docs loaded" answer, sources [], confidence 0.10
  4. KNOWLEDGE_DEBUG=1 adds a chunk_preview to each source.
  5. KNOWLEDGE_LLM=0 disables Gemini synthesis (deterministic extractive answers).

Follows CLAUDE.md ChromaDB 0.5.x notes; never raises across the boundary.
"""
import os

from schema import QueryInput, KnowledgeResult

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_PERSIST = os.environ.get(
    "CHROMA_PERSIST_DIR", os.path.join(_ROOT, "data", "chroma_db"))
# Single source of truth for the collection name (shared with build_db.py).
COLLECTION_NAME = "safety_manual"
_MODEL = "all-MiniLM-L6-v2"


def _prefer_offline_embeddings() -> None:
    """If the MiniLM model is already cached, avoid HuggingFace network checks.

    This prevents multi-second startup hangs (and offline crashes) from the hub
    'is there an update?' HEAD request, while still allowing a first-time
    download when the model is not yet cached. Does not affect Gemini calls.
    """
    if os.environ.get("HF_HUB_OFFLINE") or os.environ.get("TRANSFORMERS_OFFLINE"):
        return
    cache = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub",
                         "models--sentence-transformers--all-MiniLM-L6-v2")
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        cache = os.path.join(hf_home, "hub",
                             "models--sentence-transformers--all-MiniLM-L6-v2")
    if os.path.isdir(cache):
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


def _debug_on() -> bool:
    return os.environ.get("KNOWLEDGE_DEBUG", "").strip() in ("1", "true", "True")


def _llm_on() -> bool:
    return os.environ.get("KNOWLEDGE_LLM", "1").strip() not in ("0", "false", "False")


def _get_embedding_function():
    try:
        _prefer_offline_embeddings()
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


def _gemini_generate(prompt: str):
    """Return generated text or None. Never raises; never logs the key."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        from utils.gemini_vision import MODELS
        for model_name in MODELS:
            try:
                model = genai.GenerativeModel(model_name)
                resp = model.generate_content(prompt)
                text = (getattr(resp, "text", "") or "").strip()
                if text:
                    return text
            except Exception:
                continue
    except Exception:
        return None
    return None


class KnowledgeAgent:
    def __init__(self, persist_dir: str = _DEFAULT_PERSIST,
                 collection_name: str = COLLECTION_NAME):
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

    # ---- answer builders -------------------------------------------------
    _STOP = set((
        "the a an of to in for and or is are be with on at by from as that this it "
        "must should shall not no all any within when what which how why do does "
        "require required requires their there they you your our we").split())

    def _extractive_answer(self, docs, question: str = "") -> str:
        """Deterministic extractive QA: rank sentences in the retrieved chunks by
        overlap with the question and return the most relevant ones — a focused
        answer, not a raw chunk dump."""
        import re
        qwords = {w for w in re.findall(r"[a-z0-9]+", (question or "").lower())
                  if w not in self._STOP and len(w) > 2}
        sents = []
        seen = set()
        for doc in docs[:3]:
            for s in re.split(r"(?<=[.!?])\s+", (doc or "").replace("\n", " ")):
                s = s.strip()
                if len(s) > 25 and s.lower() not in seen:
                    seen.add(s.lower())
                    sents.append(s)
        if not sents:
            top = (docs[0] if docs else "").strip().replace("\n", " ")
            return top[:400]

        def score(s):
            return len(qwords & set(re.findall(r"[a-z0-9]+", s.lower())))

        ranked = sorted(sents, key=lambda s: (-score(s), len(s)))
        best = score(ranked[0]) if ranked else 0
        picked, total = [], 0
        for s in ranked:
            if picked and score(s) == 0:
                break
            picked.append(s)
            total += len(s)
            if len(picked) >= 3 or total > 480:
                break
        if not picked:
            picked = [ranked[0]]
        answer = " ".join(picked)
        if best <= 1:  # weak overlap — be honest about grounding
            answer = "The manual does not directly address this; closest guidance: " + answer
        return answer

    def _grounded_answer(self, question: str, docs, metas):
        """Return (answer, used_llm). Grounds a Gemini answer in retrieved text;
        falls back to extractive if Gemini is off or fails."""
        if not _llm_on():
            return self._extractive_answer(docs, question), False
        context_parts = []
        for i, (doc, meta) in enumerate(zip(docs, metas), start=1):
            ref = (meta or {}).get("filename", "manual")
            page = (meta or {}).get("page", "?")
            context_parts.append(f"[{i}] ({ref} p.{page}) {doc.strip()}")
        context = "\n\n".join(context_parts)
        prompt = (
            "You are an industrial safety assistant for an oil & gas refinery. "
            "Using ONLY the manual excerpts below, answer the question concisely "
            "(2-4 sentences) and cite the OISD section numbers that appear in the "
            "excerpts. If the excerpts do not contain the answer, say the manual "
            "does not cover it.\n\n"
            f"EXCERPTS:\n{context}\n\nQUESTION: {question}\n\nANSWER:")
        text = _gemini_generate(prompt)
        if text:
            return text, True
        return self._extractive_answer(docs, question), False

    def _no_corpus_answer(self, question: str) -> KnowledgeResult:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if api_key and _llm_on():
            prompt = (
                "You are an industrial safety assistant. There is no local "
                "regulatory corpus available. Answer this question from general "
                "industrial-safety knowledge in 2-4 sentences, and note that this "
                f"is general guidance, not a cited plant procedure.\n\nQUESTION: "
                f"{question}")
            text = _gemini_generate(prompt)
            if text:
                return KnowledgeResult(
                    answer=text,
                    sources=[{
                        "filename": "General Safety (Gemini)",
                        "page": "-",
                        "excerpt": ("No local regulatory corpus match; answered "
                                    "from general knowledge."),
                    }],
                    confidence=0.45,
                )
        return KnowledgeResult(
            answer=("No local documents loaded; add PDFs to knowledge_base/raw/ "
                    "and run knowledge_base/build_db.py to enable grounded answers."),
            sources=[], confidence=0.10, error="empty_collection")

    # ---- main entry point ------------------------------------------------
    def query(self, query_input: QueryInput, n_results: int = 4) -> KnowledgeResult:
        if self._init_error is not None:
            return KnowledgeResult(
                answer="Knowledge base unavailable.",
                sources=[], confidence=0.0, error=self._init_error)
        try:
            count = self._collection.count()
            if count == 0:
                return self._no_corpus_answer(query_input.query_text)

            res = self._collection.query(
                query_texts=[query_input.query_text],
                n_results=min(n_results, count),
            )
            docs = (res.get("documents") or [[]])[0]
            metas = (res.get("metadatas") or [[]])[0]

            if not docs:
                return self._no_corpus_answer(query_input.query_text)

            debug = _debug_on()
            sources = []
            for doc, meta in zip(docs, metas):
                excerpt = doc.strip().replace("\n", " ")
                short = excerpt[:300] + ("..." if len(excerpt) > 300 else "")
                src = {
                    "filename": str((meta or {}).get("filename", "unknown")),
                    "page": str((meta or {}).get("page", "?")),
                    "excerpt": short,
                }
                if debug:
                    src["chunk_preview"] = excerpt[:500]
                sources.append(src)

            # Confidence rises with corroborating sources (spec heuristic).
            confidence = round(min(0.95, 0.50 + 0.10 * len(sources)), 3)

            answer, _used_llm = self._grounded_answer(
                query_input.query_text, docs, metas)
            return KnowledgeResult(
                answer=answer, sources=sources, confidence=confidence)
        except Exception as e:  # noqa: BLE001
            return KnowledgeResult(
                answer="Knowledge query failed.",
                sources=[], confidence=0.0, error=str(e))


if __name__ == "__main__":
    r = KnowledgeAgent().query(
        QueryInput(query_text="confined space entry requirements"))
    print("conf:", r.confidence, "sources:", len(r.sources))
    print(r.answer)
