import os
import sys
from pathlib import Path
from pprint import pprint


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.evidence.evidence_service import EvidenceService
from services.rules import RuleEngine


FREIGHT_BILL_ID = "FB-2025-110"


def main():
    evidence_service = EvidenceService(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "password"),
    )
    rule_engine = RuleEngine()

    try:
        evidence_service.driver.verify_connectivity()
        evidence_pack = evidence_service.get_evidence(FREIGHT_BILL_ID)
        checks = rule_engine.run(evidence_pack)

        print("=" * 100)
        print(f"Rule checks for {FREIGHT_BILL_ID}")
        print("=" * 100)
        pprint(checks, sort_dicts=False)

    except Exception as exc:
        print(f"Neo4j not available or rule check failed: {exc}")
        return 1

    finally:
        evidence_service.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
