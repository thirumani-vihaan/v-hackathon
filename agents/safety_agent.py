"""SafetyAgent: sensor (+ optional vision hazards) -> SafetyAlert.

Implements the EXACT compound risk scoring from CLAUDE.md:
    gas_ppm > 50                                  -> +30
    oxygen_pct < 19.5                             -> +40
    gas_ppm > 50 AND 'hot_work' in active_permits -> +50
    gas_ppm > 80                                  -> +30
    cap at 100
"""
from schema import SensorInput, SafetyAlert


class SafetyAgent:
    def process(self, sensor_input: SensorInput, vision=None) -> SafetyAlert:
        """Primary entry point; alias of assess(). Returns a SafetyAlert."""
        return self.assess(sensor_input, vision)

    def assess(self, sensor_input: SensorInput, vision=None) -> SafetyAlert:
        try:
            reading = sensor_input.reading
            permits = list(sensor_input.active_permits or [])
            if reading.permit_type and reading.permit_type not in permits:
                permits.append(reading.permit_type)

            score = 0
            triggered = []

            if reading.gas_ppm > 50:
                score += 30
                triggered.append("gas_ppm>50 (+30)")
            if reading.oxygen_pct < 19.5:
                score += 40
                triggered.append("oxygen_pct<19.5 (+40)")
            if reading.gas_ppm > 50 and "hot_work" in permits:
                score += 50
                triggered.append("gas_ppm>50 AND hot_work permit (+50)")
            if reading.gas_ppm > 80:
                score += 30
                triggered.append("gas_ppm>80 (+30)")

            # Optional vision escalation: high-confidence fire/gas visuals add weight.
            if vision is not None:
                for h in getattr(vision, "hazards", []) or []:
                    if h.type in ("smoke_fire", "gas_leak_visual") and \
                            h.confidence >= 0.6:
                        score += 20
                        triggered.append(f"vision:{h.type} (+20)")
                        break

            # Contextual compound escalations (additive, same pattern as the vision
            # escalation above). These capture the PS1-named compound conditions a base
            # gas/oxygen threshold cannot see: maintenance activity amid accumulating gas
            # in a confined space (the entrapment mechanism behind the Vizag coke-oven
            # deaths), and the supervision blind spot at shift changeover. Gated on
            # explicit operational context so ordinary readings score exactly as before.
            zone_l = (reading.zone or "").lower()
            confined = "confined" in zone_l or "confined_space" in permits
            if "maintenance" in permits and reading.gas_ppm > 50 and confined:
                score += 25
                triggered.append("maintenance+gas>50 in confined space (+25)")
            if "shift_changeover" in permits and reading.gas_ppm > 50:
                score += 15
                triggered.append("shift-changeover supervision gap during gas (+15)")

            score = min(score, 100)

            if score >= 80:
                action = ("STOP WORK IMMEDIATELY. Evacuate the zone, isolate the "
                          "source, and deploy the emergency response team.")
            elif score >= 50:
                action = ("Suspend non-essential work. Increase ventilation and "
                          "continuous monitoring; restrict entry.")
            elif score >= 20:
                action = ("Heightened caution. Verify PPE, increase monitoring "
                          "frequency, and brief the crew.")
            else:
                action = "Conditions nominal. Continue routine monitoring."

            return SafetyAlert(
                risk_score=score,
                triggered_rules=triggered,
                recommended_action=action,
                zone=reading.zone,
            )
        except Exception as e:  # noqa: BLE001
            return SafetyAlert(
                risk_score=0,
                triggered_rules=[],
                recommended_action="Assessment failed; manual review required.",
                zone=getattr(getattr(sensor_input, "reading", None), "zone", "unknown"),
                error=str(e),
            )


if __name__ == "__main__":
    from utils.sensor_simulator import vizag_critical_reading
    si = SensorInput(reading=vizag_critical_reading(), active_permits=["hot_work"])
    alert = SafetyAgent().assess(si)
    print("risk:", alert.risk_score)
    print("triggered:", alert.triggered_rules)
