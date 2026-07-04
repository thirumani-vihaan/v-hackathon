"""Plant knowledge graph: equipment - permit - zone - gas - risk relationships.

WHY A GRAPH (and not just more RAG)
-----------------------------------
PS1 explicitly suggests "Knowledge Graphs (equipment-permit-risk relationships)" and a
"Digital Permit Intelligence Agent" that flags "hot work permits issued in proximity to
areas with elevated gas readings". Those are graph questions, not text questions: they
require traversing spatial adjacency between zones and joining it with active-permit and
live-gas state. One graph therefore collapses THREE PS1 components into a single
queryable structure:
  * Digital Permit Intelligence  (dangerous simultaneous operations)
  * Compound risk correlation    (permit x gas x proximity)
  * Geospatial proximity          (adjacent-zone hazard spillover)

Built on networkx (already a project dependency). Deterministic, offline, explainable —
every flagged conflict names the exact permit, its zone, and the adjacent hazard zone.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import networkx as nx

# ---- static plant model (a small, realistic coke-oven / tank-farm layout) ----
ZONES = ["Zone-A-Tank-Farm", "Zone-B-Process", "Zone-C-Confined", "Zone-D-Substation"]

ADJACENCY: Dict[str, List[str]] = {
    "Zone-A-Tank-Farm": ["Zone-B-Process"],
    "Zone-B-Process": ["Zone-A-Tank-Farm", "Zone-C-Confined", "Zone-D-Substation"],
    "Zone-C-Confined": ["Zone-B-Process", "Zone-D-Substation"],
    "Zone-D-Substation": ["Zone-B-Process", "Zone-C-Confined"],
}

EQUIPMENT: Dict[str, List[str]] = {
    "Zone-A-Tank-Farm": ["Crude Storage Tank T-101", "Vapour Recovery Unit"],
    "Zone-B-Process": ["Coke Oven Battery", "Reactor R-201"],
    "Zone-C-Confined": ["Reaction Vessel V-301", "Sump Pit"],
    "Zone-D-Substation": ["Transformer TR-401", "Switchgear"],
}

# Permits that constitute an ignition or intrusive-work hazard near accumulating gas.
IGNITION_PERMITS = ("hot_work", "electrical")
INTRUSIVE_PERMITS = ("maintenance", "confined_space")

GAS_ELEVATED = 50.0     # ppm; matches the compound engine's gas caution line
GAS_CRITICAL = 80.0


def build_plant_graph(zone_states: Optional[Dict[str, Dict]] = None) -> nx.Graph:
    """Build the plant graph. `zone_states` maps zone -> {gas_ppm, oxygen_pct, permits}.

    Node kinds: 'zone', 'equipment', 'permit'. Zone nodes carry live gas/oxygen and a
    derived risk level; permit nodes link to the zone in which they are active.
    """
    zone_states = zone_states or {}
    g = nx.Graph()
    for z in ZONES:
        state = zone_states.get(z, {})
        gas = float(state.get("gas_ppm", 0.0))
        risk = ("critical" if gas >= GAS_CRITICAL else
                "elevated" if gas >= GAS_ELEVATED else "normal")
        g.add_node(z, kind="zone", gas_ppm=gas,
                   oxygen_pct=float(state.get("oxygen_pct", 20.9)), risk=risk)
        for eq in EQUIPMENT.get(z, []):
            g.add_node(eq, kind="equipment")
            g.add_edge(z, eq, relation="contains")
        for p in state.get("permits", []) or []:
            pnode = f"permit:{p}@{z}"
            g.add_node(pnode, kind="permit", permit=p, zone=z)
            g.add_edge(pnode, z, relation="active_in")
    # spatial adjacency edges
    for z, neighbours in ADJACENCY.items():
        for n in neighbours:
            if g.has_node(z) and g.has_node(n):
                g.add_edge(z, n, relation="adjacent")
    return g


def permits_near_hazard(zone_states: Dict[str, Dict],
                        gas_threshold: float = GAS_ELEVATED) -> List[Dict]:
    """Digital Permit Intelligence: flag ignition/intrusive permits active in a zone
    that is itself, or is ADJACENT to, a zone with elevated gas.

    Returns a list of conflict dicts (highest severity first). This is the query no
    single sensor and no flat document search can answer — it needs the graph.
    """
    conflicts: List[Dict] = []
    for z, state in zone_states.items():
        for p in state.get("permits", []) or []:
            if p not in IGNITION_PERMITS + INTRUSIVE_PERMITS:
                continue
            # check the permit's own zone and every adjacent zone for elevated gas
            candidates = [(z, "same")] + [(n, "adjacent") for n in ADJACENCY.get(z, [])]
            for hz, proximity in candidates:
                gas = float(zone_states.get(hz, {}).get("gas_ppm", 0.0))
                if gas < gas_threshold:
                    continue
                ignition = p in IGNITION_PERMITS
                if gas >= GAS_CRITICAL and (ignition or proximity == "same"):
                    severity = "CRITICAL"
                elif ignition or proximity == "same":
                    severity = "HIGH"
                else:
                    severity = "MEDIUM"
                conflicts.append({
                    "permit": p,
                    "permit_zone": z,
                    "hazard_zone": hz,
                    "proximity": proximity,
                    "gas_ppm": round(gas, 1),
                    "severity": severity,
                    "message": (f"{p.replace('_', ' ')} permit in {z} is "
                                f"{proximity} to elevated gas ({gas:.0f} ppm) in {hz}"),
                })
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    conflicts.sort(key=lambda c: (order[c["severity"]], -c["gas_ppm"]))
    # de-duplicate identical (permit, permit_zone, hazard_zone)
    seen = set()
    unique = []
    for c in conflicts:
        key = (c["permit"], c["permit_zone"], c["hazard_zone"])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def to_dot(g: nx.Graph) -> str:
    """Render the graph as Graphviz DOT for Streamlit's st.graphviz_chart (no extra deps)."""
    risk_fill = {"critical": "#e74c3c", "elevated": "#e67e22", "normal": "#2ecc71"}
    lines = ["graph plant {", '  rankdir=LR;', '  node [style=filled, fontname="Arial"];']
    for n, d in g.nodes(data=True):
        kind = d.get("kind")
        if kind == "zone":
            fill = risk_fill.get(d.get("risk", "normal"), "#bdc3c7")
            label = f'{n}\\n{d.get("gas_ppm", 0):.0f} ppm'
            lines.append(f'  "{n}" [shape=box, fillcolor="{fill}", '
                         f'fontcolor=white, label="{label}"];')
        elif kind == "equipment":
            lines.append(f'  "{n}" [shape=ellipse, fillcolor="#ecf0f1"];')
        else:  # permit
            lines.append(f'  "{n}" [shape=diamond, fillcolor="#f1c40f", '
                         f'label="{d.get("permit")}"];')
    for u, v, d in g.edges(data=True):
        rel = d.get("relation", "")
        style = "dashed" if rel == "adjacent" else "solid"
        lines.append(f'  "{u}" -- "{v}" [style={style}, label="{rel}"];')
    lines.append("}")
    return "\n".join(lines)


if __name__ == "__main__":
    demo = {
        "Zone-B-Process": {"gas_ppm": 88, "permits": []},
        "Zone-C-Confined": {"gas_ppm": 20, "permits": ["hot_work", "maintenance"]},
        "Zone-A-Tank-Farm": {"gas_ppm": 30, "permits": []},
    }
    for c in permits_near_hazard(demo):
        print(c["severity"], "-", c["message"])
    g = build_plant_graph(demo)
    print("nodes:", g.number_of_nodes(), "edges:", g.number_of_edges())
