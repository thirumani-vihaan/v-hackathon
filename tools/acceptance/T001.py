"""T001 acceptance: folders and __init__.py exist."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DIRS = ["compliance", "knowledge_base/raw", "knowledge_base/processed", "agents",
        "utils", "ui", "tests", "data", "logs", "tools", "tools/acceptance"]
INITS = ["agents/__init__.py", "utils/__init__.py", "ui/__init__.py",
         "tests/__init__.py", "compliance/__init__.py", "knowledge_base/__init__.py"]


def main():
    bad = []
    for d in DIRS:
        if not os.path.isdir(os.path.join(ROOT, d)):
            bad.append(f"missing dir: {d}")
    for i in INITS:
        if not os.path.isfile(os.path.join(ROOT, i)):
            bad.append(f"missing init: {i}")
    if bad:
        print("\n".join(bad))
        return 1
    print("T001 PASS: all directories and __init__.py present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
