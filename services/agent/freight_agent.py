import os
from typing import Any, Dict, List, Literal, Optional, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from services.agent.decisions import AiDecisionEngine
from services.agent.explanations import ExplanationBuilder
from services.evidence.evidence_service import EvidenceService
from services.rules import RuleEngine
from services.storage import PostgresStore


class AgentState(TypedDict, total=False):
    freight_bill_id: str
    freight_bill: Dict[str, Any]
    evidence: Dict[str, Any]
    checks: List[Dict[str, Any]]
    status: str
    decision: str
    decision_mode: str
    decision_source: str
    confidence: float
    explanation: str
    awaiting_review: bool
    review: Dict[str, Any]


class FreightAgent:
    def __init__(
        self,
        store: PostgresStore,
        evidence_service: Optional[EvidenceService] = None,
        rule_engine: Optional[RuleEngine] = None,
        ai_decider: Optional[AiDecisionEngine] = None,
    ):
        self.store = store
        self.evidence_service = evidence_service or EvidenceService(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password"),
        )
        self.rule_engine = rule_engine or RuleEngine()
        self.ai_decider = ai_decider or AiDecisionEngine()
        self.explanations = ExplanationBuilder()
        self.graph = self._build_graph()

    def close(self) -> None:
        self.evidence_service.close()

    def run(
        self,
        freight_bill_id: str,
        freight_bill: Dict[str, Any],
        decision_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = self.graph.invoke(
            {
                "freight_bill_id": freight_bill_id,
                "freight_bill": freight_bill,
                "decision_mode": self._decision_mode(decision_mode),
            },
            self._config(freight_bill_id),
        )
        clean_result = self._clean_result(result)
        return self.store.update_agent_result(freight_bill_id, clean_result)

    def resume_after_review(self, freight_bill_id: str, review: Dict[str, Any]) -> Dict[str, Any]:
        current = self.store.get_freight_bill(freight_bill_id)
        if current is None:
            raise KeyError(freight_bill_id)
        if not current["awaiting_review"]:
            raise ValueError(f"{freight_bill_id} is not waiting for review")

        self.store.record_review(freight_bill_id, review)
        try:
            result = self.graph.invoke(Command(resume=review), self._config(freight_bill_id))
            clean_result = self._clean_result(result)
        except Exception:
            clean_result = self._review_result_from_persisted_state(current, review)

        return self.store.update_agent_result(freight_bill_id, clean_result)

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("collect_evidence", self._collect_evidence)
        graph.add_node("run_rules", self._run_rules)
        graph.add_node("decide", self._decide)
        graph.add_node("ai_decide", self._ai_decide)
        graph.add_node("human_review", self._human_review)
        graph.add_node("apply_review", self._apply_review)

        graph.add_edge(START, "collect_evidence")
        graph.add_edge("collect_evidence", "run_rules")
        graph.add_conditional_edges(
            "run_rules",
            self._route_decider,
            {
                "rules": "decide",
                "ai": "ai_decide",
            },
        )
        graph.add_conditional_edges(
            "decide",
            self._route_after_decision,
            {
                "review": "human_review",
                "done": END,
            },
        )
        graph.add_conditional_edges(
            "ai_decide",
            self._route_after_decision,
            {
                "review": "human_review",
                "done": END,
            },
        )
        graph.add_edge("human_review", "apply_review")
        graph.add_edge("apply_review", END)

        return graph.compile(checkpointer=InMemorySaver())

    def _collect_evidence(self, state: AgentState) -> AgentState:
        freight_bill_id = state["freight_bill_id"]
        return {"evidence": self.evidence_service.get_evidence(freight_bill_id)}

    def _run_rules(self, state: AgentState) -> AgentState:
        return {"checks": self.rule_engine.run(state["evidence"])}

    def _decide(self, state: AgentState) -> AgentState:
        status, decision, confidence = self._score(state["checks"])
        explanation = self.explanations.build(
            freight_bill=state["freight_bill"],
            checks=state["checks"],
            decision=decision,
            confidence=confidence,
        )
        return {
            "status": status,
            "decision": decision,
            "decision_source": "rules",
            "confidence": confidence,
            "explanation": explanation,
            "awaiting_review": status == "review_required",
        }

    def _ai_decide(self, state: AgentState) -> AgentState:
        try:
            decision = self.ai_decider.decide(
                freight_bill=state["freight_bill"],
                evidence=state["evidence"],
                checks=state["checks"],
            )
            return decision.to_agent_update(decision_source="ai")
        except Exception as exc:
            fallback = self._decide(state)
            fallback["decision_source"] = "rules_fallback"
            fallback["explanation"] = (
                f"AI decision unavailable: {exc}. "
                f"Fallback used. {fallback['explanation']}"
            )
            return fallback

    def _human_review(self, state: AgentState) -> AgentState:
        review = interrupt(
            {
                "freight_bill_id": state["freight_bill_id"],
                "decision": state["decision"],
                "confidence": state["confidence"],
                "explanation": state["explanation"],
                "non_pass_checks": [
                    check for check in state["checks"] if check.get("status") != "pass"
                ],
            }
        )
        return {"review": review, "awaiting_review": False}

    def _apply_review(self, state: AgentState) -> AgentState:
        review = state.get("review") or {}
        reviewer_decision = review.get("decision")
        notes = review.get("notes")

        status, decision = self._status_for_review_decision(reviewer_decision)
        suffix = f" Reviewer notes: {notes}" if notes else ""

        return {
            "status": status,
            "decision": decision,
            "decision_source": "reviewer",
            "confidence": 1.0,
            "awaiting_review": False,
            "explanation": f"Reviewer selected {reviewer_decision}.{suffix}",
        }

    @staticmethod
    def _route_decider(state: AgentState) -> Literal["rules", "ai"]:
        return "ai" if state.get("decision_mode") == "ai" else "rules"

    @staticmethod
    def _route_after_decision(state: AgentState) -> Literal["review", "done"]:
        return "review" if state.get("awaiting_review") else "done"

    @staticmethod
    def _score(checks: List[Dict[str, Any]]) -> tuple[str, str, float]:
        statuses = [check.get("status") for check in checks]
        review_count = statuses.count("review")
        fail_count = statuses.count("fail")

        if review_count:
            confidence = max(0.35, 0.72 - (review_count * 0.12) - (fail_count * 0.08))
            return "review_required", "needs_review", round(confidence, 2)

        if fail_count:
            confidence = max(0.80, 0.95 - (fail_count * 0.04))
            return "disputed", "auto_dispute", round(confidence, 2)

        return "approved", "auto_approved", 0.98

    def _review_result_from_persisted_state(
        self,
        current: Dict[str, Any],
        review: Dict[str, Any],
    ) -> Dict[str, Any]:
        status, decision = self._status_for_review_decision(review["decision"])
        notes = review.get("notes")
        suffix = f" Reviewer notes: {notes}" if notes else ""

        return {
            "freight_bill_id": current["id"],
            "freight_bill": current["freight_bill"],
            "evidence": current["evidence_chain"],
            "checks": current["checks"],
            "status": status,
            "decision": decision,
            "decision_source": "reviewer",
            "confidence": 1.0,
            "awaiting_review": False,
            "explanation": f"Reviewer selected {review['decision']} from persisted review state.{suffix}",
        }

    @staticmethod
    def _decision_mode(decision_mode: Optional[str]) -> str:
        value = decision_mode or os.getenv("FREIGHT_AGENT_DECIDER", "rules")
        return "ai" if value == "ai" else "rules"

    @staticmethod
    def _status_for_review_decision(reviewer_decision: str) -> tuple[str, str]:
        status_by_decision = {
            "approve": ("approved", "reviewer_approved"),
            "dispute": ("disputed", "reviewer_disputed"),
            "modify": ("modified", "reviewer_modified"),
        }
        return status_by_decision[reviewer_decision]

    @staticmethod
    def _config(freight_bill_id: str) -> Dict[str, Any]:
        return {"configurable": {"thread_id": freight_bill_id}}

    @staticmethod
    def _clean_result(result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            key: value
            for key, value in result.items()
            if not key.startswith("__")
        }
