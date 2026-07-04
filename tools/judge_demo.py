"""One-command judge demo: narrates the full IndustrialSafetyAI story end-to-end,
offline and deterministic. Run:  python -m tools.judge_demo

Ties together the PS1 headline benchmark, the Vizag counterfactual, a live compound
scan, permit-proximity knowledge-graph intelligence, and incident-pattern analytics.
ASCII-only output so it renders on any Windows console.
"""
import os
import random
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from schema import SensorInput, ComplianceInput  # noqa: E402
from agents.safety_agent import SafetyAgent  # noqa: E402
from agents.compliance_agent import ComplianceAgent  # noqa: E402
from utils.sensor_simulator import vizag_critical_reading  # noqa: E402
from utils import knowledge_graph as kg  # noqa: E402
from utils import incident_intelligence as ii  # noqa: E402
from tools import benchmark as bench  # noqa: E402
from utils.scenario_generator import generate_scenario  # noqa: E402


def _rule(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def main():
    print("IndustrialSafetyAI -- Judge Demo (offline, deterministic)")
    print("Thesis: every system at Vizag Steel worked; the people still died because")
    print("nothing connected the signals in time. We are that missing layer.")

    _rule("1. HEADLINE BENCHMARK -- false-negative reduction (the metric that saves lives)")
    s = bench.run(seed=42)
    h = s["headline"]
    print(f"  Dataset: {s['dataset_size']} physics-labeled scenarios "
          f"({s['incidents']} incident / {s['safe']} safe)")
    print(f"  Single-sensor operational miss rate : "
          f"{h['single_sensor_operational_false_negative_rate']:.0%}")
    print(f"  Our compound+predictive miss rate   : "
          f"{h['compound_predictive_operational_false_negative_rate']:.0%}")
    print(f"  Reduction                           : "
          f"{h['false_negative_reduction_pct']:.0f} percentage points")
    print(f"  Median early warning                : "
          f"{h['compound_median_lead_minutes']} min")
    print(f"  False-alarm rate (ours)             : "
          f"{h['compound_pred_false_alarm_rate']:.0%}  "
          f"(sensitive single-sensor: {h['single_low_false_alarm_rate']:.0%})")

    _rule("2. VIZAG COUNTERFACTUAL -- hot work in a confined space, gas below every alarm")
    cf = generate_scenario("conjunction_incident", rng=random.Random(7))
    k = cf["incident_step"]
    sh = bench.single_detect(cf["readings"], "high_alarm")
    cp = bench.compound_pred_detect(cf)
    spm = cf["seconds_per_step"]
    peak = max(r.gas_ppm for r in cf["readings"])
    print(f"  Peak gas: {peak:.0f} ppm (single high-alarm setpoint: 100 ppm)")
    print(f"  Incident onset            : minute {k}")
    print(f"  Single-sensor alarm       : {'never' if sh is None else f'minute {sh}'}"
          f"  <-- {'MISS' if sh is None or sh >= k else 'late'}")
    lead = None if cp is None else round((k - cp) * spm / 60.0, 1)
    print(f"  Our engine alerts         : "
          f"{'-' if cp is None else f'minute {cp}'}"
          f"{'' if lead is None else f'  (+{lead} min to evacuate)'}")

    _rule("3. LIVE COMPOUND SCAN -- the Vizag critical reading")
    reading = vizag_critical_reading()
    alert = SafetyAgent().assess(SensorInput(reading=reading, active_permits=["hot_work"]))
    comp = ComplianceAgent().evaluate(
        ComplianceInput(sensor=reading, active_permits=["hot_work"]))
    print(f"  Risk score        : {alert.risk_score}/100")
    print(f"  Triggered rules   : {', '.join(alert.triggered_rules)}")
    print(f"  Compliance        : highest severity = {comp.highest_severity}, "
          f"pass = {comp.pass_status}")
    if comp.violations:
        v = max(comp.violations, key=lambda x: {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3,
                                                'CRITICAL': 4}[x.severity])
        print(f"  Top violation     : {v.rule_id} {v.name}")
        print(f"  Regulatory refs   : {v.oisd_reference}")

    _rule("4. PERMIT-PROXIMITY INTELLIGENCE (knowledge graph)")
    state = {
        "Zone-B-Process": {"gas_ppm": 88, "permits": []},
        "Zone-C-Confined": {"gas_ppm": 20, "permits": ["hot_work", "maintenance"]},
    }
    conflicts = kg.permits_near_hazard(state)
    if not conflicts:
        print("  No permit-proximity conflicts.")
    for c in conflicts:
        print(f"  [{c['severity']}] {c['message']}")

    _rule("5. INCIDENT PATTERN INTELLIGENCE (near-miss corpus)")
    incs = ii.load_incidents()
    print(f"  Corpus: {len(incs)} incidents. Top prevention priorities:")
    for p in ii.prevention_priorities(incs, top_k=3):
        print("   - " + p)
    print("  Incidents similar to the live state:")
    for m in ii.similar_incidents(reading.gas_ppm, reading.oxygen_pct, reading.zone,
                                  ["hot_work"], top_k=2):
        print(f"   - {m['id']} (score {m['match_score']}): {m['description']}")

    print("\n" + "=" * 72)
    print("Fully offline. Auditable. It would have flagged Vizag hours early.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
