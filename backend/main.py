"""FastAPI application factory — wiring + safety middleware."""

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.config import (
    ALLOWED_ORIGINS,
    ALLOWED_ORIGIN_REGEX,
    ENV,
    FRONTEND_ORIGIN,
    MODERATION_STRICT,
    OPENROUTER_MODEL,
    QDRANT_URL,
)
from backend.logging_setup import setup_logging, trace_id_var
from backend.rate_limit import limiter
from backend.routers import (
    error_router,
    feedback_router,
    health_router,
    outcome_router,
    search_router,
    v2_search_router,
    voice_router,
)
from backend.services import mongo_service

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    qdrant_preview = (QDRANT_URL or "")[:20] + ("..." if len(QDRANT_URL or "") > 20 else "")
    print("\n[STARTUP] SahayakSetu - Intelligence Activated")
    print(f"   LLM: openrouter/{OPENROUTER_MODEL}")
    print(f"   RAG: Qdrant @ {qdrant_preview}")
    await mongo_service.ensure_indexes()
    print(f"   Store: MongoDB ({mongo_service.MONGODB_DB})")
    print("   --- Policy ---")
    if MODERATION_STRICT:
        print("   MODERATION_STRICT: on (classifier errors -> block)")
    else:
        print("   MODERATION_STRICT: off (classifier errors -> allow; use on in production)")
    print(f"   ENV: {ENV}")
    yield


OPENAPI_DESCRIPTION = """
Multilingual voice + text RAG API for Indian government welfare schemes.

Endpoints fall into five groups:

- **search** — POST `/api/search` (JSON) and `/api/search/stream` (NDJSON).
- **health** — `/health`, `/ready`, `/ping`, `/` for liveness and readiness.
- **voice** — `/vapi-webhook` receives Vapi assistant tool-call callbacks (HMAC-signed in production).
- **feedback** — `POST /api/feedback` records 👍/👎 reactions with trace correlation.
- **telemetry** — `POST /api/error` records client-side error reports.

Every response carries an `X-Trace-Id` header. Pass it back via `X-Trace-Id` on
subsequent requests for cross-request correlation. Error responses follow
FastAPI's default `{"detail": ...}` shape.
""".strip()

OPENAPI_TAGS = [
    {"name": "search", "description": "Primary RAG endpoints (JSON + NDJSON streaming)."},
    {"name": "health", "description": "Liveness + readiness + lightweight keep-alive."},
    {"name": "voice", "description": "Vapi assistant webhook. HMAC-signed in production."},
    {"name": "feedback", "description": "User 👍/👎 reactions tied to trace IDs."},
    {"name": "telemetry", "description": "Client-side error reports for observability."},
]


def create_app() -> FastAPI:
    app = FastAPI(
        title="SahayakSetu API",
        version="1.0.0",
        description=OPENAPI_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        contact={"name": "SahayakSetu", "url": "https://sahayaksetu.vercel.app"},
        license_info={"name": "Proprietary — Hackblr 2026"},
        lifespan=_lifespan,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS or [FRONTEND_ORIGIN],
        allow_origin_regex=ALLOWED_ORIGIN_REGEX or None,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-User-Id", "X-Trace-Id"],
        expose_headers=["X-Trace-Id"],
    )

    @app.middleware("http")
    async def trace_middleware(request: Request, call_next):
        trace_id = request.headers.get("x-trace-id") or uuid.uuid4().hex
        token = trace_id_var.set(trace_id)
        try:
            response = await call_next(request)
            response.headers["X-Trace-Id"] = trace_id
            return response
        finally:
            trace_id_var.reset(token)

    app.include_router(health_router.router)
    app.include_router(search_router.router)
    app.include_router(voice_router.router)
    app.include_router(feedback_router.router)
    app.include_router(error_router.router)
    app.include_router(outcome_router.router)
    app.include_router(v2_search_router.router)

    @app.exception_handler(Exception)
    async def safe_exception_handler(request: Request, exc: Exception):
        ref = uuid.uuid4().hex[:8]
        logger.exception("unhandled_exception", extra={"path": request.url.path, "ref": ref})
        return JSONResponse(status_code=500, content={"detail": f"Internal error. Reference: {ref}"})

    return app


app = create_app()
