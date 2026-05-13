import json
from pathlib import Path
from neo4j import GraphDatabase


NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"


driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD),
)


def run_query(tx, query, **params):
    tx.run(query, **params)


def lane_parts(lane_code: str):
    parts = lane_code.split("-")
    origin = parts[0]
    destination = "-".join(parts[1:])
    return origin, destination


def load_carriers(tx, carriers):
    for carrier in carriers:
        tx.run(
            """
            MERGE (c:Carrier {id: $id})
            SET c.name = $name,
                c.carrier_code = $carrier_code,
                c.gstin = $gstin,
                c.bank_account = $bank_account,
                c.status = $status,
                c.onboarded_on = date($onboarded_on)
            """,
            **carrier,
        )


def load_contracts(tx, contracts):
    for contract in contracts:
        tx.run(
            """
            MERGE (c:Contract {id: $id})
            SET c.effective_date = date($effective_date),
                c.expiry_date = date($expiry_date),
                c.status = $status,
                c.notes = $notes
            """,
            id=contract["id"],
            effective_date=contract["effective_date"],
            expiry_date=contract["expiry_date"],
            status=contract["status"],
            notes=contract.get("notes"),
        )

        tx.run(
            """
            MATCH (carrier:Carrier {id: $carrier_id})
            MATCH (contract:Contract {id: $contract_id})
            MERGE (carrier)-[:HAS_CONTRACT]->(contract)
            """,
            carrier_id=contract["carrier_id"],
            contract_id=contract["id"],
        )

        for rate in contract["rate_card"]:
            lane_code = rate["lane"]
            origin, destination = lane_parts(lane_code)

            tx.run(
                """
                MERGE (lane:Lane {code: $code})
                SET lane.origin = $origin,
                    lane.destination = $destination,
                    lane.description = $description
                """,
                code=lane_code,
                origin=origin,
                destination=destination,
                description=rate.get("description"),
            )

            rate_rule_id = f"{contract['id']}::{lane_code}"

            tx.run(
                """
                MERGE (rr:RateRule {id: $id})
                SET rr.lane = $lane,
                    rr.rate_per_kg = $rate_per_kg,
                    rr.rate_per_unit = $rate_per_unit,
                    rr.unit = $unit,
                    rr.unit_capacity_kg = $unit_capacity_kg,
                    rr.alternate_rate_per_kg = $alternate_rate_per_kg,
                    rr.min_charge = $min_charge,
                    rr.fuel_surcharge_percent = $fuel_surcharge_percent,
                    rr.revised_on = CASE
                        WHEN $revised_on IS NULL THEN NULL
                        ELSE date($revised_on)
                    END,
                    rr.revised_fuel_surcharge_percent = $revised_fuel_surcharge_percent
                """,
                id=rate_rule_id,
                lane=lane_code,
                rate_per_kg=rate.get("rate_per_kg"),
                rate_per_unit=rate.get("rate_per_unit"),
                unit=rate.get("unit"),
                unit_capacity_kg=rate.get("unit_capacity_kg"),
                alternate_rate_per_kg=rate.get("alternate_rate_per_kg"),
                min_charge=rate.get("min_charge"),
                fuel_surcharge_percent=rate.get("fuel_surcharge_percent"),
                revised_on=rate.get("revised_on"),
                revised_fuel_surcharge_percent=rate.get("revised_fuel_surcharge_percent"),
            )

            tx.run(
                """
                MATCH (contract:Contract {id: $contract_id})
                MATCH (rr:RateRule {id: $rate_rule_id})
                MATCH (lane:Lane {code: $lane_code})
                MERGE (contract)-[:HAS_RATE_RULE]->(rr)
                MERGE (rr)-[:FOR_LANE]->(lane)
                """,
                contract_id=contract["id"],
                rate_rule_id=rate_rule_id,
                lane_code=lane_code,
            )


def load_shipments(tx, shipments):
    for shipment in shipments:
        lane_code = shipment["lane"]
        origin, destination = lane_parts(lane_code)

        tx.run(
            """
            MERGE (lane:Lane {code: $code})
            SET lane.origin = $origin,
                lane.destination = $destination
            """,
            code=lane_code,
            origin=origin,
            destination=destination,
        )

        tx.run(
            """
            MERGE (s:Shipment {id: $id})
            SET s.shipment_date = date($shipment_date),
                s.status = $status,
                s.total_weight_kg = $total_weight_kg,
                s.notes = $notes
            """,
            id=shipment["id"],
            shipment_date=shipment["shipment_date"],
            status=shipment["status"],
            total_weight_kg=shipment["total_weight_kg"],
            notes=shipment.get("notes"),
        )

        tx.run(
            """
            MATCH (s:Shipment {id: $shipment_id})
            MATCH (carrier:Carrier {id: $carrier_id})
            MATCH (contract:Contract {id: $contract_id})
            MATCH (lane:Lane {code: $lane_code})
            MERGE (s)-[:SHIPPED_BY]->(carrier)
            MERGE (s)-[:UNDER_CONTRACT]->(contract)
            MERGE (s)-[:ON_LANE]->(lane)
            """,
            shipment_id=shipment["id"],
            carrier_id=shipment["carrier_id"],
            contract_id=shipment["contract_id"],
            lane_code=shipment["lane"],
        )


