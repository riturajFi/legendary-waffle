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
