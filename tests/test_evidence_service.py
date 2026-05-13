import os
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.evidence.evidence_service import EvidenceService


class EvidenceServiceIntegrationTest(unittest.TestCase):
    EXPECTED_BILL_EVIDENCE = {
        "FB-2025-101": {
            "bill_number": "SFX/2025/00234",
            "lane": "DEL-BLR",
            "billed_weight_kg": 850,
            "rate_per_kg": 15.0,
            "carrier_id": "CAR001",
            "shipment_id": "SHP-2025-002",
            "shipment_lane": "DEL-BLR",
            "bol_id": "BOL-2025-002",
            "bol_weight_kg": 850,
            "contract_id": "CC-2024-SFX-001",
            "rate_rule_id": "CC-2024-SFX-001::DEL-BLR",
            "rate_rule_rate_per_kg": 15.0,
        },
        "FB-2025-102": {
            "bill_number": "SFX/2025/00251",
            "lane": "DEL-BOM",
            "billed_weight_kg": 600,
            "rate_per_kg": 13.2,
            "carrier_id": "CAR001",
            "shipment_id": None,
        },
        "FB-2025-103": {
            "bill_number": "SFX/2025/00245",
            "lane": "DEL-BOM",
            "billed_weight_kg": 800,
            "rate_per_kg": 12.5,
            "carrier_id": "CAR001",
            "shipment_id": "SHP-2025-001",
            "shipment_lane": "DEL-BOM",
            "bol_id": "BOL-2025-001",
            "bol_weight_kg": 1200,
            "contract_id": "CC-2024-SFX-001",
            "rate_rule_id": "CC-2024-SFX-001::DEL-BOM",
            "rate_rule_rate_per_kg": 12.5,
        },
        "FB-2025-104": {
            "bill_number": "SFX/2025/00267",
            "lane": "DEL-BOM",
            "billed_weight_kg": 1500,
            "rate_per_kg": 12.5,
            "carrier_id": "CAR001",
            "shipment_id": "SHP-2025-001",
            "shipment_lane": "DEL-BOM",
            "bol_id": "BOL-2025-001",
            "bol_weight_kg": 1200,
            "contract_id": "CC-2024-SFX-001",
            "rate_rule_id": "CC-2024-SFX-001::DEL-BOM",
            "rate_rule_rate_per_kg": 12.5,
        },
        "FB-2025-105": {
            "bill_number": "DEL/25-26/1089",
            "lane": "BLR-CHN",
            "billed_weight_kg": 1200,
            "rate_per_kg": 8.7,
            "carrier_id": "CAR002",
            "shipment_id": "SHP-2025-004",
            "shipment_lane": "BLR-CHN",
            "bol_id": "BOL-2025-004",
            "bol_weight_kg": 1200,
            "contract_id": "CC-2024-DEL-001",
            "rate_rule_id": "CC-2024-DEL-001::BLR-CHN",
            "rate_rule_rate_per_kg": 8.0,
        },
        "FB-2025-106": {
            "bill_number": "TCI/2025/00047",
            "lane": "BOM-AHM",
            "billed_weight_kg": 4500,
            "rate_per_kg": 7.5,
            "carrier_id": "CAR003",
            "shipment_id": None,
        },
        "FB-2025-107": {
            "bill_number": "TCI/2025/00052",
            "lane": "BOM-AHM",
            "billed_weight_kg": 7800,
            "rate_per_kg": 6.5,
            "carrier_id": "CAR003",
            "shipment_id": "SHP-2025-005",
            "shipment_lane": "BOM-AHM",
            "bol_id": "BOL-2025-005",
            "bol_weight_kg": 7800,
            "contract_id": "CC-2024-TCI-002",
            "rate_rule_id": "CC-2024-TCI-002::BOM-AHM",
            "alternate_rate_per_kg": 6.5,
            "unit": "FTL",
        },
        "FB-2025-108": {
            "bill_number": "BDA/24-25/4567",
            "lane": "DEL-BOM-AIR",
            "billed_weight_kg": 250,
            "rate_per_kg": 85.0,
            "carrier_id": "CAR004",
            "shipment_id": "SHP-2025-006",
            "shipment_lane": "DEL-BOM-AIR",
            "bol_id": "BOL-2025-006",
            "bol_weight_kg": 250,
            "contract_id": "CC-2024-BDA-001",
            "rate_rule_id": "CC-2024-BDA-001::DEL-BOM-AIR",
            "rate_rule_rate_per_kg": 85.0,
        },
        "FB-2025-109": {
            "bill_number": "SFX/2025/00234",
            "lane": "DEL-BLR",
            "billed_weight_kg": 850,
            "rate_per_kg": 15.0,
            "carrier_id": "CAR001",
            "shipment_id": "SHP-2025-002",
            "shipment_lane": "DEL-BLR",
            "bol_id": "BOL-2025-002",
            "bol_weight_kg": 850,
            "contract_id": "CC-2024-SFX-001",
            "rate_rule_id": "CC-2024-SFX-001::DEL-BLR",
            "rate_rule_rate_per_kg": 15.0,
        },
        "FB-2025-110": {
            "bill_number": "GAT/2025/00089",
            "lane": "CHN-DEL",
            "billed_weight_kg": 350,
            "rate_per_kg": 22.0,
            "carrier_id": None,
            "shipment_id": None,
        },
    }

    def setUp(self):
        self.service = EvidenceService(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password"),
        )

        try:
            self.service.driver.verify_connectivity()
        except Exception as exc:
            self.service.close()
            self.skipTest(f"Neo4j not available: {exc}")

    def tearDown(self):
        self.service.close()

    def test_trace_happy_path_for_all_seed_freight_bills(self):
        for freight_bill_id, expected in self.EXPECTED_BILL_EVIDENCE.items():
            with self.subTest(freight_bill_id=freight_bill_id):
                evidence = self.service.trace_happy_path(freight_bill_id)
                self.assertTrue(
                    evidence["found"],
                    f"{freight_bill_id} not found. Load seed graph before running this test.",
                )

                evidence_data = evidence["evidence"]
                freight_bill = evidence_data["freight_bill"]

                self.assertEqual(evidence["freight_bill_id"], freight_bill_id)
                self.assertEqual(freight_bill["id"], freight_bill_id)
                self.assertEqual(freight_bill["bill_number"], expected["bill_number"])
                self.assertEqual(freight_bill["lane"], expected["lane"])
                self.assertEqual(
                    freight_bill["billed_weight_kg"],
                    expected["billed_weight_kg"],
                )
                self.assertEqual(freight_bill["rate_per_kg"], expected["rate_per_kg"])

                self.assertEqual(evidence_data["bill_lane"]["code"], expected["lane"])
                self._assert_optional_node_id(
                    evidence_data["bill_carrier"],
                    expected["carrier_id"],
                )
                self._assert_optional_node_id(
                    evidence_data["claimed_shipment"],
                    expected["shipment_id"],
                )

                if expected["shipment_id"] is None:
                    self.assertIsNone(evidence_data["shipment_carrier"])
                    self.assertIsNone(evidence_data["shipment_lane"])
                    self.assertIsNone(evidence_data["bol"])
                    self.assertIsNone(evidence_data["contract"])
                    self.assertIsNone(evidence_data["rate_rule"])
                    self.assertIsNone(evidence_data["rate_lane"])
                    continue

                self.assertEqual(
                    evidence_data["shipment_carrier"]["id"],
                    expected["carrier_id"],
                )
                self.assertEqual(
                    evidence_data["shipment_lane"]["code"],
                    expected["shipment_lane"],
                )
                self.assertEqual(evidence_data["bol"]["id"], expected["bol_id"])
                self.assertEqual(
                    evidence_data["bol"]["actual_weight_kg"],
                    expected["bol_weight_kg"],
                )
                self.assertEqual(evidence_data["contract"]["id"], expected["contract_id"])
                self.assertEqual(
                    evidence_data["rate_rule"]["id"],
                    expected["rate_rule_id"],
                )
                self.assertEqual(
                    evidence_data["rate_lane"]["code"],
                    expected["shipment_lane"],
                )

                if "rate_rule_rate_per_kg" in expected:
                    self.assertEqual(
                        evidence_data["rate_rule"]["rate_per_kg"],
                        expected["rate_rule_rate_per_kg"],
                    )
                if "alternate_rate_per_kg" in expected:
                    self.assertEqual(
                        evidence_data["rate_rule"]["alternate_rate_per_kg"],
                        expected["alternate_rate_per_kg"],
                    )
                if "unit" in expected:
                    self.assertEqual(evidence_data["rate_rule"]["unit"], expected["unit"])

    def _assert_optional_node_id(self, node, expected_id):
        if expected_id is None:
            self.assertIsNone(node)
            return

        self.assertIsNotNone(node)
        self.assertEqual(node["id"], expected_id)


if __name__ == "__main__":
    unittest.main()
