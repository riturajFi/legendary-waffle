import os
import sys
from pathlib import Path
from pprint import pprint


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.evidence.evidence_service import EvidenceService


FREIGHT_BILL_IDS = [
    "FB-2025-101",
    "FB-2025-102",
    "FB-2025-103",
    "FB-2025-104",
    "FB-2025-105",
    "FB-2025-106",
    "FB-2025-107",
    "FB-2025-108",
    "FB-2025-109",
    "FB-2025-110",
]


def main():
    service = EvidenceService(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "password"),
    )

    try:
        service.driver.verify_connectivity()

        for freight_bill_id in FREIGHT_BILL_IDS:
            print("=" * 100)
            print(f"Current freight bill: {freight_bill_id}")
            print("=" * 100)
            pprint(service.get_current_freight_bill(freight_bill_id), sort_dicts=False)
            print()

            print(f"Happy path evidence for {freight_bill_id}")
            print("-" * 100)
            pprint(service.trace_happy_path(freight_bill_id), sort_dicts=False)
            print()

            print(f"BFS traversal for {freight_bill_id}")
            print("-" * 100)
            pprint(service.bfs_to_evidence_targets(freight_bill_id), sort_dicts=False)
            print()

            print(f"Duplicate bills for {freight_bill_id}")
            print("-" * 100)
            pprint(service.find_duplicate_bills(freight_bill_id), sort_dicts=False)
            print()

            print(f"Billed carrier for {freight_bill_id}")
            print("-" * 100)
            pprint(service.get_billed_carrier(freight_bill_id), sort_dicts=False)
            print()

            print(f"Carrier exact-name fallback for {freight_bill_id}")
            print("-" * 100)
            pprint(service.find_carriers_by_exact_name(freight_bill_id), sort_dicts=False)
            print()

            print(f"Carrier loose-name fallback for {freight_bill_id}")
            print("-" * 100)
            pprint(service.find_carriers_by_loose_name(freight_bill_id), sort_dicts=False)
            print()

            print(f"Exact shipment candidate for {freight_bill_id}")
            print("-" * 100)
            pprint(service.get_exact_shipment_candidate(freight_bill_id), sort_dicts=False)
            print()

            print(f"Other bills for same shipment for {freight_bill_id}")
            print("-" * 100)
            pprint(
                service.find_other_bills_for_same_shipment(freight_bill_id),
                sort_dicts=False,
            )
            print()

            print(f"BOLs for claimed shipment for {freight_bill_id}")
            print("-" * 100)
            pprint(service.get_bols_for_claimed_shipment(freight_bill_id), sort_dicts=False)
            print()

            print(f"Previous bills for same shipment for {freight_bill_id}")
            print("-" * 100)
            pprint(service.get_previous_bills_for_same_shipment(freight_bill_id), sort_dicts=False)
            print()

            print(f"Cumulative shipment billing for {freight_bill_id}")
            print("-" * 100)
            pprint(
                service.get_cumulative_billing_for_shipment(freight_bill_id),
                sort_dicts=False,
            )
            print()

            print(f"Revised rate rule for {freight_bill_id}")
            print("-" * 100)
            pprint(service.get_revised_rate_rule(freight_bill_id), sort_dicts=False)
            print()

            print(f"Weak shipment candidates for {freight_bill_id}")
            print("-" * 100)
            pprint(service.find_weak_shipment_candidates(freight_bill_id), sort_dicts=False)
            print()

            print(f"Contract candidates by bill date for {freight_bill_id}")
            print("-" * 100)
            pprint(service.find_contract_candidates(freight_bill_id), sort_dicts=False)
            print()

            print(f"Contract candidates by shipment date for {freight_bill_id}")
            print("-" * 100)
            pprint(
                service.find_contract_candidates_by_shipment_date(freight_bill_id),
                sort_dicts=False,
            )
            print()

            print(f"Shipment contract/rate rule for {freight_bill_id}")
            print("-" * 100)
            pprint(service.get_shipment_contract_rate_rule(freight_bill_id), sort_dicts=False)
            print()

    except Exception as exc:
        print(f"Neo4j not available or query failed: {exc}")
        return 1

    finally:
        service.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
