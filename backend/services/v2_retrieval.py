"""
v2 retrieval — talks to the new ``sahayaksetu`` Qdrant cluster (the one populated
by the myscheme-pipeline scrape + ingest, ~4.6k schemes) and to ``sahayaksetu.schemes``
in Mongo for full-detail lookup.

Kept entirely separate from the existing ``retrieval_service`` / ``grounding_service``
so the original /api/search keeps working while we validate v2 against real traffic.

Memory discipline:
- Embedder is a module-level lazy singleton, same model the grounding service already
  loads (``BAAI/bge-small-en-v1.5``). Sharing the model means v2 adds zero RSS once
  grounding has warmed it up.
- Qdrant client is a module-level singleton built from MYSCHEME_QDRANT_* env vars.
- Mongo connection is borrowed from the existing ``mongo_service``.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    QuantizationSearchParams,
    SearchParams,
)

logger = logging.getLogger(__name__)

V2_QDRANT_COLLECTION = "schemes"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_LIMIT = 20
MAX_LIMIT = 50

_qclient: QdrantClient | None = None
_qclient_lock = threading.Lock()
_embedder = None
_embedder_lock = threading.Lock()


def _get_qclient() -> QdrantClient:
    global _qclient
    if _qclient is not None:
        return _qclient
    with _qclient_lock:
        if _qclient is None:
            url = os.environ.get("MYSCHEME_QDRANT_URL")
            key = os.environ.get("MYSCHEME_QDRANT_API_KEY")
            if not url:
                raise RuntimeError("MYSCHEME_QDRANT_URL not configured")
            _qclient = QdrantClient(url=url, api_key=key or None)
    return _qclient


def _get_embedder():
    """Reuse fastembed/BAAI — same model the grounding service uses, so the model
    weights live in process exactly once regardless of how many services touch it."""
    global _embedder
    if _embedder is not None:
        return _embedder
    with _embedder_lock:
        if _embedder is None:
            from fastembed import TextEmbedding
            _embedder = TextEmbedding(EMBEDDING_MODEL)
    return _embedder


def _embed(text: str) -> list[float]:
    return list(next(_get_embedder().embed([text])))


def _build_filter(
    *,
    level: str | None,
    state: str | None,
    categories: list[str] | None,
    tags: list[str] | None,
) -> Filter | None:
    """Translate query params into a Qdrant Filter. ``must`` semantics — every
    supplied filter must match. Multi-value params (categories/tags) become MatchAny
    so any of the requested values qualifies."""
    must: list[FieldCondition] = []
    if level:
        must.append(FieldCondition(key="level", match=MatchValue(value=level.lower())))
    if state:
        must.append(FieldCondition(key="state", match=MatchValue(value=state)))
    if categories:
        must.append(FieldCondition(key="categories", match=MatchAny(any=categories)))
    if tags:
        must.append(FieldCondition(key="tags", match=MatchAny(any=tags)))
    return Filter(must=must) if must else None


async def search(
    query: str,
    *,
    level: str | None = None,
    state: str | None = None,
    categories: list[str] | None = None,
    tags: list[str] | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Execute a v2 search. Returns the public response shape directly so the
    router stays as thin as possible."""
    if not query or not query.strip():
        return {"query": query, "took_ms": 0, "total": 0, "results": []}
    limit = max(1, min(int(limit), MAX_LIMIT))

    started = time.monotonic()
    qvec = _embed(query.strip())
    flt = _build_filter(level=level, state=state, categories=categories, tags=tags)
    res = _get_qclient().query_points(
        collection_name=V2_QDRANT_COLLECTION,
        query=qvec,
        query_filter=flt,
        limit=limit,
        with_payload=True,
        # Rescore over the full-precision vectors after the INT8 ANN pass —
        # cheap accuracy boost given on_disk + scalar quantization storage.
        search_params=SearchParams(
            quantization=QuantizationSearchParams(rescore=True),
        ),
    )
    took_ms = round((time.monotonic() - started) * 1000)

    results = []
    for pt in res.points:
        p = pt.payload or {}
        slug = p.get("slug") or ""
        results.append({
            "slug": slug,
            "score": pt.score,
            "name": p.get("name"),
            "level": p.get("level"),
            "state": p.get("state"),
            "categories": p.get("categories") or [],
            "tags": p.get("tags") or [],
            "short_summary": p.get("short_summary") or "",
            "detail_url": f"/api/v2/schemes/{slug}" if slug else None,
        })
    return {
        "query": query,
        "took_ms": took_ms,
        "total": len(results),
        "results": results,
    }


