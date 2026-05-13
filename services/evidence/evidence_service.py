from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase

from .queries import (
    BFS_TO_EVIDENCE_TARGETS_QUERY,
    CONTRACT_CANDIDATES_QUERY,
    CUMULATIVE_BILLING_FOR_SHIPMENT_QUERY,
    DUPLICATE_BILLS_QUERY,
    OTHER_BILLS_FOR_SAME_SHIPMENT_QUERY,
    REVISED_RATE_RULE_QUERY,
    TRACE_HAPPY_PATH_QUERY,
    TRACE_HAPPY_PATHS,
    WEAK_SHIPMENT_CANDIDATES_QUERY,
)
from .utils import node_to_dict, path_to_dict, serialize_neo4j_value


class EvidenceService:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def trace_happy_path(self, freight_bill_id: str) -> Dict[str, Any]:
        """
        Happy path:
        FreightBill
          -> CLAIMS_SHIPMENT -> Shipment
          -> SHIPPED_BY -> Carrier
          -> HAS_BOL -> BOL
          -> UNDER_CONTRACT -> Contract
          -> ON_LANE -> Lane
          -> Contract -> HAS_RATE_RULE -> RateRule -> FOR_LANE -> Lane
        """

        with self.driver.session() as session:
            record = session.execute_read(
                lambda tx: tx.run(
                    TRACE_HAPPY_PATH_QUERY,
                    freight_bill_id=freight_bill_id,
                ).single()
            )

        if record is None:
            return {
                "freight_bill_id": freight_bill_id,
                "found": False,
                "evidence": {},
            }

        return {
            "freight_bill_id": freight_bill_id,
            "found": True,
            "evidence": {
                "freight_bill": node_to_dict(record["fb"]),
                "bill_carrier": node_to_dict(record["bill_carrier"]),
                "bill_lane": node_to_dict(record["bill_lane"]),
                "claimed_shipment": node_to_dict(record["shipment"]),
                "shipment_carrier": node_to_dict(record["shipment_carrier"]),
                "shipment_lane": node_to_dict(record["shipment_lane"]),
                "bol": node_to_dict(record["bol"]),
                "contract": node_to_dict(record["contract"]),
                "rate_rule": node_to_dict(record["rate_rule"]),
                "rate_lane": node_to_dict(record["rate_lane"]),
            },
            "paths_collected": list(TRACE_HAPPY_PATHS),
        }

    def bfs_to_evidence_targets(self, freight_bill_id: str) -> Dict[str, Any]:
        """
        Traverse outward from a FreightBill up to 5 hops and collect BOL/Contract targets.
        """

        with self.driver.session() as session:
            records = session.execute_read(
                lambda tx: list(
                    tx.run(
                        BFS_TO_EVIDENCE_TARGETS_QUERY,
                        freight_bill_id=freight_bill_id,
                    )
                )
            )

        return {
            "freight_bill_id": freight_bill_id,
            "targets_found": len(records),
            "targets": [
                {
                    "target": node_to_dict(record["target"]),
                    "labels": list(record["labels"]),
                    "path": path_to_dict(record["path"]),
                }
                for record in records
            ],
        }

    def find_duplicate_bills(self, freight_bill_id: str) -> Dict[str, Any]:
        records = self._read_records(DUPLICATE_BILLS_QUERY, freight_bill_id)
        duplicates = [node_to_dict(record["dup"]) for record in records]

        return {
            "freight_bill_id": freight_bill_id,
            "duplicates_found": len(duplicates),
            "duplicates": duplicates,
        }

    def find_other_bills_for_same_shipment(self, freight_bill_id: str) -> Dict[str, Any]:
        records = self._read_records(
            OTHER_BILLS_FOR_SAME_SHIPMENT_QUERY,
            freight_bill_id,
        )

        return {
            "freight_bill_id": freight_bill_id,
            "matches_found": len(records),
            "matches": [
                {
                    "shipment": node_to_dict(record["s"]),
                    "other_freight_bill": node_to_dict(record["other"]),
                }
                for record in records
            ],
        }

    def get_cumulative_billing_for_shipment(
        self,
        freight_bill_id: str,
    ) -> Dict[str, Any]:
        record = self._read_single_record(
            CUMULATIVE_BILLING_FOR_SHIPMENT_QUERY,
            freight_bill_id,
        )

        if record is None:
            return {
                "freight_bill_id": freight_bill_id,
                "found": False,
                "cumulative_billing": None,
            }

        return {
            "freight_bill_id": freight_bill_id,
            "found": True,
            "cumulative_billing": {
                "shipment_id": record["shipment_id"],
                "shipment_weight": record["shipment_weight"],
                "bill_ids": list(record["bill_ids"]),
                "total_billed_weight": record["total_billed_weight"],
            },
        }

    def get_revised_rate_rule(self, freight_bill_id: str) -> Dict[str, Any]:
        record = self._read_single_record(REVISED_RATE_RULE_QUERY, freight_bill_id)

        if record is None:
            return {
                "freight_bill_id": freight_bill_id,
                "found": False,
                "rate_rule": None,
            }

        return {
            "freight_bill_id": freight_bill_id,
            "found": True,
            "rate_rule": self._record_to_serializable_dict(record),
        }

    def find_weak_shipment_candidates(
        self,
        freight_bill_id: str,
        window_days: int = 90,
    ) -> Dict[str, Any]:
        records = self._read_records(
            WEAK_SHIPMENT_CANDIDATES_QUERY,
            freight_bill_id,
            window_days=window_days,
        )

        return {
            "freight_bill_id": freight_bill_id,
            "window_days": window_days,
            "candidates_found": len(records),
            "candidates": [
                {
                    "shipment": node_to_dict(record["shipment"]),
                    "carrier": node_to_dict(record["carrier"]),
                    "lane": node_to_dict(record["lane"]),
                    "weight_diff": record["weight_diff"],
                }
                for record in records
            ],
        }

    def find_contract_candidates(self, freight_bill_id: str) -> Dict[str, Any]:
        records = self._read_records(CONTRACT_CANDIDATES_QUERY, freight_bill_id)

        return {
            "freight_bill_id": freight_bill_id,
            "candidates_found": len(records),
            "requires_review": len(records) > 1,
            "candidates": [
                {
                    "contract": node_to_dict(record["contract"]),
                    "rate_rule": node_to_dict(record["rr"]),
                    "lane": node_to_dict(record["lane"]),
                }
                for record in records
            ],
        }

    def _read_records(
        self,
        query: str,
        freight_bill_id: str,
        **params: Any,
    ) -> List[Any]:
        with self.driver.session() as session:
            return session.execute_read(
                lambda tx: list(
                    tx.run(
                        query,
                        freight_bill_id=freight_bill_id,
                        **params,
                    )
                )
            )

    def _read_single_record(
        self,
        query: str,
        freight_bill_id: str,
        **params: Any,
    ) -> Optional[Any]:
        with self.driver.session() as session:
            return session.execute_read(
                lambda tx: tx.run(
                    query,
                    freight_bill_id=freight_bill_id,
                    **params,
                ).single()
            )

    @staticmethod
    def _record_to_serializable_dict(record: Any) -> Dict[str, Any]:
        return {
            key: serialize_neo4j_value(record[key])
            for key in record.keys()
        }
