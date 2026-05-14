import json
import os
import sys
import unittest
from pathlib import Path
from urllib import error, request


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


API_BASE_URL = os.getenv("FREIGHT_API_BASE_URL", "http://127.0.0.1:8000")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("FREIGHT_API_TEST_TIMEOUT", "45"))
ONLY_FREIGHT_BILL_ID = os.getenv("FREIGHT_TEST_BILL_ID")
TEST_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "test_data.json"


class TestRunAgentForTestData(unittest.TestCase):
    def test_run_agent_for_all_test_freight_bills(self):
        freight_bill_ids = self._test_freight_bill_ids()
        results = []

        for freight_bill_id in freight_bill_ids:
            with self.subTest(freight_bill_id=freight_bill_id):
                print(f"POST {freight_bill_id}", flush=True)
                result = self._post_freight_bill(freight_bill_id)
                results.append(result)
                print(
                    f"-> {result.get('status')} / {result.get('decision_source')}",
                    flush=True,
                )
                self.assertEqual(result.get("id"), freight_bill_id)
                self.assertIn(
                    result.get("status"),
                    {"approved", "disputed", "review_required", "errored"},
                )

        print(json.dumps(results, indent=2, default=str))

    @staticmethod
    def _test_freight_bill_ids():
        data = json.loads(TEST_DATA_PATH.read_text())
        freight_bill_ids = [freight_bill["id"] for freight_bill in data["freight_bills"]]
        if ONLY_FREIGHT_BILL_ID:
            return [freight_bill_id for freight_bill_id in freight_bill_ids if freight_bill_id == ONLY_FREIGHT_BILL_ID]
        return freight_bill_ids

    def _post_freight_bill(self, freight_bill_id):
        payload = json.dumps(
            {
                "id": freight_bill_id,
                "decision_mode": "ai",
            }
        ).encode("utf-8")
        api_request = request.Request(
            f"{API_BASE_URL}/freight-bills",
            data=payload,
            headers={"content-type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(api_request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except TimeoutError:
            self.fail(
                f"{freight_bill_id} timed out after {REQUEST_TIMEOUT_SECONDS} seconds"
            )
        except error.URLError as exc:
            self.skipTest(f"API not available at {API_BASE_URL}: {exc}")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            self.fail(f"{freight_bill_id} failed with HTTP {exc.code}: {body}")


if __name__ == "__main__":
    unittest.main()
