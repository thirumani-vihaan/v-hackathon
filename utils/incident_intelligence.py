"""Incident Pattern Intelligence — mines a near-miss / incident corpus for recurring
patterns and retrieves past incidents similar to the current plant state.

PS1 asks for a "RAG-powered agent that cross-references near-miss reports, historical
incident data, and OISD/Factory Act regulatory guidance to identify recurring patterns
that manual investigations miss — and surfaces them as actionable prevention priorities."

This module is the deterministic, offline core of that capability: no embeddings, no
network, fully auditable. It complements the ChromaDB manual-RAG (unstructured guidance)
with structured incident analytics, and pairs with the knowledge graph (incidents map to
zones and permit combinations).
"""
from __future__ import annotations

import json
import os
from collections import Counter
from itertools import combinations
from typing import Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_CORPUS = os.path.join(os.path.dirname(_HERE), "knowledge_base", "incidents.json")

_SEVERITY_WEIGHT = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "NEAR_MISS": 1}
HAZARD_PERMITS = ("hot_work", "confined_space", "maintenance", "electrical",
                  "shift_changeover")


def load_incidents(path: str = _CORPUS) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _weight(inc: Dict) -> int:
    return _SEVERITY_WEIGHT.get(inc.get("severity", "MEDIUM"), 2)


def recurring_patterns(incidents: Optional[List[Dict]] = None,
                       min_count: int = 2) -> List[Dict]:
    """Surface recurring, severity-weighted patterns as prevention priorities.

    Considers single hazardous permits, co-occurring permit pairs, and root causes.
    Each pattern is scored by how often it appears AND how severe those incidents were,
    so the ranking reflects risk, not just frequency.
    """
    incidents = incidents or load_incidents()
    total = len(incidents) or 1
    counts: Counter = Counter()
    weighted: Counter = Counter()

    for inc in incidents:
        w = _weight(inc)
        permits = [p for p in inc.get("permits", []) if p in HAZARD_PERMITS]
        # single permits
        for p in set(permits):
            key = ("permit", p)
            counts[key] += 1
            weighted[key] += w
        # co-occurring permit pairs (the compound signal)
        for a, b in combinations(sorted(set(permits)), 2):
            key = ("permit_pair", f"{a}+{b}")
            counts[key] += 1
            weighted[key] += w
        # root cause
        rc = inc.get("root_cause")
        if rc:
            key = ("root_cause", rc)
            counts[key] += 1
            weighted[key] += w

    patterns = []
    for key, cnt in counts.items():
        if cnt < min_count:
            continue
        kind, label = key
        patterns.append({
            "kind": kind,
            "pattern": label,
            "count": cnt,
            "share": round(cnt / total, 3),
            "severity_score": weighted[key],
            "priority": round(weighted[key] * cnt / total, 2),
        })
    patterns.sort(key=lambda p: (-p["priority"], -p["count"]))
    return patterns


def prevention_priorities(incidents: Optional[List[Dict]] = None,
                          top_k: int = 5) -> List[str]:
    """Human-readable prevention priorities derived from recurring patterns."""
    out = []
    for p in recurring_patterns(incidents)[:top_k]:
        if p["kind"] == "permit_pair":
            a, b = p["pattern"].split("+")
            out.append(f"Simultaneous {a.replace('_', ' ')} + {b.replace('_', ' ')} "
                       f"drove {p['count']} incidents ({p['share']:.0%}) — require a "
                       f"combined-permit review before authorising both.")
        elif p["kind"] == "root_cause":
            out.append(f"Root cause '{p['pattern'].replace('_', ' ')}' recurs in "
                       f"{p['count']} incidents — target it as a prevention priority.")
        else:
            out.append(f"{p['pattern'].replace('_', ' ').title()} appears in "
                       f"{p['count']} incidents ({p['share']:.0%}).")
    return out


def similar_incidents(gas_ppm: float, oxygen_pct: float, zone: str,
                      permits: List[str], incidents: Optional[List[Dict]] = None,
                      top_k: int = 3) -> List[Dict]:
    """Retrieve past incidents most similar to the current plant state (structured
    grounded recall). Score rewards permit overlap, same zone, and gas/oxygen proximity.
    """
    incidents = incidents or load_incidents()
    pset = {p for p in permits if p}
    scored = []
    for inc in incidents:
        ipermits = set(inc.get("permits", []))
        overlap = len(pset & ipermits)
        score = overlap * 3.0
        if inc.get("zone") == zone:
            score += 2.0
        score += max(0.0, 2.0 - abs(inc.get("gas_ppm", 0) - gas_ppm) / 20.0)
        score += max(0.0, 1.5 - abs(inc.get("oxygen_pct", 20.9) - oxygen_pct) / 2.0)
        if score > 0:
            scored.append((score, inc))
    scored.sort(key=lambda t: -t[0])
    results = []
    for score, inc in scored[:top_k]:
        r = dict(inc)
        r["match_score"] = round(score, 2)
        results.append(r)
    return results


if __name__ == "__main__":
    incs = load_incidents()
    print(f"corpus: {len(incs)} incidents\n")
    print("Top prevention priorities:")
    for p in prevention_priorities(incs):
        print(" -", p)
    print("\nSimilar to current state (gas=70, O2=18.5, confined, hot_work+maintenance):")
    for m in similar_incidents(70, 18.5, "Zone-C-Confined",
                               ["confined_space", "hot_work", "maintenance"]):
        print(f"  {m['id']} (score {m['match_score']}): {m['description']}")
