from datetime import date
from typing import Any, Dict, List, Optional


class RuleEngine:
    def run(self, evidence_pack: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            self.duplicate_check(evidence_pack),
            self.carrier_check(evidence_pack),
            self.shipment_check(evidence_pack),
            self.rate_check(evidence_pack),
            self.weight_check(evidence_pack),
            self.amount_check(evidence_pack),
        ]

    def duplicate_check(self, pack: Dict[str, Any]) -> Dict[str, Any]:
        duplicates = pack.get("duplicates", {}).get("duplicates", [])
        status = "fail" if duplicates else "pass"

        return self._check(
            "duplicate_check",
            status,
            "duplicate freight bill found" if duplicates else "no duplicate freight bill",
            {"duplicates": [bill.get("id") for bill in duplicates]},
        )

    def carrier_check(self, pack: Dict[str, Any]) -> Dict[str, Any]:
        carrier = pack.get("carrier", {}).get("linked", {}).get("carrier")
        exact_matches = pack.get("carrier", {}).get("exact_name_matches", {}).get("carriers", [])
        loose_matches = pack.get("carrier", {}).get("loose_name_matches", {}).get("carriers", [])

        if carrier:
            return self._check("carrier_check", "pass", "linked carrier found", carrier)
        if exact_matches:
            return self._check("carrier_check", "review", "carrier matched by exact name", exact_matches)
        if loose_matches:
            return self._check("carrier_check", "review", "carrier matched by loose name", loose_matches)

        return self._check("carrier_check", "fail", "no carrier evidence found")

    def shipment_check(self, pack: Dict[str, Any]) -> Dict[str, Any]:
        freight_bill = self._freight_bill(pack)
        shipment = pack.get("shipment", {}).get("exact", {}).get("shipment")
        candidates = pack.get("shipment", {}).get("weak_candidates", {}).get("candidates", [])
        selected_contract = self._selected_contract_candidate(pack)

        if shipment:
            return self._check("shipment_check", "pass", "claimed shipment found", shipment)
        if self._contract_only_bill(freight_bill, selected_contract):
            return self._check(
                "shipment_check",
                "pass",
                "no shipment reference; contract selected by bill date, lane, carrier, and rate",
                {
                    "selected_contract": selected_contract.get("contract"),
                    "selected_rate_rule": selected_contract.get("rate_rule"),
                    "weak_candidates": candidates,
                },
            )
        if candidates:
            return self._check("shipment_check", "review", "weak shipment candidates found", candidates)

        return self._check("shipment_check", "fail", "no shipment evidence found")

    def rate_check(self, pack: Dict[str, Any]) -> Dict[str, Any]:
        freight_bill = self._freight_bill(pack)
        rate_rule = self._rate_rule(pack)
        selected_contract = self._selected_contract_candidate(pack)

        if not freight_bill:
            return self._check("rate_check", "fail", "freight bill missing")
        if not rate_rule:
            return self._check("rate_check", "review", "no rate rule selected")

        billed_rate = freight_bill.get("rate_per_kg")
        allowed_rates = [
            rate_rule.get("rate_per_kg"),
            rate_rule.get("alternate_rate_per_kg"),
        ]
        allowed_rates = [rate for rate in allowed_rates if rate is not None]

        if any(self._money_equal(billed_rate, rate) for rate in allowed_rates):
            return self._check("rate_check", "pass", "billed rate matches rate rule", {
                "billed_rate": billed_rate,
                "allowed_rates": allowed_rates,
                "selected_contract": (selected_contract or {}).get("contract"),
                "selected_rate_rule": rate_rule,
            })

        return self._check("rate_check", "fail", "billed rate does not match rate rule", {
            "billed_rate": billed_rate,
            "allowed_rates": allowed_rates,
            "selected_contract": (selected_contract or {}).get("contract"),
            "selected_rate_rule": rate_rule,
        })

    def weight_check(self, pack: Dict[str, Any]) -> Dict[str, Any]:
        freight_bill = self._freight_bill(pack)
        shipment = pack.get("shipment", {}).get("exact", {}).get("shipment")
        bols = pack.get("bol", {}).get("bols", [])
        cumulative = pack.get("cumulative_billing", {}).get("cumulative_billing")
        selected_contract = self._selected_contract_candidate(pack)

        if not freight_bill:
            return self._check("weight_check", "fail", "freight bill missing")
        if not shipment and self._contract_only_bill(freight_bill, selected_contract):
            return self._check(
                "weight_check",
                "pass",
                "no shipment reference; weight accepted against selected contract billing",
                {
                    "billed_weight": freight_bill.get("billed_weight_kg") or 0,
                    "selected_contract": selected_contract.get("contract"),
                    "selected_rate_rule": selected_contract.get("rate_rule"),
                },
            )
        if not shipment:
            return self._check("weight_check", "review", "no exact shipment for weight check")

        billed_weight = freight_bill.get("billed_weight_kg") or 0
        delivered_weight = sum(bol.get("actual_weight_kg") or 0 for bol in bols)
        shipment_weight = shipment.get("total_weight_kg") or 0
        total_billed_weight = (cumulative or {}).get("total_billed_weight")

        if total_billed_weight and shipment_weight and total_billed_weight > shipment_weight:
            return self._check("weight_check", "fail", "total billed weight exceeds shipment weight", {
                "shipment_weight": shipment_weight,
                "total_billed_weight": total_billed_weight,
            })
        if delivered_weight and billed_weight > delivered_weight:
            return self._check("weight_check", "fail", "billed weight exceeds delivered BOL weight", {
                "billed_weight": billed_weight,
                "delivered_weight": delivered_weight,
            })

        return self._check("weight_check", "pass", "weight evidence looks valid", {
            "billed_weight": billed_weight,
            "delivered_weight": delivered_weight,
            "shipment_weight": shipment_weight,
            "total_billed_weight": total_billed_weight,
        })

    def amount_check(self, pack: Dict[str, Any]) -> Dict[str, Any]:
        freight_bill = self._freight_bill(pack)
        rate_rule = self._rate_rule(pack)

        if not freight_bill:
            return self._check("amount_check", "fail", "freight bill missing")

        billed_weight = freight_bill.get("billed_weight_kg") or 0
        billed_rate = freight_bill.get("rate_per_kg") or 0
        expected_base = billed_weight * billed_rate

        if not self._money_equal(expected_base, freight_bill.get("base_charge")):
            return self._check("amount_check", "fail", "base charge mismatch", {
                "expected_base": round(expected_base, 2),
                "actual_base": freight_bill.get("base_charge"),
            })

        fuel_percent = self._fuel_percent(freight_bill, rate_rule)
        if fuel_percent is None:
            return self._check("amount_check", "review", "base charge matches, fuel rule missing")

        expected_fuel = expected_base * fuel_percent / 100
        expected_gst = (expected_base + expected_fuel) * 0.18
        expected_total = expected_base + expected_fuel + expected_gst

        mismatches = {}
        if not self._money_equal(expected_fuel, freight_bill.get("fuel_surcharge")):
            mismatches["fuel_surcharge"] = {
                "expected": round(expected_fuel, 2),
                "actual": freight_bill.get("fuel_surcharge"),
            }
        if not self._money_equal(expected_gst, freight_bill.get("gst_amount")):
            mismatches["gst_amount"] = {
                "expected": round(expected_gst, 2),
                "actual": freight_bill.get("gst_amount"),
            }
        if not self._money_equal(expected_total, freight_bill.get("total_amount")):
            mismatches["total_amount"] = {
                "expected": round(expected_total, 2),
                "actual": freight_bill.get("total_amount"),
            }

        if mismatches:
            return self._check("amount_check", "fail", "amount mismatch", mismatches)

        return self._check("amount_check", "pass", "amounts match", {
            "base_charge": round(expected_base, 2),
            "fuel_surcharge": round(expected_fuel, 2),
            "gst_amount": round(expected_gst, 2),
            "total_amount": round(expected_total, 2),
        })

    def _freight_bill(self, pack: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return pack.get("freight_bill", {}).get("freight_bill")

    def _rate_rule(self, pack: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        used = pack.get("contracts", {}).get("used_by_shipment", {}).get("rate_rule")
        if used:
            return used

        selected = self._selected_contract_candidate(pack)
        if selected:
            return selected.get("rate_rule")

        return None

    def _selected_contract_candidate(self, pack: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        used = pack.get("contracts", {}).get("used_by_shipment", {})
        if used.get("rate_rule"):
            return {
                "contract": used.get("contract"),
                "rate_rule": used.get("rate_rule"),
                "lane": used.get("lane"),
            }

        candidates = pack.get("contracts", {}).get("by_bill_date", {}).get("candidates", [])
        freight_bill = self._freight_bill(pack) or {}
        billed_rate = freight_bill.get("rate_per_kg")

        matching_candidates = [
            candidate
            for candidate in candidates
            if self._rate_matches(billed_rate, candidate.get("rate_rule"))
        ]
        if len(matching_candidates) == 1:
            return matching_candidates[0]
        if len(candidates) == 1:
            return candidates[0]

        return None

    @staticmethod
    def _contract_only_bill(
        freight_bill: Optional[Dict[str, Any]],
        selected_contract: Optional[Dict[str, Any]],
    ) -> bool:
        if not freight_bill or not selected_contract:
            return False

        return not freight_bill.get("shipment_reference")

    def _fuel_percent(
        self,
        freight_bill: Dict[str, Any],
        rate_rule: Optional[Dict[str, Any]],
    ) -> Optional[float]:
        if not rate_rule:
            return None

        revised_on = rate_rule.get("revised_on")
        revised_fuel = rate_rule.get("revised_fuel_surcharge_percent")
        bill_date = freight_bill.get("bill_date")

        if revised_on and revised_fuel is not None and self._parse_date(bill_date) >= self._parse_date(revised_on):
            return revised_fuel

        return rate_rule.get("fuel_surcharge_percent")

    def _rate_matches(
        self,
        billed_rate: Optional[float],
        rate_rule: Optional[Dict[str, Any]],
    ) -> bool:
        if not rate_rule:
            return False

        return any(
            self._money_equal(billed_rate, rate)
            for rate in (
                rate_rule.get("rate_per_kg"),
                rate_rule.get("alternate_rate_per_kg"),
            )
            if rate is not None
        )

    @staticmethod
    def _check(
        name: str,
        status: str,
        reason: str,
        details: Optional[Any] = None,
    ) -> Dict[str, Any]:
        return {
            "name": name,
            "status": status,
            "reason": reason,
            "details": details or {},
        }

    @staticmethod
    def _money_equal(left: Optional[float], right: Optional[float]) -> bool:
        if left is None or right is None:
            return False

        return abs(float(left) - float(right)) <= 0.05

    @staticmethod
    def _parse_date(value: str) -> date:
        return date.fromisoformat(value)
