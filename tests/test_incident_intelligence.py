"""Tests for Incident Pattern Intelligence (P2): recurring-pattern mining and
similar-incident retrieval over the near-miss corpus. Deterministic and offline.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils import incident_intelligence as ii  # noqa: E402


def test_corpus_loads():
    incs = ii.load_incidents()
    assert len(incs) >= 15
    for inc in incs:
        assert {"id", "zone", "permits", "gas_ppm", "severity"} <= set(inc)


def test_recurring_patterns_sorted_by_priority():
    pats = ii.recurring_patterns()
    assert pats
    priorities = [p["priority"] for p in pats]
    assert priorities == sorted(priorities, reverse=True)


def test_compound_permit_pair_surfaces():
    pairs = {p["pattern"] for p in ii.recurring_patterns() if p["kind"] == "permit_pair"}
    # the confined-space + maintenance conjunction is a known recurring driver
    assert "confined_space+maintenance" in pairs


def test_prevention_priorities_are_strings():
    pri = ii.prevention_priorities(top_k=5)
    assert 1 <= len(pri) <= 5
    assert all(isinstance(s, str) and s for s in pri)


def test_similar_incidents_ranks_matching_state_first():
    matches = ii.similar_incidents(
        gas_ppm=82, oxygen_pct=18.1, zone="Zone-C-Confined",
        permits=["confined_space", "hot_work", "maintenance"], top_k=3)
    assert len(matches) == 3
    assert all("match_score" in m for m in matches)
    # scores are in non-increasing order
    scores = [m["match_score"] for m in matches]
    assert scores == sorted(scores, reverse=True)
    # the top match should share the confined + hot_work + maintenance conjunction
    top = matches[0]
    assert {"confined_space", "hot_work", "maintenance"} <= set(top["permits"])


def test_similar_incidents_respects_top_k():
    assert len(ii.similar_incidents(60, 19.0, "Zone-B-Process", ["hot_work"], top_k=1)) == 1
