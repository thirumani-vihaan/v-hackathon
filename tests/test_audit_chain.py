"""Tests for the tamper-evident SHA-256 hash-chained audit log."""
import os
import sys
import json

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils import audit_logger as al  # noqa: E402


def test_chain_valid_after_appends(tmp_path):
    p = str(tmp_path / "log.jsonl")
    for i in range(3):
        al.append_event({"type": "t", "i": i}, path=p)
    res = al.verify_chain(p)
    assert res["valid"] is True
    assert res["entries"] == 3
    assert res["chained"] == 3


def test_first_entry_links_to_genesis(tmp_path):
    p = str(tmp_path / "log.jsonl")
    al.append_event({"type": "t", "i": 0}, path=p)
    first = al.read_last_n(1, p)[-1]
    assert first["prev_hash"] == "0" * 64
    assert len(first["entry_hash"]) == 64


def test_tampering_breaks_chain(tmp_path):
    p = str(tmp_path / "log.jsonl")
    for i in range(4):
        al.append_event({"type": "t", "i": i}, path=p)
    lines = open(p, encoding="utf-8").read().splitlines()
    entry = json.loads(lines[1])
    entry["i"] = 999  # tamper with content but keep the old hash
    lines[1] = json.dumps(entry, ensure_ascii=False)
    open(p, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    res = al.verify_chain(p)
    assert res["valid"] is False
    assert res["broken_at"] == 1


def test_secrets_are_never_written(tmp_path):
    p = str(tmp_path / "log.jsonl")
    al.append_event({"type": "t", "api_key": "SECRET", "token": "X"}, path=p)
    entry = al.read_last_n(1, p)[-1]
    assert "api_key" not in entry and "token" not in entry
    assert al.verify_chain(p)["valid"] is True


def test_legacy_entries_tolerated(tmp_path):
    p = str(tmp_path / "log.jsonl")
    # a legacy, unchained line (no entry_hash), then chained appends
    with open(p, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "legacy", "note": "old"}) + "\n")
    al.append_event({"type": "t", "i": 1}, path=p)
    al.append_event({"type": "t", "i": 2}, path=p)
    res = al.verify_chain(p)
    assert res["valid"] is True
    assert res["entries"] == 3
    assert res["chained"] == 2
