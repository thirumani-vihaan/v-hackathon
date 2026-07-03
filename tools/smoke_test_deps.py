"""Dependency smoke test for IndustrialSafetyAI.

Verifies every critical dependency imports and behaves, prewarms the HF embedding
model, exercises both ChromaDB API shapes, and enforces the LangGraph
updates-only rule. Exit 0 on success, 1 on failure.
"""
import os
import sys
import traceback

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)


def _setup_env():
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(_ROOT, ".env"))
    except Exception:
        pass
    cache = os.path.join(_ROOT, "data", "hf_cache")
    os.makedirs(cache, exist_ok=True)
    os.environ["HF_HOME"] = cache
    os.environ["SENTENCE_TRANSFORMERS_HOME"] = cache
    os.makedirs(os.path.join(_ROOT, "data", "chroma_db"), exist_ok=True)


def check_imports():
    import langgraph  # noqa: F401
    import langchain  # noqa: F401
    import chromadb  # noqa: F401
    import google.generativeai  # noqa: F401
    import streamlit  # noqa: F401
    import folium  # noqa: F401
    import reportlab  # noqa: F401
    import pypdf  # noqa: F401
    import sentence_transformers  # noqa: F401
    print("[ok] core imports")


def check_chromadb():
    import chromadb
    persist = os.path.join(_ROOT, "data", "chroma_db")
    try:
        from chromadb.config import Settings
        client = chromadb.PersistentClient(
            path=persist, settings=Settings(anonymized_telemetry=False))
    except Exception:
        client = chromadb.PersistentClient(path=persist)
    col = client.get_or_create_collection("smoke")
    assert col is not None
    print("[ok] chromadb PersistentClient + get_or_create_collection")


def check_embedding_prewarm():
    try:
        from chromadb.utils.embedding_functions import (
            SentenceTransformerEmbeddingFunction,
        )
        ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        vec = ef(["test sentence"])
    except Exception as e:
        print(f"[info] chroma EF path unavailable ({e}); using sentence_transformers")
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer("all-MiniLM-L6-v2")
        vec = m.encode(["test sentence"])
    assert vec is not None and len(vec) >= 1
    print("[ok] embedding prewarm (all-MiniLM-L6-v2)")


def check_langgraph_updates_only():
    from typing import TypedDict
    from langgraph.graph import StateGraph, END

    class State(TypedDict):
        x: str

    def node(state):
        # MUST NOT mutate incoming state; return an update dict only.
        assert isinstance(state, dict)
        return {"x": "y"}

    g = StateGraph(State)
    g.add_node("n", node)
    g.set_entry_point("n")
    g.add_edge("n", END)
    app = g.compile()
    out = app.invoke({"x": "z"})
    assert out.get("x") == "y", f"unexpected output: {out}"
    print("[ok] langgraph StateGraph updates-only node")


def main():
    _setup_env()
    steps = [
        ("imports", check_imports),
        ("chromadb", check_chromadb),
        ("embedding", check_embedding_prewarm),
        ("langgraph", check_langgraph_updates_only),
    ]
    for name, fn in steps:
        try:
            fn()
        except Exception:
            print(f"[FAIL] {name}")
            traceback.print_exc()
            return 1
    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
