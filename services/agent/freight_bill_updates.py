from typing import Any, Dict


MODIFIABLE_FREIGHT_BILL_FIELDS = {
    "carrier_id",
    "carrier_name",
    "bill_number",
    "bill_date",
    "shipment_reference",
    "lane",
    "billed_weight_kg",
    "rate_per_kg",
    "billing_unit",
    "base_charge",
    "fuel_surcharge",
    "gst_amount",
    "total_amount",
}

REQUIRED_FREIGHT_BILL_FIELDS = {
    "bill_number",
    "bill_date",
    "lane",
    "billed_weight_kg",
    "rate_per_kg",
    "base_charge",
    "fuel_surcharge",
    "gst_amount",
    "total_amount",
}


def apply_freight_bill_overrides(
    freight_bill_id: str,
    freight_bill: Dict[str, Any],
    overrides: Dict[str, Any],
    *,
    require_overrides: bool = False,
    context: str = "freight bill update",
) -> Dict[str, Any]:
    if require_overrides and not overrides:
        raise ValueError(f"{context} requires modifications")
    if "id" in overrides:
        raise ValueError("freight bill id cannot be modified")

    unknown_fields = set(overrides) - MODIFIABLE_FREIGHT_BILL_FIELDS
    if unknown_fields:
        fields = ", ".join(sorted(unknown_fields))
        raise ValueError(f"unsupported freight bill modification fields: {fields}")

    updated_bill = {
        **freight_bill,
        **overrides,
        "id": freight_bill_id,
    }
    missing_fields = [
        field
        for field in sorted(REQUIRED_FREIGHT_BILL_FIELDS)
        if updated_bill.get(field) is None
    ]
    if missing_fields:
        fields = ", ".join(missing_fields)
        raise ValueError(f"modified freight bill missing required fields: {fields}")

    return updated_bill