async def get_scheme(slug: str) -> dict | None:
    """Full doc lookup from Mongo. Strips the ``raw`` field if it ever sneaks in
    (we don't store it now, but defence-in-depth)."""
    from backend.services.mongo_service import db
    doc = await db().schemes.find_one({"slug": slug})
    if not doc:
        return None
    doc.pop("raw", None)
    return doc


# --- Featured / popular schemes -------------------------------------------------
# Powering the "Commonly asked" grid on the home page. Always pins a few national
# flagships so newcomers see something familiar; pads the rest with state-specific
# schemes when the user has supplied a state. Skips any slug not yet in Mongo so
# the endpoint stays responsive while the catalogue is still ingesting.

# Order matters — first 5 are the "hot" national pins; we walk this list and take
# the first ones whose Mongo doc exists. If a slug ever 404s (renamed upstream,
# not yet scraped), we skip and keep going.
FLAGSHIP_SLUGS = [
    "pm-kisan",          # PM-KISAN — agriculture income support
    "ab-pmjay",          # Ayushman Bharat — health cover
    "pmmy",              # PM Mudra Yojana — small business loans
    "pmuy",              # PM Ujjwala — LPG for BPL
    "mgnrega",           # Mahatma Gandhi NREGA — rural employment
    # Backup flagships in case any of the above are missing from the catalogue.
    "pmay-u", "pmjdy", "pm-svanidhi", "pmv", "pmuy2", "pmay-g", "pmkmdy",
]

# Default-by-category emojis. Layered on top of slug-specific overrides below.
_CATEGORY_EMOJI = {
    "Agriculture": "🌾",
    "Health & Wellness": "🏥",
    "Health": "🏥",
    "Education & Learning": "🎓",
    "Education": "🎓",
    "Housing & Shelter": "🏠",
    "Housing": "🏠",
    "Banking,Financial Services and Insurance": "🏦",
    "Business & Entrepreneurship": "💼",
    "Skills & Employment": "🛠️",
    "Employment": "🛠️",
    "Social welfare & Empowerment": "🤝",
    "Energy": "⚡",
    "Travel & Tourism": "✈️",
    "Sports & Culture": "🏅",
    "Science, IT & Communications": "🧪",
    "Public Safety, Law & Justice": "⚖️",
    "Transport & Infrastructure": "🚧",
}
# Slug-specific emojis trump category — keeps the famous schemes visually familiar.
_SLUG_EMOJI = {
    "pm-kisan": "🌾",
    "ab-pmjay": "🏥",
    "pmmy": "💰",
    "pmuy": "🔥",
    "pmuy2": "🔥",
    "mgnrega": "⚒️",
    "pmay-u": "🏠",
    "pmay-g": "🏠",
    "pmjdy": "💳",
    "pm-svanidhi": "🛒",
    "pmv": "🔧",
    "pmkmdy": "🌾",
}


def _emoji_for(doc: dict) -> str:
    slug = doc.get("slug") or ""
    if slug in _SLUG_EMOJI:
        return _SLUG_EMOJI[slug]
    for cat in doc.get("categories") or []:
        if cat in _CATEGORY_EMOJI:
            return _CATEGORY_EMOJI[cat]
    return "📋"


