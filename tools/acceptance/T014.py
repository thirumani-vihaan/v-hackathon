"""T014 acceptance: build the ChromaDB knowledge base and verify it has docs."""
import os
import sys
import subprocess
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def main():
    try:
        # Ensure a source PDF exists.
        raw = os.path.join(ROOT, "knowledge_base", "raw")
        pdfs = [f for f in os.listdir(raw) if f.lower().endswith(".pdf")] \
            if os.path.isdir(raw) else []
        if not pdfs:
            subprocess.run([sys.executable,
                            os.path.join("tools", "generate_synthetic_pdf.py")],
                           cwd=ROOT, check=True)

        # Build the DB.
        proc = subprocess.run(
            [sys.executable, os.path.join("knowledge_base", "build_db.py")],
            cwd=ROOT, capture_output=True, text=True)
        print(proc.stdout[-1200:])
        if proc.returncode != 0:
            print(proc.stderr[-1200:])
            return 1

        # Verify collection populated.
        from agents.knowledge_agent import KnowledgeAgent
        agent = KnowledgeAgent()
        count = agent._collection.count()
        assert count > 0, "collection is empty after build"
        print(f"collection count = {count}")
    except Exception:
        traceback.print_exc()
        return 1
    print("T014 PASS: knowledge base built")
    return 0


if __name__ == "__main__":
    sys.exit(main())
