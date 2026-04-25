"""Environment configuration and client singletons."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001").strip()
# Models to race for generation calls — first to respond wins, others are cancelled.
# Set RACE_MODELS= (empty) to disable racing and use only OPENROUTER_MODEL.
_RACE_MODELS_RAW = os.getenv("RACE_MODELS", "google/gemini-2.0-flash-001,openai/gpt-4o-mini").strip()
RACE_MODELS: list[str] = [m.strip() for m in _RACE_MODELS_RAW.split(",") if m.strip()] or [OPENROUTER_MODEL]
OPENROUTER_REFERRER = os.getenv("OPENROUTER_REFERRER", "https://sahayaksetu.vercel.app").strip()
OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "SahayakSetu").strip()
ENV = os.getenv("ENV", "development").strip().lower()
IS_PRODUCTION = ENV == "production"

# Public-facing URLs. In production these MUST be set explicitly so a misconfigured
# staging deploy does not silently route through the live host. In dev we default to
# loopback so local-only setups (no external host) still work without env wiring.
_DEV_BACKEND_DEFAULT = "http://localhost:8000"
_DEV_FRONTEND_DEFAULT = "http://localhost:5173"
BACKEND_URL = os.getenv("BACKEND_URL", "" if IS_PRODUCTION else _DEV_BACKEND_DEFAULT).strip()
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "" if IS_PRODUCTION else _DEV_FRONTEND_DEFAULT).strip()
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", FRONTEND_ORIGIN).split(",")
    if origin.strip()
]
# Combined default regex: allow any localhost port (for local dev, including Vite's :5173
# and preview :4173) AND any *.vercel.app deployment. Localhost origins cannot reach a
# production deployment, so permitting them unconditionally is safe.
ALLOWED_ORIGIN_REGEX = os.getenv(
    "ALLOWED_ORIGIN_REGEX",
    r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$|^https://[a-z0-9-]+\.vercel\.app$",
).strip()

# Also keep common local origins in the explicit list so wildcard-less deployments still work.
_local_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:8080",
]
for _o in _local_origins:
    if _o not in ALLOWED_ORIGINS:
        ALLOWED_ORIGINS.append(_o)
VAPI_WEBHOOK_SECRET = os.getenv("VAPI_WEBHOOK_SECRET", "").strip()
# Signed-body timestamp skew (seconds). Mitigates replay of very old captured payloads.
VAPI_WEBHOOK_MAX_SKEW_S = int(os.getenv("VAPI_WEBHOOK_MAX_SKEW_S", "300"))

# HMAC key for session-user-id signing. Empty => unsigned (dev-only).
SESSION_SECRET = os.getenv("SESSION_SECRET", "").strip()

# MongoDB — sessions, feedback, webhook nonces.
MONGODB_URL = os.getenv("MONGODB_URL", "").strip()
MONGODB_DB = os.getenv("MONGODB_DB", "sahayaksetu").strip()


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None or not str(v).strip():
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


# True: moderation JSON/call failures block (fail-closed). Default: on in prod, off in dev.
MODERATION_STRICT = _env_bool("MODERATION_STRICT", default=IS_PRODUCTION)
# If True, Vapi webhook JSON must include a parseable timestamp (strict integrations).
VAPI_WEBHOOK_REQUIRE_TIMESTAMP = _env_bool("VAPI_WEBHOOK_REQUIRE_TIMESTAMP", False)
# True enables structured JSON generation path for /api/search.
# Default ON in production to keep grounding verifier active.
LLM_JSON_MODE = _env_bool("LLM_JSON_MODE", IS_PRODUCTION)
# Enable lightweight hybrid retrieval: vector score + keyword overlap blend.
HYBRID_RETRIEVAL = _env_bool("HYBRID_RETRIEVAL", False)
DEBUG_RETRIEVAL = _env_bool("DEBUG_RETRIEVAL", False)

QDRANT_COLLECTION = "sahayak_schemes"
SIMILARITY_THRESHOLD = 0.2
RAG_VECTOR_QUERY_LIMIT = 8
RAG_VECTOR_CANDIDATE_LIMIT = 12
HYBRID_KEYWORD_WEIGHT = float(os.getenv("HYBRID_KEYWORD_WEIGHT", "0.3"))
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
# Adaptive floor: rejects very weak vector neighbours (junk). Default 0.15 (panel tuning); override via env.
NEAR_MISS_SCORE_FLOOR = float(
    os.getenv("NEAR_MISS_SCORE_FLOOR", str(max(0.15, SIMILARITY_THRESHOLD * 0.4)))
)
NEAR_MISS_MAX = 2
HISTORY_WINDOW = 20
MAX_SESSION_STORE_SIZE = 500
EVICT_COUNT = 100
LLM_HISTORY_MESSAGE_LIMIT = 4
RETRIEVAL_SOFT_FLOOR = 0.35
RETRIEVAL_HARD_FLOOR = 0.55

# Rate limiting — number of trusted reverse-proxy hops in front of the app.
# 0 = no proxy (use socket peer); 1 = single proxy (Render/Vercel default); 2+ = chained.
TRUSTED_PROXY_COUNT = int(os.getenv("TRUSTED_PROXY_COUNT", "1" if IS_PRODUCTION else "0"))

# External call limits — tune via env in production.
LLM_CALL_TIMEOUT_S = float(os.getenv("LLM_CALL_TIMEOUT_S", "120"))
AGENT_PLAN_CALL_TIMEOUT_S = float(os.getenv("AGENT_PLAN_CALL_TIMEOUT_S", "90"))
MODERATION_CALL_TIMEOUT_S = float(os.getenv("MODERATION_CALL_TIMEOUT_S", "45"))
REWRITE_QUERY_TIMEOUT_S = float(os.getenv("REWRITE_QUERY_TIMEOUT_S", "30"))
API_RETRY_ATTEMPTS = int(os.getenv("API_RETRY_ATTEMPTS", "3"))
API_RETRY_BASE_DELAY_S = float(os.getenv("API_RETRY_BASE_DELAY_S", "0.4"))
API_RETRY_MAX_DELAY_S = float(os.getenv("API_RETRY_MAX_DELAY_S", "6.0"))
MAX_PROMPT_CHARS = int(os.getenv("MAX_PROMPT_CHARS", "16000"))
MAX_QUERY_CHARS = int(os.getenv("MAX_QUERY_CHARS", "600"))


# --- Required-config enforcement ----------------------------------------------------
# Fail loudly at startup rather than at first request so misconfigured deploys never
# pass /health. Dev mode tolerates missing optional secrets; production does not.

def _missing_in_prod() -> list[str]:
    missing: list[str] = []
    if not SESSION_SECRET:
        missing.append("SESSION_SECRET")
    if not VAPI_WEBHOOK_SECRET:
        missing.append("VAPI_WEBHOOK_SECRET")
    if not MONGODB_URL:
        missing.append("MONGODB_URL")
    if not BACKEND_URL:
        missing.append("BACKEND_URL")
    if not FRONTEND_ORIGIN:
        missing.append("FRONTEND_ORIGIN")
    return missing


if not QDRANT_URL:
    raise RuntimeError("Missing required env vars. QDRANT_URL=MISSING")
if not OPENROUTER_API_KEY:
    raise RuntimeError("Missing required env vars. OPENROUTER_API_KEY=MISSING")

if IS_PRODUCTION:
    _missing = _missing_in_prod()
    if _missing:
        raise RuntimeError(
            "Missing required production env vars: " + ", ".join(_missing)
        )

# Lazy Qdrant client — built on first use so import-time failures (HuggingFace download
# stalls, network blips) don't crash before lifespan startup. Use get_qdrant_client().
_qdrant_client = None


def get_qdrant_client():
    """Return the singleton Qdrant client, building it on first call."""
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient

        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
        client.set_model(EMBEDDING_MODEL)
        _qdrant_client = client
    return _qdrant_client


class _QdrantClientProxy:
    """Backwards-compat proxy: ``from backend.config import qdrant_client`` keeps working,
    but the underlying client is built lazily on first attribute access. Lets lifespan
    startup or tests replace the cached client without touching every importer."""

    def __getattr__(self, item):
        return getattr(get_qdrant_client(), item)

    def __repr__(self) -> str:  # pragma: no cover — diagnostic only
        return f"<QdrantClientProxy initialised={_qdrant_client is not None}>"


qdrant_client = _QdrantClientProxy()

openrouter_client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_BASE_URL,
    max_retries=0,
    default_headers={
        "HTTP-Referer": OPENROUTER_REFERRER,
        "X-Title": OPENROUTER_APP_TITLE,
    },
)
