from typing import Any, Dict, List

from pydantic import ValidationError

from .context import build_decision_context
from .guardrails import apply_rule_guardrails
from .models import AiDecisionResult
from .openai_client import OpenAiDecisionClient


class AiDecisionEngine:
    def __init__(self, client: OpenAiDecisionClient | None = None):
        self.client = client or OpenAiDecisionClient()

    def decide(
        self,
        freight_bill: Dict[str, Any],
        evidence: Dict[str, Any],
        checks: List[Dict[str, Any]],
    ) -> AiDecisionResult:
        context = build_decision_context(freight_bill, evidence, checks)
        raw_result = self.client.decide(context)

        try:
            result = AiDecisionResult.model_validate(raw_result)
        except ValidationError as exc:
            raise RuntimeError(f"AI decision response failed schema validation: {exc}") from exc

        return apply_rule_guardrails(result, checks, context=context)
