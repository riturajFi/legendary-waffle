# Freight Bill Review API

## Run With Docker

### 1. Create `.env`

```bash
OPENAI_API_KEY=your_openai_key
OPENAI_DECISION_MODEL=gpt-4.1-mini
FREIGHT_AGENT_DECIDER=ai
```

### 2. Start Everything

```bash
docker compose up --build
```

This starts:

- Neo4j
- Postgres
- seed loader for `data/seed data logistics.json`
- FastAPI backend

Backend:

```text
http://127.0.0.1:8000
```

Neo4j browser:

```text
http://127.0.0.1:7474
```

Neo4j login:

```text
neo4j / password
```

### 3. Test API

Health check:

```bash
curl http://127.0.0.1:8000/health
```

List freight bills:

```bash
curl http://127.0.0.1:8000/seed-freight-bills
```

Run one freight bill:

```bash
curl -X POST http://127.0.0.1:8000/freight-bills \
  -H 'content-type: application/json' \
  -d '{"id":"FB-2025-101","decision_mode":"ai"}'
```

Review queue:

```bash
curl http://127.0.0.1:8000/review-queue
```

Observability page:

```text
http://127.0.0.1:8000/observability
```

### 4. Stop

```bash
docker compose down
```

Remove all database data:

```bash
docker compose down -v
```

## Run Locally Without Docker Backend

### 1. Create Python Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Start Databases

```bash
docker compose up -d neo4j postgres
```

### 3. Load Data

```bash
venv/bin/python data/migration/scripts/load_seed_graph.py "data/seed data logistics.json" --clear
```

### 4. Run Backend

```bash
venv/bin/uvicorn api.main:app --reload
```

## Test Data

Load test graph:

```bash
venv/bin/python data/migration/scripts/load_seed_graph.py data/test_data.json --clear
```

Run backend with test data:

```bash
FREIGHT_SEED_DATA_PATH=data/test_data.json \
venv/bin/uvicorn api.main:app --reload
```

Run all test bills:

```bash
venv/bin/python -m unittest tests.test_run_test_data_agent
```

Run one test bill:

```bash
FREIGHT_TEST_BILL_ID=FB-TEST-WRONG-FUEL \
venv/bin/python -m unittest tests.test_run_test_data_agent
```