def load_bols(tx, bols):
    for bol in bols:
        tx.run(
            """
            MERGE (b:BOL {id: $id})
            SET b.delivery_date = date($delivery_date),
                b.actual_weight_kg = $actual_weight_kg,
                b.notes = $notes
            """,
            id=bol["id"],
            delivery_date=bol["delivery_date"],
            actual_weight_kg=bol["actual_weight_kg"],
            notes=bol.get("notes") or bol.get("_note"),
        )

        tx.run(
            """
            MATCH (s:Shipment {id: $shipment_id})
            MATCH (b:BOL {id: $bol_id})
            MERGE (s)-[:HAS_BOL]->(b)
            """,
            shipment_id=bol["shipment_id"],
            bol_id=bol["id"],
        )


def load_freight_bills(tx, freight_bills):
    for fb in freight_bills:
        lane_code = fb["lane"]
        origin, destination = lane_parts(lane_code)

        tx.run(
            """
            MERGE (lane:Lane {code: $code})
            SET lane.origin = $origin,
                lane.destination = $destination
            """,
            code=lane_code,
            origin=origin,
            destination=destination,
        )

        tx.run(
            """
            MERGE (fb:FreightBill {id: $id})
            SET fb.scenario = $scenario,
                fb.carrier_id = $carrier_id,
                fb.carrier_name = $carrier_name,
                fb.bill_number = $bill_number,
                fb.bill_date = date($bill_date),
                fb.shipment_reference = $shipment_reference,
                fb.lane = $lane,
                fb.billed_weight_kg = $billed_weight_kg,
                fb.rate_per_kg = $rate_per_kg,
                fb.billing_unit = $billing_unit,
                fb.base_charge = $base_charge,
                fb.fuel_surcharge = $fuel_surcharge,
                fb.gst_amount = $gst_amount,
                fb.total_amount = $total_amount
            """,
            id=fb["id"],
            scenario=fb.get("_scenario"),
            carrier_id=fb.get("carrier_id"),
            carrier_name=fb.get("carrier_name"),
            bill_number=fb["bill_number"],
            bill_date=fb["bill_date"],
            shipment_reference=fb.get("shipment_reference"),
            lane=fb["lane"],
            billed_weight_kg=fb["billed_weight_kg"],
            rate_per_kg=fb["rate_per_kg"],
            billing_unit=fb.get("billing_unit"),
            base_charge=fb["base_charge"],
            fuel_surcharge=fb["fuel_surcharge"],
            gst_amount=fb["gst_amount"],
            total_amount=fb["total_amount"],
        )

        tx.run(
            """
            MATCH (fb:FreightBill {id: $fb_id})
            MATCH (lane:Lane {code: $lane_code})
            MERGE (fb)-[:CLAIMS_LANE]->(lane)
            """,
            fb_id=fb["id"],
            lane_code=lane_code,
        )

        if fb.get("carrier_id"):
            tx.run(
                """
                MATCH (fb:FreightBill {id: $fb_id})
                MATCH (carrier:Carrier {id: $carrier_id})
                MERGE (fb)-[:BILLED_BY]->(carrier)
                """,
                fb_id=fb["id"],
                carrier_id=fb["carrier_id"],
            )

        if fb.get("shipment_reference"):
            tx.run(
                """
                MATCH (fb:FreightBill {id: $fb_id})
                MATCH (s:Shipment {id: $shipment_id})
                MERGE (fb)-[:CLAIMS_SHIPMENT]->(s)
                """,
                fb_id=fb["id"],
                shipment_id=fb["shipment_reference"],
            )


def main():
    data_path = Path(__file__).resolve().parents[2] / "seed data logistics.json"
    data = json.loads(data_path.read_text())

    with driver.session() as session:
        session.execute_write(load_carriers, data["carriers"])
        session.execute_write(load_contracts, data["carrier_contracts"])
        session.execute_write(load_shipments, data["shipments"])
        session.execute_write(load_bols, data["bills_of_lading"])
        session.execute_write(load_freight_bills, data["freight_bills"])

    driver.close()
    print("Loaded seed graph into Neo4j.")


if __name__ == "__main__":
    main()
