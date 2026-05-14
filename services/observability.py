import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


OBSERVABILITY_DIR = Path(__file__).resolve().parents[1] / "observability"
DEFAULT_OBSERVABILITY_LOG_PATH = OBSERVABILITY_DIR / "observability_log.json"

SCENARIO_MATCH_SYSTEM_PROMPT = """
You judge whether a freight bill audit agent handled a seed-data scenario correctly.

Use only:
- the seed scenario text,
- the final status/decision,
- the final agent explanation.

Return one JSON object only:
{
  "status": "match" | "mismatch" | "unclear",
  "matches": true | false | null,
  "confidence": number between 0 and 1,
  "reason": "short reason for the UI"
}

Scenario text describes the test intent. The result matches when the explanation and
final status/decision address that same intent, even if wording differs. Mark mismatch
when the agent approved/disputed/reviewed for a reason that contradicts or misses the
scenario intent. Mark unclear when scenario or explanation lacks enough detail.
Keep reason under 160 characters.
""".strip()


class ScenarioMatchJudge:
    def __init__(self, model: Optional[str] = None):
        self._load_dotenv()
        self.model = (
            model
            or os.getenv("OPENAI_OBSERVABILITY_MODEL")
            or os.getenv("OPENAI_MODEL")
            or "gpt-4.1-mini"
        )

    def judge(
        self,
        scenario: Optional[str],
        explanation: Optional[str],
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not scenario or not explanation:
            return {
                "status": "skipped",
                "matches": None,
                "confidence": 0.0,
                "reason": "Scenario or explanation missing.",
            }
        if not os.getenv("OPENAI_API_KEY"):
            return {
                "status": "skipped",
                "matches": None,
                "confidence": 0.0,
                "reason": "OPENAI_API_KEY not set.",
            }

        try:
            from openai import OpenAI

            client = OpenAI()
            response = client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": SCENARIO_MATCH_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "scenario": scenario,
                                "agent_result": result,
                                "agent_explanation": explanation,
                            },
                            indent=2,
                            sort_keys=True,
                            default=str,
                        ),
                    },
                ],
                max_output_tokens=220,
            )
            return self._normalize(self._parse_json(response.output_text))
        except Exception as exc:
            return {
                "status": "error",
                "matches": None,
                "confidence": 0.0,
                "reason": f"Scenario check failed: {exc}"[:240],
            }

    @staticmethod
    def _normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
        status = raw.get("status")
        matches = raw.get("matches")
        if status not in {"match", "mismatch", "unclear"}:
            status = "match" if matches is True else "mismatch" if matches is False else "unclear"

        matches_by_status = {
            "match": True,
            "mismatch": False,
            "unclear": None,
        }
        try:
            confidence = float(raw.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

        return {
            "status": status,
            "matches": matches_by_status[status],
            "confidence": max(0.0, min(1.0, confidence)),
            "reason": str(raw.get("reason") or "")[:240],
        }

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise
            return json.loads(text[start : end + 1])

    @staticmethod
    def _load_dotenv() -> None:
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except Exception:
            return


class ObservabilityLogger:
    def __init__(
        self,
        log_path: str | Path | None = None,
        scenario_judge: ScenarioMatchJudge | None = None,
    ):
        self.log_path = Path(
            log_path
            or os.getenv("OBSERVABILITY_LOG_PATH")
            or DEFAULT_OBSERVABILITY_LOG_PATH
        )
        self.scenario_judge = scenario_judge or ScenarioMatchJudge()

    def record_freight_bill_result(self, record: Dict[str, Any]) -> None:
        freight_bill = record.get("freight_bill") or {}
        freight_bill_id = record.get("id") or freight_bill.get("id")
        if not freight_bill_id:
            return

        scenario = freight_bill.get("_scenario") or freight_bill.get("scenario")
        result = {
            "status": record.get("status"),
            "decision": record.get("decision"),
            "decision_mode": record.get("decision_mode"),
            "decision_source": record.get("decision_source"),
            "awaiting_review": record.get("awaiting_review"),
        }
        entry = {
            "id": freight_bill_id,
            "scenario": scenario,
            "explanation": record.get("explanation"),
            "result": result,
            "scenario_check": self.scenario_judge.judge(
                scenario,
                record.get("explanation"),
                result,
            ),
        }
        self._append(entry)

    def entries(self) -> List[Dict[str, Any]]:
        return self._read_entries()

    def _append(self, entry: Dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        entries = self._read_entries()
        entries.append(entry)
        tmp_path = self.log_path.with_suffix(f"{self.log_path.suffix}.tmp")
        tmp_path.write_text(json.dumps(entries, indent=2, default=str))
        tmp_path.replace(self.log_path)

    def _read_entries(self) -> List[Dict[str, Any]]:
        if not self.log_path.exists():
            return []
        try:
            data = json.loads(self.log_path.read_text())
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []
