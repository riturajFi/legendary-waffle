TRACE_HAPPY_PATHS = (
    "FreightBill -> BILLED_BY -> Carrier",
    "FreightBill -> CLAIMS_LANE -> Lane",
    "FreightBill -> CLAIMS_SHIPMENT -> Shipment",
    "Shipment -> SHIPPED_BY -> Carrier",
    "Shipment -> HAS_BOL -> BOL",
    "Shipment -> UNDER_CONTRACT -> Contract",
    "Shipment -> ON_LANE -> Lane",
    "Contract -> HAS_RATE_RULE -> RateRule -> FOR_LANE -> Lane",
)


TRACE_HAPPY_PATH_QUERY = """
MATCH (fb:FreightBill {id: $freight_bill_id})

OPTIONAL MATCH (fb)-[:CLAIMS_SHIPMENT]->(shipment:Shipment)
OPTIONAL MATCH (shipment)-[:SHIPPED_BY]->(shipment_carrier:Carrier)
OPTIONAL MATCH (shipment)-[:HAS_BOL]->(bol:BOL)
OPTIONAL MATCH (shipment)-[:UNDER_CONTRACT]->(contract:Contract)
OPTIONAL MATCH (shipment)-[:ON_LANE]->(shipment_lane:Lane)

OPTIONAL MATCH (contract)-[:HAS_RATE_RULE]->(rate_rule:RateRule)-[:FOR_LANE]->(rate_lane:Lane)
WHERE rate_lane.code = fb.lane

OPTIONAL MATCH (fb)-[:BILLED_BY]->(bill_carrier:Carrier)
OPTIONAL MATCH (fb)-[:CLAIMS_LANE]->(bill_lane:Lane)

RETURN
  fb,
  bill_carrier,
  bill_lane,
  shipment,
  shipment_carrier,
  shipment_lane,
  bol,
  contract,
  rate_rule,
  rate_lane
"""


BFS_TO_EVIDENCE_TARGETS_QUERY = """
MATCH path = (fb:FreightBill {id: $freight_bill_id})
  -[:CLAIMS_SHIPMENT|BILLED_BY|CLAIMS_LANE*1..2]->
  ()
  -[:HAS_BOL|UNDER_CONTRACT|HAS_CONTRACT|HAS_RATE_RULE|FOR_LANE*0..4]->
  (target)
WHERE target:BOL OR target:Contract
RETURN DISTINCT target, labels(target) AS labels, path
ORDER BY length(path), labels(target), target.id
"""


LOAD_CURRENT_FREIGHT_BILL_QUERY = """
MATCH (fb:FreightBill {id: $freight_bill_id})
RETURN fb
"""


DUPLICATE_BILLS_QUERY = """
MATCH (fb:FreightBill {id: $freight_bill_id})
OPTIONAL MATCH (dup:FreightBill)
WHERE dup.id <> fb.id
  AND dup.carrier_id = fb.carrier_id
  AND dup.bill_number = fb.bill_number
  AND (
    dup.bill_date < fb.bill_date
    OR (dup.bill_date = fb.bill_date AND dup.id < fb.id)
  )
RETURN collect(DISTINCT dup) AS duplicate_bills
"""


BILLED_CARRIER_QUERY = """
MATCH (fb:FreightBill {id: $freight_bill_id})
OPTIONAL MATCH (fb)-[:BILLED_BY]->(carrier:Carrier)
RETURN carrier
"""


CARRIER_BY_EXACT_NAME_QUERY = """
MATCH (fb:FreightBill {id: $freight_bill_id})
MATCH (carrier:Carrier)
WHERE toLower(carrier.name) = toLower(fb.carrier_name)
RETURN carrier
ORDER BY carrier.id
"""


CARRIER_BY_LOOSE_NAME_QUERY = """
MATCH (fb:FreightBill {id: $freight_bill_id})
MATCH (carrier:Carrier)
WHERE toLower(carrier.name) CONTAINS toLower(split(fb.carrier_name, " ")[0])
RETURN carrier
ORDER BY carrier.id
"""


EXACT_SHIPMENT_CANDIDATE_QUERY = """
MATCH (fb:FreightBill {id: $freight_bill_id})
OPTIONAL MATCH (fb)-[:CLAIMS_SHIPMENT]->(shipment:Shipment)
OPTIONAL MATCH (shipment)-[:SHIPPED_BY]->(shipment_carrier:Carrier)
OPTIONAL MATCH (shipment)-[:ON_LANE]->(shipment_lane:Lane)
RETURN shipment, shipment_carrier, shipment_lane
"""


OTHER_BILLS_FOR_SAME_SHIPMENT_QUERY = """
MATCH (fb:FreightBill {id: $freight_bill_id})
MATCH (fb)-[:CLAIMS_SHIPMENT]->(s:Shipment)
MATCH (other:FreightBill)-[:CLAIMS_SHIPMENT]->(s)
WHERE other.id <> fb.id
RETURN s, other
ORDER BY other.id
"""


