"""Smoke test for the one-command judge demo runner: it must execute end-to-end,
offline and deterministically, and return exit code 0.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def test_judge_demo_runs_clean(capsys):
    from tools import judge_demo
    rc = judge_demo.main()
    assert rc == 0
    out = capsys.readouterr().out
    # the narrative hits every capability section
    assert "HEADLINE BENCHMARK" in out
    assert "VIZAG COUNTERFACTUAL" in out
    assert "PERMIT-PROXIMITY INTELLIGENCE" in out
    assert "INCIDENT PATTERN INTELLIGENCE" in out
    # and the headline reduction is real
    assert "percentage points" in out
