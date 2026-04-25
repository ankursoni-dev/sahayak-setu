"""v2 search/detail/health endpoints — backed by the new myscheme-pipeline cluster.

Independent from the existing /api/search so the v1 path keeps serving the
hand-curated 96-scheme cluster while v2 ramps up against the scraped 4.6k.
"""

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from backend.rate_limit import limiter
from backend.services import v2_retrieval

router = APIRouter(tags=["search-v2"], prefix="/api/v2")
logger = logging.getLogger(__name__)


@router.get(
    "/search",
    summary="Search schemes (myscheme-pipeline corpus)",
    description=(
        "Two-stage retrieval over the scraped catalogue. The list view is "
        "served entirely from Qdrant payloads — no Mongo round-trip per result. "
        "Call /api/v2/schemes/{slug} to get the full doc."
    ),
)
@limiter.limit("30/minute;300/hour")
async def v2_search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=400, description="Free-text query"),
    level: str | None = Query(None, description="'central' or 'state'"),
    state: str | None = Query(None, max_length=64),
    categories: list[str] | None = Query(None, description="Repeat to OR multiple values"),
    tags: list[str] | None = Query(None, description="Repeat to OR multiple values"),
    limit: int = Query(20, ge=1, le=50),
):
    return await v2_retrieval.search(
        q,
        level=level,
        state=state,
        categories=categories,
        tags=tags,
        limit=limit,
    )


@router.get(
    "/schemes/{slug}",
    summary="Full scheme detail by slug",
    description="Reads from Mongo (sahayaksetu.schemes). Returns 404 when slug is unknown.",
)
@limiter.limit("60/minute;500/hour")
async def v2_scheme_detail(request: Request, slug: str):
    doc = await v2_retrieval.get_scheme(slug)
    if not doc:
        raise HTTPException(status_code=404, detail=f"scheme '{slug}' not found")
    return doc


@router.get(
    "/featured",
    summary="Featured / popular schemes for the home grid",
    description=(
        "Pinned national flagships followed by state-specific schemes when "
        "?state=<name> is supplied. Cards include emoji, summary, apply/source "
        "links — drop-in for the SchemesGrid component."
    ),
)
@limiter.limit("60/minute;500/hour")
async def v2_featured(
    request: Request,
    state: str | None = Query(None, max_length=64, description="User's state for filler schemes"),
    limit: int = Query(12, ge=1, le=20),
):
    return {"items": await v2_retrieval.featured_schemes(state=state, limit=limit)}


@router.get("/health", summary="v2 readiness check")
async def v2_health(request: Request):
    return await v2_retrieval.health()
