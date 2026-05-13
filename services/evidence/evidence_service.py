from typing import Any, Dict

from neo4j import GraphDatabase

from .queries import TRACE_HAPPY_PATH_QUERY, TRACE_HAPPY_PATHS
from .utils import node_to_dict


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
