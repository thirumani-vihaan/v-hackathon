"""Task state helpers for tasks.json. No jq — pure Python."""
import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS_PATH = os.path.join(_ROOT, "tasks.json")


def load_tasks():
    with open(TASKS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tasks(tasks):
    with open(TASKS_PATH, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)
        f.write("\n")


def get_task(task_id):
    for t in load_tasks():
        if t["id"] == task_id:
            return t
    return None


def set_status(task_id, status):
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["status"] = status
            break
    save_tasks(tasks)


def set_note(task_id, note):
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["note"] = note
            break
    save_tasks(tasks)


def deps_done(task):
    tasks = {t["id"]: t for t in load_tasks()}
    for dep in task.get("deps", []):
        d = tasks.get(dep)
        if d is None or d.get("status") != "done":
            return False
    return True


def next_pending_task_id():
    for t in load_tasks():
        if t.get("status", "pending") == "pending" and deps_done(t):
            return t["id"]
    return None


def all_done():
    return all(t.get("status") == "done" for t in load_tasks())


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        for t in load_tasks():
            print(f"{t['id']:6} {t.get('status','pending'):11} {t['title']}")
        print("next_pending:", next_pending_task_id())
        print("all_done:", all_done())
