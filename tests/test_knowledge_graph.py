"""Tests for the plant knowledge graph (P1b): permit-proximity intelligence, spatial
adjacency reasoning, and DOT rendering. Deterministic and offline.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils import knowledge_graph as kg  # noqa: E402


def test_graph_builds_with_expected_node_kinds():
    g = kg.build_plant_graph({
        "Zone-B-Process": {"gas_ppm": 88, "permits": ["hot_work"]},
    })
    kinds = {d.get("kind") for _, d in g.nodes(data=True)}
    assert {"zone", "equipment", "permit"} <= kinds
    # adjacency edges present
    assert any(d.get("relation") == "adjacent" for _, _, d in g.edges(data=True))


def test_same_zone_hot_work_and_gas_is_flagged():
    conflicts = kg.permits_near_hazard({
        "Zone-B-Process": {"gas_ppm": 90, "permits": ["hot_work"]},
    })
    assert conflicts
    top = conflicts[0]
    assert top["permit"] == "hot_work"
    assert top["severity"] == "CRITICAL"
    assert top["proximity"] == "same"


def test_adjacent_zone_hazard_is_flagged():
    # hot work in the confined zone, elevated gas in the adjacent process zone
    conflicts = kg.permits_near_hazard({
        "Zone-C-Confined": {"gas_ppm": 10, "permits": ["hot_work"]},
        "Zone-B-Process": {"gas_ppm": 88, "permits": []},
    })
    assert any(c["proximity"] == "adjacent" and c["hazard_zone"] == "Zone-B-Process"
               for c in conflicts)


def test_no_conflict_when_gas_low():
    conflicts = kg.permits_near_hazard({
        "Zone-B-Process": {"gas_ppm": 20, "permits": ["hot_work", "maintenance"]},
    })
    assert conflicts == []


def test_conflicts_sorted_critical_first():
    conflicts = kg.permits_near_hazard({
        "Zone-B-Process": {"gas_ppm": 90, "permits": ["hot_work"]},   # CRITICAL same
        "Zone-A-Tank-Farm": {"gas_ppm": 60, "permits": ["maintenance"]},  # lower
    })
    sev = [c["severity"] for c in conflicts]
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    assert sev == sorted(sev, key=lambda s: order[s])


def test_non_hazard_permits_ignored():
    conflicts = kg.permits_near_hazard({
        "Zone-B-Process": {"gas_ppm": 90, "permits": ["cold_work", "general"]},
    })
    assert conflicts == []


def test_to_dot_is_graphviz_string():
    g = kg.build_plant_graph({"Zone-B-Process": {"gas_ppm": 88, "permits": ["hot_work"]}})
    dot = kg.to_dot(g)
    assert dot.startswith("graph plant {")
    assert "Zone-B-Process" in dot and "hot_work" in dot
