"""T007 acceptance: KnowledgeAgent RAG returns sources>0, confidence>0, and a
relevant answer for 'confined space entry requirements'."""
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def main():
    try:
        from schema import QueryInput, KnowledgeResult
        from agents.knowledge_agent import KnowledgeAgent

        agent = KnowledgeAgent()
        res = agent.query(QueryInput(query_text="confined space entry requirements"))
        assert isinstance(res, KnowledgeResult), "must return KnowledgeResult"
        if res.error:
            print("knowledge error:", res.error)
        assert len(res.sources) > 0, "expected at least one citation source"
        assert res.confidence > 0, f"expected confidence>0, got {res.confidence}"

        combined = (res.answer + " " +
                    " ".join(s.get("excerpt", "") for s in res.sources)).lower()
        assert any(term in combined for term in
                   ("confined", "rescue", "entry", "space")), \
            "answer/sources not relevant to confined space"

        for s in res.sources:
            assert "filename" in s and "page" in s and "excerpt" in s
    except Exception:
        traceback.print_exc()
        return 1
    print("T007 PASS: KnowledgeAgent RAG citations OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
