"""Run the acceptance command for a task id and mirror its exit code.

Usage: python tools/run_acceptance.py T009
"""
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from task_state import get_task  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("usage: python tools/run_acceptance.py <TASK_ID>")
        return 2
    task_id = sys.argv[1]
    task = get_task(task_id)
    if task is None:
        print(f"unknown task id: {task_id}")
        return 2
    cmd = task["acceptance"]
    print(f"=== acceptance for {task_id}: {cmd}")
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if proc.stdout:
        print("--- stdout ---")
        print(proc.stdout)
    if proc.stderr:
        print("--- stderr ---")
        print(proc.stderr)
    print(f"=== exit code: {proc.returncode}")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
