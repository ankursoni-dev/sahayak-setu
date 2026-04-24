from fastapi import APIRouter, HTTPException

from backend.config import OPENROUTER_MODEL, SIMILARITY_THRESHOLD
from backend.services.dependency_health import readiness_snapshot

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe", description="Returns active LLM model + retrieval threshold.")
def handle_health():
    return {"status": "online", "model": OPENROUTER_MODEL, "threshold": SIMILARITY_THRESHOLD}


@router.get(
    "/ready",
    summary="Readiness probe",
    description="503 when Qdrant/Redis/LLM dependencies are not connectable.",
    responses={503: {"description": "One or more dependencies unreachable."}},
)
async def handle_ready():
    snapshot = await readiness_snapshot()
    if not snapshot["ready"]:
        raise HTTPException(status_code=503, detail=snapshot)
    return snapshot


@router.get("/ping", summary="Lightweight keep-alive")
def handle_ping():
    return "pong"


@router.get("/", summary="Service banner")
def handle_root():
    return {"status": "SahayakSetu Backend Online", "model": OPENROUTER_MODEL}
