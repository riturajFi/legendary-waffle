from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from services.agent import FreightAgent
from services.observability import ObservabilityLogger
from services.seed_data import get_seed_freight_bill, seed_freight_bill_ids
from services.storage import PostgresStore


OBSERVABILITY_PAGE = Path(__file__).resolve().parents[1] / "observability" / "index.html"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        return


class IngestFreightBillRequest(BaseModel):
    id: str = Field(..., description="Freight bill id from the seed data, e.g. FB-2025-101")
    decision_mode: Optional[Literal["rules", "ai"]] = Field(
        default=None,
        description="Optional decision node override. Defaults to FREIGHT_AGENT_DECIDER or rules.",
    )


class ReviewRequest(BaseModel):
    decision: Literal["approve", "dispute", "modify"]
    notes: Optional[str] = None
    modifications: Dict[str, Any] = Field(default_factory=dict)


class DevResetRequest(BaseModel):
    decision_mode: Optional[Literal["rules", "ai"]] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_dotenv()
    store = PostgresStore()
    store.init_schema()
    agent = FreightAgent(store=store)
    observability = ObservabilityLogger()

    app.state.store = store
    app.state.agent = agent
    app.state.observability = observability

    try:
        yield
    finally:
        agent.close()


app = FastAPI(title="Freight Bill Review API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/seed-freight-bills")
def list_seed_freight_bills() -> Dict[str, Any]:
    return {"ids": seed_freight_bill_ids()}


@app.post("/freight-bills", status_code=status.HTTP_201_CREATED)
def ingest_freight_bill(request: Request, payload: IngestFreightBillRequest) -> Dict[str, Any]:
    try:
        freight_bill = get_seed_freight_bill(payload.id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Seed freight bill {payload.id} not found")

    store: PostgresStore = request.app.state.store
    agent: FreightAgent = request.app.state.agent

    store.upsert_ingested_bill(freight_bill)
    try:
        result = agent.run(payload.id, freight_bill, decision_mode=payload.decision_mode)
    except Exception as exc:
        result = store.mark_error(payload.id, str(exc))

    request.app.state.observability.record_freight_bill_result(result)
    return result


@app.get("/freight-bills/{freight_bill_id}")
def get_freight_bill(request: Request, freight_bill_id: str) -> Dict[str, Any]:
    store: PostgresStore = request.app.state.store
    record = store.get_freight_bill(freight_bill_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Freight bill {freight_bill_id} not found")

    request.app.state.observability.record_freight_bill_result(record)
    return record


@app.get("/review-queue")
def get_review_queue(request: Request) -> Dict[str, Any]:
    store: PostgresStore = request.app.state.store
    return {"items": store.list_review_queue()}


@app.get("/observability")
def get_observability_page() -> FileResponse:
    return FileResponse(OBSERVABILITY_PAGE)


@app.get("/observability/log")
def get_observability_log(request: Request) -> Dict[str, Any]:
    observability: ObservabilityLogger = request.app.state.observability
    return {"items": observability.entries()}


@app.post("/review/{freight_bill_id}")
def submit_review(request: Request, freight_bill_id: str, payload: ReviewRequest) -> Dict[str, Any]:
    agent: FreightAgent = request.app.state.agent

    try:
        result = agent.resume_after_review(
            freight_bill_id,
            payload.model_dump(exclude_none=True),
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Freight bill {freight_bill_id} not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    request.app.state.observability.record_freight_bill_result(result)
    return result


@app.post("/dev/reset/{freight_bill_id}")
def reset_freight_bill_for_dev(
    request: Request,
    freight_bill_id: str,
    payload: Optional[DevResetRequest] = None,
) -> Dict[str, Any]:
    try:
        freight_bill = get_seed_freight_bill(freight_bill_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Seed freight bill {freight_bill_id} not found")

    store: PostgresStore = request.app.state.store
    agent: FreightAgent = request.app.state.agent
    reset_options = payload or DevResetRequest()

    try:
        agent.evidence_service.update_freight_bill(freight_bill)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Neo4j freight bill {freight_bill_id} not found")

    store.upsert_ingested_bill(freight_bill)
    try:
        result = agent.run(freight_bill_id, freight_bill, decision_mode=reset_options.decision_mode)
    except Exception as exc:
        result = store.mark_error(freight_bill_id, str(exc))

    request.app.state.observability.record_freight_bill_result(result)
    return result
