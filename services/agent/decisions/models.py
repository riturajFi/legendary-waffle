from typing import Literal, List

from pydantic import BaseModel, Field


class AiDecisionResult(BaseModel):
    status: Literal["approved", "disputed", "review_required"]
    decision: Literal["ai_approved", "ai_dispute", "ai_review"]
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    review_reasons: List[str] = Field(default_factory=list)

    @property
    def awaiting_review(self) -> bool:
        return self.status == "review_required"

    def to_agent_update(self, decision_source: str = "ai") -> dict:
        return {
            "status": self.status,
            "decision": self.decision,
            "decision_source": decision_source,
            "confidence": round(self.confidence, 2),
            "explanation": self.explanation,
            "awaiting_review": self.awaiting_review,
        }
