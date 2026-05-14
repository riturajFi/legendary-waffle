from typing import Any, Dict, List

from services.agent.sanitization import strip_scenario_hints


def build_decision_context(
    freight_bill: Dict[str, Any],
    evidence: Dict[str, Any],
    checks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "freight_bill": strip_scenario_hints(freight_bill),
        "rule_checks": strip_scenario_hints(_compact_checks(checks)),
        "graph_evidence": strip_scenario_hints({
            "duplicates": evidence.get("duplicates"),
            "carrier": evidence.get("carrier"),
            "shipment": evidence.get("shipment"),
            "bol": evidence.get("bol"),
            "previous_bills": evidence.get("previous_bills"),
            "cumulative_billing": evidence.get("cumulative_billing"),
            "contracts": evidence.get("contracts"),
            "rate_rule": evidence.get("rate_rule"),
        }),
        "charge_math": _build_charge_math(freight_bill, evidence),
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


def _build_charge_math(
    freight_bill: Dict[str, Any],
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    rate_rule = _selected_rate_rule(freight_bill, evidence) or {}
    billed_weight = freight_bill.get("billed_weight_kg") or 0
    billed_rate = freight_bill.get("rate_per_kg") or 0
    base_charge = billed_weight * billed_rate
    fuel_percent = _fuel_percent(freight_bill, rate_rule)

    if fuel_percent is None:
        return {
            "available": False,
            "reason": "no selected rate rule with fuel surcharge percent",
        }

    fuel_surcharge = base_charge * fuel_percent / 100
    gst_amount = (base_charge + fuel_surcharge) * 0.18
    total_amount = base_charge + fuel_surcharge + gst_amount

    return {
        "available": True,
        "selected_rate_rule": strip_scenario_hints(rate_rule),
        "billed_weight_kg": billed_weight,
        "billed_rate": billed_rate,
        "base_charge": {
            "formula": "billed_weight_kg * billed_rate",
            "expected": round(base_charge, 2),
            "actual": freight_bill.get("base_charge"),
        },
        "fuel_surcharge": {
            "formula": "base_charge * fuel_percent / 100",
            "fuel_percent": fuel_percent,
            "expected": round(fuel_surcharge, 2),
            "actual": freight_bill.get("fuel_surcharge"),
        },
        "gst_amount": {
            "formula": "(base_charge + fuel_surcharge) * 0.18",
            "expected": round(gst_amount, 2),
            "actual": freight_bill.get("gst_amount"),
        },
        "total_amount": {
            "formula": "base_charge + fuel_surcharge + gst_amount",
            "expected": round(total_amount, 2),
            "actual": freight_bill.get("total_amount"),
        },
    }


def _selected_rate_rule(
    freight_bill: Dict[str, Any],
    evidence: Dict[str, Any],
) -> Dict[str, Any] | None:
    used = (
        evidence.get("contracts", {})
        .get("used_by_shipment", {})
        .get("rate_rule")
    )
    if used:
        return used

    candidates = (
        evidence.get("contracts", {})
        .get("by_bill_date", {})
        .get("candidates", [])
    )
    billed_rate = freight_bill.get("rate_per_kg")
    matches = [
        candidate.get("rate_rule")
        for candidate in candidates
        if _rate_matches(billed_rate, candidate.get("rate_rule") or {})
    ]
    if len(matches) == 1:
        return matches[0]
    if len(candidates) == 1:
        return candidates[0].get("rate_rule")

    return None


def _fuel_percent(
    freight_bill: Dict[str, Any],
    rate_rule: Dict[str, Any],
) -> float | None:
    revised_on = rate_rule.get("revised_on")
    revised_fuel = rate_rule.get("revised_fuel_surcharge_percent")
    bill_date = freight_bill.get("bill_date")

    if revised_on and revised_fuel is not None and bill_date and bill_date >= revised_on:
        return revised_fuel

    return rate_rule.get("fuel_surcharge_percent")


def _rate_matches(billed_rate: Any, rate_rule: Dict[str, Any]) -> bool:
    if billed_rate is None:
        return False

    allowed_rates = [
        rate_rule.get("rate_per_kg"),
        rate_rule.get("alternate_rate_per_kg"),
    ]
    return any(
        rate is not None and abs(float(billed_rate) - float(rate)) <= 0.05
        for rate in allowed_rates
    )
