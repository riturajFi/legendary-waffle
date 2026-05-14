import json
from typing import Any, Dict


SYSTEM_PROMPT = """
You are the AI decision node for a freight bill audit agent.

Use the freight bill, deterministic rule checks, and graph evidence only.
Rules are computed by code and are strong evidence, not suggestions.

Return one JSON object only:
{
  "status": "approved" | "disputed" | "review_required",
  "decision": "ai_approved" | "ai_dispute" | "ai_review",
  "confidence": number between 0 and 1,
  "explanation": "short reviewer-facing explanation",
  "review_reasons": ["short reason", "..."]
}

Decision policy:
- approved: clean evidence, no failed checks, no review checks.
- disputed: strong deterministic failure such as duplicate, overbilling, rate mismatch, or amount mismatch.
- review_required: missing, ambiguous, weak, or conflicting evidence.
- Never approve when any rule check has status fail or review.
- Keep explanation factual. Do not invent contract, shipment, BOL, or carrier facts.
""".strip()


def build_user_prompt(context: Dict[str, Any]) -> str:
    return (
        "Decide this freight bill from evidence below. "
        "Return JSON only.\n\n"
        f"{json.dumps(context, indent=2, sort_keys=True, default=str)}"
    )