def _truncate(text: str, n: int) -> str:
    if not text:
        return ""
    text = text.strip()
    return text if len(text) <= n else text[:n].rstrip() + "…"


def _strip_md_quick(text: str) -> str:
    """Lightweight markdown-strip for short_summary / benefit / eligibility fields."""
    import re
    if not text:
        return ""
    t = re.sub(r"`([^`]+)`", r"\1", text)
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"\*([^*]+)\*", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"^\s*[-•\d.]+\s*", "", t, flags=re.M)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _doc_to_card(doc: dict) -> dict:
    """Map a Mongo scheme doc to the lean frontend "curated scheme" shape."""
    from backend.services.retrieval_service import _derive_apply_link, _derive_source_link
    benefit = _truncate(_strip_md_quick(doc.get("benefits_md") or ""), 140)
    eligibility = _truncate(_strip_md_quick(doc.get("eligibility_md") or ""), 140)
    summary = _truncate(doc.get("brief_description") or benefit or "", 140)
    apply_link = _derive_apply_link(doc) or ""
    source_link = _derive_source_link(doc)
    return {
        "id": doc.get("slug") or doc.get("_id"),
        "slug": doc.get("slug"),
        "name": doc.get("name") or "",
        "ministry": doc.get("ministry") or doc.get("department") or "",
        "category": (doc.get("categories") or [None])[0] or "",
        "summary": summary,
        "benefit": benefit,
        "eligibility": eligibility,
        "applyLink": apply_link,
        "sourceLink": source_link,
        "emoji": _emoji_for(doc),
        "level": doc.get("level"),
        "state": doc.get("state"),
    }


async def featured_schemes(state: str | None, limit: int = 12) -> list[dict]:
    """Return up to ``limit`` cards for the home-page grid.

    Composition:
      1. First N=5 national flagships (whichever of FLAGSHIP_SLUGS exist in Mongo).
      2. Remaining (limit - N) slots filled with schemes scoped to the user's state
         when supplied; otherwise more central schemes.
    Both lookups go through Mongo since the cards need rich text fields.
    """
    from backend.services.mongo_service import db
    coll = db().schemes
    flagships: list[dict] = []
    seen: set[str] = set()
    target_flagships = 5

    async for doc in coll.find({"slug": {"$in": FLAGSHIP_SLUGS}}):
        flagships.append(doc)
        seen.add(doc.get("slug") or "")

    # Order flagships by the slug list so the pinned order matches FLAGSHIP_SLUGS.
    by_slug = {d.get("slug"): d for d in flagships}
    flagships = [by_slug[s] for s in FLAGSHIP_SLUGS if s in by_slug][:target_flagships]
    seen = {d.get("slug") for d in flagships}

    fillers_needed = max(0, limit - len(flagships))
    fillers: list[dict] = []
    if fillers_needed > 0:
        if state:
            cursor = coll.find(
                {"level": "state", "state": state, "slug": {"$nin": list(seen)}},
            ).limit(fillers_needed)
        else:
            cursor = coll.find(
                {"level": "central", "slug": {"$nin": list(seen)}},
            ).limit(fillers_needed)
        async for doc in cursor:
            fillers.append(doc)

    cards = [_doc_to_card(d) for d in flagships + fillers]
    return cards


async def health() -> dict[str, Any]:
    """Readiness probe — does the v2 cluster respond and is Mongo reachable?"""
    out: dict[str, Any] = {"qdrant": "down", "mongo": "down", "schemes_indexed": None}
    try:
        info = _get_qclient().get_collection(V2_QDRANT_COLLECTION)
        out["qdrant"] = "up"
        out["schemes_indexed"] = info.points_count
    except Exception as e:
        logger.warning("v2_qdrant_health_failed", extra={"error": str(e)[:200]})
    try:
        from backend.services.mongo_service import db
        await db().command("ping")
        out["mongo"] = "up"
    except Exception as e:
        logger.warning("v2_mongo_health_failed", extra={"error": str(e)[:200]})
    return out
