import json
import os
from pathlib import Path
from typing import Any, Dict, List


OBSERVABILITY_DIR = Path(__file__).resolve().parents[1] / "observability"
DEFAULT_OBSERVABILITY_LOG_PATH = OBSERVABILITY_DIR / "observability_log.json"


class ObservabilityLogger:
    def __init__(self, log_path: str | Path | None = None):
        self.log_path = Path(
            log_path
            or os.getenv("OBSERVABILITY_LOG_PATH")
            or DEFAULT_OBSERVABILITY_LOG_PATH
        )

    def record_freight_bill_result(self, record: Dict[str, Any]) -> None:
        freight_bill = record.get("freight_bill") or {}
        freight_bill_id = record.get("id") or freight_bill.get("id")
        if not freight_bill_id:
            return

        entry = {
            "id": freight_bill_id,
            "scenario": freight_bill.get("_scenario") or freight_bill.get("scenario"),
            "result": {
                "status": record.get("status"),
                "decision": record.get("decision"),
                "decision_mode": record.get("decision_mode"),
                "decision_source": record.get("decision_source"),
                "awaiting_review": record.get("awaiting_review"),
            },
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
