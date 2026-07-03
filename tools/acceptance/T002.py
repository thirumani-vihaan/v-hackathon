"""T002 acceptance: schema imports + core third-party packages import."""
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def main():
    try:
        import schema
        from schema import (SensorReading, Hazard, VisionResult, SafetyAlert,
                            ComplianceResult, KnowledgeResult, OrchestratorResult)
        SensorReading(gas_ppm=5, temp_c=30, oxygen_pct=20.9, humidity_pct=50,
                      permit_type="general", worker_count=1, zone="Z",
                      timestamp="2026-07-03T00:00:00")
        import chromadb  # noqa: F401
        import langgraph  # noqa: F401
        import langchain  # noqa: F401
        import google.generativeai  # noqa: F401
        import streamlit  # noqa: F401
        import folium  # noqa: F401
        import reportlab  # noqa: F401
        import pypdf  # noqa: F401
        import sentence_transformers  # noqa: F401
        import torch  # noqa: F401
        import cv2  # noqa: F401
        import pandas  # noqa: F401
        import numpy  # noqa: F401
    except Exception:
        traceback.print_exc()
        return 1
    print("T002 PASS: schema + core packages import")
    return 0


if __name__ == "__main__":
    sys.exit(main())
