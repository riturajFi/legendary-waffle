import os
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class PostgresStore:
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv("DATABASE_URL") or self._database_url_from_env()

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS freight_bills (
                    id TEXT PRIMARY KEY,
                    payload JSONB NOT NULL,
                    status TEXT NOT NULL,
                    decision TEXT,
                    decision_mode TEXT,
                    decision_source TEXT,
                    confidence DOUBLE PRECISION,
                    explanation TEXT,
                    checks JSONB NOT NULL DEFAULT '[]'::jsonb,
                    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
                    awaiting_review BOOLEAN NOT NULL DEFAULT FALSE,
                    agent_thread_id TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                "ALTER TABLE freight_bills ADD COLUMN IF NOT EXISTS decision_source TEXT"
            )
            conn.execute(
                "ALTER TABLE freight_bills ADD COLUMN IF NOT EXISTS decision_mode TEXT"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_decisions (
                    id BIGSERIAL PRIMARY KEY,
                    freight_bill_id TEXT NOT NULL REFERENCES freight_bills(id),
                    decision TEXT NOT NULL,
                    notes TEXT,
                    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id BIGSERIAL PRIMARY KEY,
                    freight_bill_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_freight_bills_review_queue
                ON freight_bills (awaiting_review, status)
                """
            )

    def upsert_ingested_bill(self, freight_bill: Dict[str, Any]) -> Dict[str, Any]:
        freight_bill_id = freight_bill["id"]

        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO freight_bills (
                    id,
                    payload,
                    status,
                    decision,
                    decision_mode,
                    decision_source,
                    confidence,
                    explanation,
                    checks,
                    evidence,
                    awaiting_review,
                    agent_thread_id,
                    updated_at
                )
                VALUES (
                    %(id)s,
                    %(payload)s,
                    'received',
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    '[]'::jsonb,
                    '{}'::jsonb,
                    FALSE,
                    %(thread_id)s,
                    now()
                )
                ON CONFLICT (id) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    status = 'received',
                    decision = NULL,
                    decision_mode = NULL,
                    decision_source = NULL,
                    confidence = NULL,
                    explanation = NULL,
                    checks = '[]'::jsonb,
                    evidence = '{}'::jsonb,
                    awaiting_review = FALSE,
                    agent_thread_id = EXCLUDED.agent_thread_id,
                    updated_at = now()
                RETURNING *
                """,
                {
                    "id": freight_bill_id,
                    "payload": Jsonb(freight_bill),
                    "thread_id": freight_bill_id,
                },
            ).fetchone()

        self.add_audit_event(freight_bill_id, "freight_bill_ingested", {"freight_bill": freight_bill})
        return self._public_row(row)

    def update_agent_result(self, freight_bill_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                UPDATE freight_bills
                SET status = %(status)s,
                    decision = %(decision)s,
                    decision_mode = %(decision_mode)s,
                    decision_source = %(decision_source)s,
                    confidence = %(confidence)s,
                    explanation = %(explanation)s,
                    checks = %(checks)s,
                    evidence = %(evidence)s,
                    awaiting_review = %(awaiting_review)s,
                    updated_at = now()
                WHERE id = %(id)s
                RETURNING *
                """,
                {
                    "id": freight_bill_id,
                    "status": result.get("status", "errored"),
                    "decision": result.get("decision"),
                    "decision_mode": result.get("decision_mode"),
                    "decision_source": result.get("decision_source"),
                    "confidence": result.get("confidence"),
                    "explanation": result.get("explanation"),
                    "checks": Jsonb(result.get("checks") or []),
                    "evidence": Jsonb(result.get("evidence") or {}),
                    "awaiting_review": bool(result.get("awaiting_review")),
                },
            ).fetchone()

        self.add_audit_event(freight_bill_id, "agent_result_recorded", result)
        return self._public_row(row)

    def mark_error(self, freight_bill_id: str, message: str) -> Dict[str, Any]:
        return self.update_agent_result(
            freight_bill_id,
            {
                "status": "errored",
                "decision": "error",
                "decision_mode": None,
                "decision_source": "system",
                "confidence": 0.0,
                "explanation": message,
                "checks": [],
                "evidence": {},
                "awaiting_review": False,
            },
        )

    def get_freight_bill(self, freight_bill_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM freight_bills WHERE id = %s",
                (freight_bill_id,),
            ).fetchone()

        return self._public_row(row) if row else None

    def list_review_queue(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM freight_bills
                WHERE awaiting_review = TRUE
                ORDER BY updated_at ASC, id ASC
                """
            ).fetchall()

        return [self._public_row(row) for row in rows]

    def record_review(self, freight_bill_id: str, review: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO review_decisions (freight_bill_id, decision, notes, payload)
                VALUES (%(freight_bill_id)s, %(decision)s, %(notes)s, %(payload)s)
                """,
                {
                    "freight_bill_id": freight_bill_id,
                    "decision": review["decision"],
                    "notes": review.get("notes"),
                    "payload": Jsonb(review),
                },
            )

        self.add_audit_event(freight_bill_id, "review_submitted", review)

    def add_audit_event(self, freight_bill_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_events (freight_bill_id, event_type, payload)
                VALUES (%(freight_bill_id)s, %(event_type)s, %(payload)s)
                """,
                {
                    "freight_bill_id": freight_bill_id,
                    "event_type": event_type,
                    "payload": Jsonb(payload),
                },
            )

    def _connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    @staticmethod
    def _database_url_from_env() -> str:
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "password")
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        database = os.getenv("POSTGRES_DB", "freight")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    @staticmethod
    def _public_row(row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if row is None:
            return {}

        return {
            "id": row["id"],
            "freight_bill": row["payload"],
            "status": row["status"],
            "decision": row["decision"],
            "decision_mode": row.get("decision_mode"),
            "decision_source": row.get("decision_source"),
            "confidence": row["confidence"],
            "explanation": row["explanation"],
            "checks": row["checks"],
            "evidence_chain": row["evidence"],
            "awaiting_review": row["awaiting_review"],
            "agent_thread_id": row["agent_thread_id"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }
