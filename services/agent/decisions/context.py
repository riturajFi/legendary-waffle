from typing import Any, Dict, List


def build_decision_context(
    freight_bill: Dict[str, Any],
    evidence: Dict[str, Any],
    checks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "freight_bill": freight_bill,
        "rule_checks": _compact_checks(checks),
        "graph_evidence": {
            "duplicates": evidence.get("duplicates"),
            "carrier": evidence.get("carrier"),
            "shipment": evidence.get("shipment"),
            "bol": evidence.get("bol"),
            "previous_bills": evidence.get("previous_bills"),
            "cumulative_billing": evidence.get("cumulative_billing"),
            "contracts": evidence.get("contracts"),
            "rate_rule": evidence.get("rate_rule"),
        },
    }


def _compact_checks(checks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "name": check.get("name"),
            "status": check.get("status"),
            "reason": check.get("reason"),
            "details": check.get("details") or {},
        }
        for check in checks
    ]
