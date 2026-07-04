"""OutputAgent — the 5th pipeline stage (format / consolidate / brief).

The pipeline ends with an OutputAgent that formats the final response and
produces voice output:
  * format()   -> validates/returns the aggregated OrchestratorResult (schema-safe
                  pass-through; the orchestrator calls this as its final stage).
  * briefing() -> a plain-language, speakable incident briefing consolidating
                  safety + compliance + vision + knowledge, optionally with a
                  localized evacuation line for CRITICAL incidents.

It never creates new dataclasses (schema is immutable) and makes no LLM calls,
so it stays deterministic and cannot break the graph.
"""
from typing import Optional

from schema import OrchestratorResult
from utils import translations


class OutputAgent:
    def format(self, result: OrchestratorResult) -> OrchestratorResult:
        """Final formatting stage. Returns the same schema OrchestratorResult.

        Kept as an identity/validation pass so it is guaranteed schema-safe and
        cannot alter agent semantics; the value-add is exposed via briefing().
        """
        if not isinstance(result, OrchestratorResult):
            raise TypeError("OutputAgent.format expects an OrchestratorResult")
        return result

    def severity(self, result: OrchestratorResult) -> str:
        """Overall incident severity from safety risk + compliance severity."""
        risk = result.safety.risk_score if result.safety else 0
        comp = result.compliance.highest_severity if result.compliance else None
        if risk >= 70 or comp == "CRITICAL":
            return "CRITICAL"
        if risk >= 40 or comp in ("HIGH",):
            return "HIGH"
        if risk >= 20 or comp in ("MEDIUM", "LOW"):
            return "MODERATE"
        return "NORMAL"

    def briefing(self, result: OrchestratorResult,
                 lang: str = "English") -> str:
        """Consolidated, human-readable briefing string (speakable)."""
        lines = []
        sev = self.severity(result)
        lines.append(f"Incident briefing — status {sev}. Reference {result.request_id}.")

        if result.safety:
            s = result.safety
            lines.append(
                f"Safety: risk score {s.risk_score} in {s.zone}. "
                f"Action: {s.recommended_action}.")
            if s.triggered_rules:
                lines.append("Triggered rules: " + ", ".join(s.triggered_rules[:5]) + ".")

        if result.compliance:
            c = result.compliance
            status = "PASS" if c.pass_status else "FAIL"
            lines.append(
                f"Compliance: {status}"
                + (f", highest severity {c.highest_severity}" if c.highest_severity else "")
                + f", {len(c.violations)} violation(s).")
            for v in c.violations[:3]:
                lines.append(f"  - {v.rule_id} {v.name} ({v.severity}).")

        if result.vision:
            v = result.vision
            kinds = ", ".join(sorted({h.type for h in v.hazards})) or "none"
            lines.append(f"Vision ({v.source}): {len(v.hazards)} hazard(s) [{kinds}].")

        if result.knowledge:
            k = result.knowledge
            srcs = ", ".join(s.get("filename", "?") for s in k.sources[:3]) or "none"
            lines.append(
                f"Knowledge (confidence {k.confidence:.2f}, sources: {srcs}).")

        if sev == "CRITICAL":
            zone = result.safety.zone if result.safety else "affected zone"
            msg, _ = translations.translate_evac(lang, zone, result.request_id,
                                                 use_gemini=False)
            lines.append("EVACUATION: " + msg)

        return "\n".join(lines)


if __name__ == "__main__":
    from schema import SafetyAlert, ComplianceResult
    r = OrchestratorResult(
        request_id="demo-1", input_type="sensor",
        safety=SafetyAlert(risk_score=100, triggered_rules=["R1", "R7"],
                           recommended_action="Evacuate", zone="Zone-B-Process"),
        compliance=ComplianceResult(pass_status=False, violations=[],
                                    highest_severity="CRITICAL"))
    print(OutputAgent().briefing(r, "Hindi"))
