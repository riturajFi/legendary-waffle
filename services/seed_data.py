import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_SEED_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "seed data logistics.json"


@lru_cache(maxsize=1)
def load_seed_data() -> Dict[str, Any]:
    seed_data_path = Path(os.getenv("FREIGHT_SEED_DATA_PATH", DEFAULT_SEED_DATA_PATH))
    return json.loads(seed_data_path.read_text())


def get_seed_freight_bill(freight_bill_id: str) -> Dict[str, Any]:
    for freight_bill in load_seed_data()["freight_bills"]:
        if freight_bill["id"] == freight_bill_id:
            return dict(freight_bill)

    raise KeyError(freight_bill_id)


def seed_freight_bill_ids() -> List[str]:
    return [freight_bill["id"] for freight_bill in load_seed_data()["freight_bills"]]
