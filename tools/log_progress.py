"""Append a progress line to logs/agent_progress.log.

Usage: python tools/log_progress.py T009 PASS "orchestrator routing works"
"""
import sys
import os
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(_ROOT, "logs")
LOG_PATH = os.path.join(LOG_DIR, "agent_progress.log")


def log_progress(task_id, result, note=""):
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.utcnow().isoformat()
    line = f"{ts} {task_id} {result} {note}".rstrip()
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return line


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python tools/log_progress.py <TASK_ID> <PASS|FAIL> [note...]")
        sys.exit(2)
    tid = sys.argv[1]
    res = sys.argv[2]
    note = " ".join(sys.argv[3:])
    print(log_progress(tid, res, note))
