"""Tests for multi-framework regulatory coverage (P2): every rule must cite OISD,
Factory Act 1948, and DGMS so the compliance engine spans all three frameworks named
in the PS1 evaluation focus. Rule count and behaviour are unchanged.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from agents.compliance_agent import ComplianceAgent, REGULATORY_FRAMEWORKS  # noqa: E402


def test_still_at_least_20_rules():
    assert len(ComplianceAgent().rules) >= 20


def test_every_rule_cites_all_three_frameworks():
    for rule in ComplianceAgent().rules:
        ref = rule["oisd_reference"]
        for fw in REGULATORY_FRAMEWORKS:
            assert fw in ref, f"{rule['rule_id']} missing {fw} in '{ref}'"


def test_coverage_report():
    cov = ComplianceAgent().regulatory_coverage()
    assert cov["total_rules"] >= 20
    assert cov["frameworks"]["OISD"] >= 20
    assert cov["frameworks"]["Factory Act"] >= 20
    assert cov["frameworks"]["DGMS"] >= 20
