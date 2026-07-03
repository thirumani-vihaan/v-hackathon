"""Autonomous task loop for IndustrialSafetyAI.

Repeatedly picks the next pending task whose dependencies are done, runs its
acceptance script, and marks it done on pass. On failure it records an attempt;
after 3 failed attempts on the same task it STOPS and prints full diagnostics
(failing task id, acceptance command, stdout/stderr).

This driver does not modify source files — fixes are applied by the operator
between runs. It is safe to re-run; passed tasks are skipped.
"""
import os
import sys
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)

import task_state  # noqa: E402
from log_progress import log_progress  # noqa: E402

MAX_ATTEMPTS = 3


def _child_env():
    """Force UTF-8 stdio so acceptance scripts that print Unicode (e.g. arrows)
    don't crash on the Windows cp1252 console."""
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_one(task):
    tid = task["id"]
    cmd = task["acceptance"]
    print(f"\n=== running {tid}: {task['title']}")
    print(f"    acceptance: {cmd}")
    proc = subprocess.run(cmd, shell=True, cwd=_ROOT, capture_output=True, text=True,
                          env=_child_env())
    ok = proc.returncode == 0
    tail_out = proc.stdout[-1200:]
    tail_err = proc.stderr[-1200:]
    if tail_out:
        print(tail_out)
    if not ok and tail_err:
        print("--- stderr ---")
        print(tail_err)
    note = ("ok" if ok else f"exit={proc.returncode}").replace("\n", " ")
    log_progress(tid, "PASS" if ok else "FAIL", note)
    return ok, proc


def main():
    while True:
        tid = task_state.next_pending_task_id()
        if tid is None:
            if task_state.all_done():
                print("\nALL TASKS DONE")
                return 0
            print("\nNo ready pending task, but not all done (blocked). Remaining:")
            for t in task_state.load_tasks():
                if t.get("status") != "done":
                    print(f"  {t['id']} status={t.get('status')} deps={t.get('deps')}")
            return 2

        task = task_state.get_task(tid)
        ok, proc = run_one(task)
        if ok:
            task_state.set_status(tid, "done")
            task_state.set_note(tid, "passed")
            continue

        # failure path: bump attempts
        tasks = task_state.load_tasks()
        for t in tasks:
            if t["id"] == tid:
                t["attempts"] = t.get("attempts", 0) + 1
                attempts = t["attempts"]
                break
        task_state.save_tasks(tasks)

        if attempts >= MAX_ATTEMPTS:
            print("\n" + "=" * 60)
            print(f"STOP: task {tid} failed {attempts} attempts")
            print(f"acceptance command: {task['acceptance']}")
            print("--- full stdout ---")
            print(proc.stdout)
            print("--- full stderr ---")
            print(proc.stderr)
            print("=" * 60)
            task_state.set_status(tid, "failed")
            return 1
        else:
            print(f"\n{tid} failed (attempt {attempts}/{MAX_ATTEMPTS}); "
                  f"stopping for operator fix.")
            return 3


if __name__ == "__main__":
    sys.exit(main())
