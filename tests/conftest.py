import os
import sys
import subprocess
import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def pytest_sessionstart(session):
    """
    Called after the Session object has been created and
    before performing collection and entering the run loop.
    Ensures required offline assets are downloaded/built so tests don't fail on a fresh clone.
    """
    # 1. Build ChromaDB if empty
    db_path = os.path.join(_ROOT, "knowledge_base", "chroma_db")
    if not os.path.isdir(db_path) or not os.listdir(db_path):
        print("\n[conftest] ChromaDB is missing. Building it now...")
        subprocess.run([sys.executable, os.path.join(_ROOT, "knowledge_base", "build_db.py")], check=False)

    # 2. Download ViT if missing
    vit_path = os.path.join(_ROOT, "models", "vit_local")
    if not os.path.isdir(vit_path):
        print("\n[conftest] ViT models missing. Downloading...")
        subprocess.run([sys.executable, os.path.join(_ROOT, "models", "download_vit.py")], check=False)
        subprocess.run([sys.executable, os.path.join(_ROOT, "models", "train_vit_head.py")], check=False)
