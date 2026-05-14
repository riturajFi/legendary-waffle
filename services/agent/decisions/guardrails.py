from typing import Any, Dict, List, Optional

from .models import AiDecisionResult


def apply_rule_guardrails(
    result: AiDecisionResult,
    checks: List[Dict],
    context: Optional[Dict[str, Any]] = None,
) -> AiDecisionResult:
    non_pass = [check for check in checks if check.get("status") != "pass"]

    if result.status == "review_required" and checks and not non_pass:
        return AiDecisionResult(
            status="approved",
            decision="ai_approved",
            confidence=max(result.confidence, 0.9),
            explanation=(
                "All deterministic rule checks passed. Approved by rule guardrail; "
                "raw graph candidate ambiguity alone is not enough to require review."
            ),
            review_reasons=[],
        )

    if result.status == "approved" and non_pass:
        if _contract_only_resolution_allowed(context or {}, checks, non_pass):
            return result

        reasons = "; ".join(f"{check['name']}: {check['reason']}" for check in non_pass)
        return AiDecisionResult(
            status="review_required",
            decision="ai_review",
            confidence=min(result.confidence, 0.5),
            explanation=(
                "AI approval blocked by deterministic rule guardrail. "
                f"Non-pass checks: {reasons}."
            ),
            review_reasons=[check["reason"] for check in non_pass],
        )

    return result


def _contract_only_resolution_allowed(
    context: Dict[str, Any],
    checks: List[Dict],
    non_pass: List[Dict],
) -> bool:
    freight_bill = context.get("freight_bill") or {}
    if freight_bill.get("shipment_reference"):
        return False

    non_pass_names = {check.get("name") for check in non_pass}
    if not non_pass_names.issubset({"shipment_check", "weight_check"}):
        return False

    statuses_by_name = {check.get("name"): check.get("status") for check in checks}
    if statuses_by_name.get("rate_check") != "pass":
        return False
    if statuses_by_name.get("amount_check") != "pass":
        return False

    contracts = (
        context.get("graph_evidence", {})
        .get("contracts", {})
        .get("by_bill_date", {})
        .get("candidates", [])
    )
    billed_rate = freight_bill.get("rate_per_kg")
    matches = [
        candidate
        for candidate in contracts
        if _rate_matches(billed_rate, candidate.get("rate_rule") or {})
    ]

    return len(matches) == 1


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
