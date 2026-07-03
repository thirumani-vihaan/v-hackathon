"""ComplianceAgent: deterministic rule engine over compliance/safety_rules.json.

Evaluates a SensorReading + active permits against the 20 OISD rules (R001-R020)
and returns a ComplianceResult. Fully deterministic — no randomness, no network.
"""
import json
import os

from schema import (
    ComplianceInput,
    ComplianceResult,
    ComplianceViolation,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
_RULES_PATH = os.path.join(os.path.dirname(_HERE), "compliance", "safety_rules.json")

_SEVERITY_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def _load_rules(path: str = _RULES_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _cmp(op: str, left, right) -> bool:
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == "in":
        return left in right
    if op == "not_in":
        return left not in right
    raise ValueError(f"unknown op: {op}")


def _eval_clause(clause: dict, sensor, permits: list) -> bool:
    # Permit presence clause.
    if "permit" in clause:
        present = clause["permit"] in permits or clause["permit"] == sensor.permit_type
        if clause.get("op") == "present":
            return present
        if clause.get("op") == "absent":
            return not present
        return present
    # Permit count clause: {"permit_count": 0} means no active permits at all.
    if "permit_count" in clause:
        total = len(permits) + (1 if sensor.permit_type else 0)
        # Treat a lone "general"/"none" permit_type with empty permits as no-permit
        # only when permits list is empty and permit_type is falsy.
        return len(permits) == clause["permit_count"] and not _has_real_permit(sensor)
    # Field comparison clause.
    if "field" in clause:
        value = getattr(sensor, clause["field"])
        return _cmp(clause["op"], value, clause.get("value"))
    return False


def _has_real_permit(sensor) -> bool:
    return bool(sensor.permit_type) and sensor.permit_type.lower() not in ("", "none")


def _rule_matches(rule: dict, sensor, permits: list) -> bool:
    cond = rule.get("conditions", {})
    if "all" in cond:
        return all(_eval_clause(c, sensor, permits) for c in cond["all"])
    if "any" in cond:
        return any(_eval_clause(c, sensor, permits) for c in cond["any"])
    return False


class ComplianceAgent:
    def __init__(self, rules_path: str = _RULES_PATH):
        try:
            self.rules = _load_rules(rules_path)
        except Exception as e:  # noqa: BLE001
            self.rules = []
            self._load_error = str(e)
        else:
            self._load_error = None

    def evaluate(self, compliance_input: ComplianceInput) -> ComplianceResult:
        try:
            sensor = compliance_input.sensor
            permits = list(compliance_input.active_permits or [])
            # active permit list should include the reading's own permit type.
            if _has_real_permit(sensor) and sensor.permit_type not in permits:
                permits = permits + [sensor.permit_type]

            violations = []
            for rule in self.rules:
                if _rule_matches(rule, sensor, permits):
                    violations.append(ComplianceViolation(
                        rule_id=rule["rule_id"],
                        name=rule["name"],
                        severity=rule["severity"],
                        message=rule["message"],
                        oisd_reference=rule["oisd_reference"],
                    ))

            highest = None
            if violations:
                highest = max(violations,
                              key=lambda v: _SEVERITY_ORDER[v.severity]).severity
            # A run "passes" only if no BLOCK-level (CRITICAL/HIGH-block) violation.
            # We treat any CRITICAL or HIGH violation as failing the check.
            fails = any(v.severity in ("CRITICAL", "HIGH") for v in violations)
            return ComplianceResult(
                pass_status=not fails,
                violations=violations,
                highest_severity=highest,
                error=self._load_error,
            )
        except Exception as e:  # noqa: BLE001
            return ComplianceResult(
                pass_status=False,
                violations=[],
                highest_severity=None,
                error=str(e),
            )

    def check(self, compliance_input: ComplianceInput) -> ComplianceResult:
        """Primary entry point; alias of evaluate(). Returns a ComplianceResult."""
        return self.evaluate(compliance_input)


if __name__ == "__main__":
    from utils.sensor_simulator import vizag_critical_reading
    ci = ComplianceInput(sensor=vizag_critical_reading(),
                         active_permits=["hot_work"])
    res = ComplianceAgent().evaluate(ci)
    print("pass:", res.pass_status, "highest:", res.highest_severity)
    for v in res.violations:
        print(" ", v.rule_id, v.severity, v.name)