CUMULATIVE_BILLING_FOR_SHIPMENT_QUERY = """
MATCH (fb:FreightBill {id: $freight_bill_id})
MATCH (fb)-[:CLAIMS_SHIPMENT]->(s:Shipment)
MATCH (bill:FreightBill)-[:CLAIMS_SHIPMENT]->(s)
WHERE bill.bill_date < fb.bill_date
  OR (bill.bill_date = fb.bill_date AND bill.id <= fb.id)
RETURN
  s.id AS shipment_id,
  s.total_weight_kg AS shipment_weight,
  collect(bill.id) AS bill_ids,
  sum(bill.billed_weight_kg) AS total_billed_weight
"""


REVISED_RATE_RULE_QUERY = """
MATCH (fb:FreightBill {id: $freight_bill_id})
MATCH (fb)-[:CLAIMS_SHIPMENT]->(s:Shipment)
MATCH (s)-[:UNDER_CONTRACT]->(c:Contract)
MATCH (c)-[:HAS_RATE_RULE]->(rr:RateRule)-[:FOR_LANE]->(lane:Lane)
WHERE lane.code = fb.lane
RETURN
  fb.id AS freight_bill_id,
  fb.bill_date AS bill_date,
  c.id AS contract_id,
  rr.id AS rate_rule_id,
  rr.rate_per_kg AS rate_per_kg,
  rr.fuel_surcharge_percent AS original_fuel_surcharge,
  rr.revised_on AS revised_on,
  rr.revised_fuel_surcharge_percent AS revised_fuel_surcharge
"""


WEAK_SHIPMENT_CANDIDATES_QUERY = """
MATCH (fb:FreightBill {id: $freight_bill_id})
MATCH (fb)-[:BILLED_BY]->(carrier:Carrier)
MATCH (shipment:Shipment)-[:SHIPPED_BY]->(carrier)
MATCH (shipment)-[:ON_LANE]->(lane:Lane)
WHERE lane.code = fb.lane
RETURN
  shipment,
  carrier,
  lane,
  abs(shipment.total_weight_kg - fb.billed_weight_kg) AS weight_diff
ORDER BY weight_diff ASC, shipment.shipment_date DESC, shipment.id
"""


CLAIMED_SHIPMENT_BOLS_QUERY = """
MATCH (fb:FreightBill {id: $freight_bill_id})
MATCH (fb)-[:CLAIMS_SHIPMENT]->(shipment:Shipment)
OPTIONAL MATCH (shipment)-[:HAS_BOL]->(bol:BOL)
RETURN shipment, collect(DISTINCT bol) AS bols
"""


CANDIDATE_SHIPMENT_BOLS_QUERY = """
MATCH (shipment:Shipment {id: $shipment_id})
OPTIONAL MATCH (shipment)-[:HAS_BOL]->(bol:BOL)
RETURN shipment, collect(DISTINCT bol) AS bols
"""


PREVIOUS_BILLS_FOR_SAME_SHIPMENT_QUERY = """
MATCH (fb:FreightBill {id: $freight_bill_id})
MATCH (fb)-[:CLAIMS_SHIPMENT]->(shipment:Shipment)
OPTIONAL MATCH (other:FreightBill)-[:CLAIMS_SHIPMENT]->(shipment)
WHERE other.bill_date < fb.bill_date
  OR (other.bill_date = fb.bill_date AND other.id < fb.id)
RETURN
  shipment,
  collect(DISTINCT other) AS previous_bills,
  sum(other.billed_weight_kg) AS previous_billed_weight
"""


CONTRACT_CANDIDATES_QUERY = """
MATCH (fb:FreightBill {id: $freight_bill_id})
MATCH (fb)-[:BILLED_BY]->(carrier:Carrier)
MATCH (carrier)-[:HAS_CONTRACT]->(contract:Contract)
MATCH (contract)-[:HAS_RATE_RULE]->(rr:RateRule)-[:FOR_LANE]->(lane:Lane)
WHERE lane.code = fb.lane
  AND contract.effective_date <= fb.bill_date
  AND contract.expiry_date >= fb.bill_date
RETURN contract, rr, lane
ORDER BY contract.effective_date DESC, contract.id
"""


CONTRACT_CANDIDATES_BY_SHIPMENT_DATE_QUERY = """
MATCH (fb:FreightBill {id: $freight_bill_id})
MATCH (fb)-[:CLAIMS_SHIPMENT]->(shipment:Shipment)
MATCH (shipment)-[:SHIPPED_BY]->(carrier:Carrier)
MATCH (carrier)-[:HAS_CONTRACT]->(contract:Contract)
MATCH (contract)-[:HAS_RATE_RULE]->(rate_rule:RateRule)-[:FOR_LANE]->(lane:Lane)
WHERE lane.code = fb.lane
  AND contract.effective_date <= shipment.shipment_date
  AND contract.expiry_date >= shipment.shipment_date
RETURN
  shipment,
  contract,
  rate_rule,
  lane
ORDER BY contract.effective_date DESC, contract.id
"""


SHIPMENT_CONTRACT_RATE_RULE_QUERY = """
MATCH (fb:FreightBill {id: $freight_bill_id})
MATCH (fb)-[:CLAIMS_SHIPMENT]->(shipment:Shipment)
OPTIONAL MATCH (shipment)-[:UNDER_CONTRACT]->(contract:Contract)
OPTIONAL MATCH (contract)-[:HAS_RATE_RULE]->(rate_rule:RateRule)-[:FOR_LANE]->(lane:Lane)
WHERE lane.code = fb.lane
RETURN shipment, contract, rate_rule, lane
"""
