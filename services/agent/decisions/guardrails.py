from typing import Dict, List

from .models import AiDecisionResult


def apply_rule_guardrails(
    result: AiDecisionResult,
    checks: List[Dict],
) -> AiDecisionResult:
    non_pass = [check for check in checks if check.get("status") != "pass"]

    if result.status == "approved" and non_pass:
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
