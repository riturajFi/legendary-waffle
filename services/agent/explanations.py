import os
from typing import Any, Dict, List


class ExplanationBuilder:
    def build(
        self,
        freight_bill: Dict[str, Any],
        checks: List[Dict[str, Any]],
        decision: str,
        confidence: float,
    ) -> str:
        fallback = self._fallback_explanation(freight_bill, checks, decision, confidence)

        if not os.getenv("OPENAI_API_KEY"):
            return fallback

        try:
            from openai import OpenAI

            client = OpenAI()
            response = client.responses.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                input=self._prompt(freight_bill, checks, decision, confidence),
                max_output_tokens=160,
            )
            return response.output_text.strip() or fallback
        except Exception:
            return fallback

    @staticmethod
    def _prompt(
        freight_bill: Dict[str, Any],
        checks: List[Dict[str, Any]],
        decision: str,
        confidence: float,
    ) -> str:
        non_pass = [
            {
                "name": check["name"],
                "status": check["status"],
                "reason": check["reason"],
            }
            for check in checks
            if check.get("status") != "pass"
        ]

        return (
            "Write a concise freight-bill audit explanation for an operations reviewer. "
            "Do not invent facts. Include the decision, confidence, and the main evidence. "
            f"Freight bill: {freight_bill}. Decision: {decision}. Confidence: {confidence}. "
            f"Non-pass checks: {non_pass}."
        )

    @staticmethod
    def _fallback_explanation(
        freight_bill: Dict[str, Any],
        checks: List[Dict[str, Any]],
        decision: str,
        confidence: float,
    ) -> str:
        non_pass = [check for check in checks if check.get("status") != "pass"]
        bill_id = freight_bill.get("id", "unknown")

        if not non_pass:
            return f"{bill_id} passed all rule checks. Decision {decision} at confidence {confidence:.2f}."

        reasons = "; ".join(f"{check['name']}: {check['reason']}" for check in non_pass)
        return f"{bill_id} requires action because {reasons}. Decision {decision} at confidence {confidence:.2f}."
