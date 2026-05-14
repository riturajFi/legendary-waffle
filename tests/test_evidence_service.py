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
            print(f"Evidence pack for {freight_bill_id}")
            print("=" * 100)
            evidence_pack = service.get_evidence(freight_bill_id)
            pprint(evidence_pack, sort_dicts=False)
            print()

    except Exception as exc:
        print(f"Neo4j not available or query failed: {exc}")
        return 1

    finally:
        service.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
