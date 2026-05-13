data blueprint - 

Carrier
  ├── HAS_CONTRACT → Contract
  │       └── HAS_RATE_RULE → RateRule
  │                └── FOR_LANE → Lane
  │
  └── SHIPPED_BY ← Shipment
          ├── UNDER_CONTRACT → Contract
          ├── ON_LANE → Lane
          └── HAS_BOL → BOL

FreightBill
  ├── BILLED_BY → Carrier
  └── CLAIMS_LANE → Lane