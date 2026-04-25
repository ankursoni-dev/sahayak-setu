"""Qdrant retrieval — single responsibility for vector search."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from backend.config import (
    HYBRID_KEYWORD_WEIGHT,
    NEAR_MISS_MAX,
    NEAR_MISS_SCORE_FLOOR,
    QDRANT_COLLECTION,
    RAG_VECTOR_CANDIDATE_LIMIT,
    RAG_VECTOR_QUERY_LIMIT,
    qdrant_client,
)
from backend.services.injection_guard import wrap_retrieved_chunk

logger = logging.getLogger(__name__)
_CATALOG_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data" / "schemes.json"
_CATALOG_CACHE: list[dict] | None = None


@dataclass
class SearchResult:
    scheme_name: str
    document: str
    score: float
    apply_link: str | None = None
    source: str | None = None
    source_id: str | None = None
    vector_score: float = 0.0
    keyword_score: float = 0.0
    blended_score: float = 0.0
    last_verified_at: str | None = None
    # "all" for nationwide central schemes, list[str] of state names for state-specific,
    # None when unknown. Frontend renders a corresponding pill on each scheme card.
    state_availability: str | list[str] | None = None
    # Tokens that overlapped between the user query and this chunk — drives the
    # qualitative "Why this match" explainer (F7) without exposing raw similarity scores.
    matched_terms: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.matched_terms is None:
            self.matched_terms = []


def search_schemes(query: str, limit: int = 3) -> list[SearchResult]:
    try:
        raw_results = qdrant_client.query(
            collection_name=QDRANT_COLLECTION,
            query_text=query,
            limit=limit,
        )
        if raw_results:
            return [
                SearchResult(
                    scheme_name=result.metadata.get("scheme", "Scheme"),
                    document=result.document,
                    score=result.score,
                    apply_link=result.metadata.get("apply_link"),
                    source=result.metadata.get("source"),
                    vector_score=float(result.score),
                    keyword_score=0.0,
                    blended_score=float(result.score),
                    last_verified_at=result.metadata.get("last_verified_at"),
                    state_availability=result.metadata.get("state_availability"),
                    matched_terms=_matched_terms(query, result.document or "", scheme=result.metadata.get("scheme", "")),
                )
                for result in raw_results
            ]
        logger.info(
            "qdrant_vector_empty",
            extra={"query_prefix": (query or "")[:160], "collection": QDRANT_COLLECTION},
        )
    except Exception:
        logger.warning("qdrant_query_failed_falling_back_to_catalog", exc_info=True)
    return _catalog_keyword_search(query, limit)


def filter_by_threshold(results: list[SearchResult], threshold: float) -> list[SearchResult]:
    return [result for result in results if result.score > threshold]


def _query_tokens(text: str) -> set[str]:
    # Language-agnostic-ish tokenization: keep unicode word chars, strip tiny tokens.
    toks = re.findall(r"\w+", (text or "").lower(), flags=re.UNICODE)
    return {t for t in toks if len(t) > 2}


def _keyword_overlap_score(query: str, document: str) -> float:
    q = _query_tokens(query)
    if not q:
        return 0.0
    d = _query_tokens(document)
    if not d:
        return 0.0
    score = len(q & d) / (len(q) + 1e-5)
    q_text = (query or "").strip().lower()
    d_text = (document or "").lower()
    if q_text and q_text in d_text:
        score += 0.2
    return max(0.0, min(1.0, score))


def _load_catalog() -> list[dict]:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None:
        return _CATALOG_CACHE
    try:
        rows = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
        if isinstance(rows, list):
            _CATALOG_CACHE = [r for r in rows if isinstance(r, dict)]
        else:
            _CATALOG_CACHE = []
    except Exception:
        logger.warning("local_catalog_load_failed", exc_info=True)
        _CATALOG_CACHE = []
    return _CATALOG_CACHE


def _catalog_keyword_search(query: str, limit: int) -> list[SearchResult]:
    rows = _load_catalog()
    if not rows:
        return []
    scored: list[SearchResult] = []
    for row in rows:
        text = str(row.get("text") or "")
        meta = row.get("metadata") or {}
        scheme = str(meta.get("scheme") or "Scheme")
        score = _keyword_overlap_score(query, f"{scheme} {text}")
        scored.append(
            SearchResult(
                scheme_name=scheme,
                document=text,
                score=score,
                apply_link=meta.get("apply_link"),
                source=meta.get("source"),
                vector_score=0.0,
                keyword_score=score,
                blended_score=score,
                last_verified_at=meta.get("last_verified_at"),
                state_availability=meta.get("state_availability"),
                matched_terms=_matched_terms(query, text, scheme=scheme),
            )
        )
    scored.sort(key=lambda x: x.score, reverse=True)
    return _dedupe_by_scheme(scored)[:limit]


# Stop tokens for the "matched_terms" explainer — drop fillers so users see signal words.
_EXPLAIN_STOP = {
    "the", "and", "for", "with", "from", "this", "that", "what", "which", "have", "has",
    "are", "is", "of", "to", "in", "a", "an", "or", "be", "i", "me", "my", "we", "you",
    "your", "tell", "about", "how", "can", "do", "does", "show", "find", "get", "give",
    "want", "need", "scheme", "schemes", "yojana", "yojna", "please", "kindly",
}


def _matched_terms(query: str, document: str, *, scheme: str = "") -> list[str]:
    """Pick a few qualitative tokens that overlap query and document — used for the
    public 'Why this match' explainer. Bounded to 4 items so the UI can render inline."""
    q_tokens = [t for t in _query_tokens(query) if t not in _EXPLAIN_STOP]
    if not q_tokens:
        return []
    d_tokens = _query_tokens(document) | _query_tokens(scheme)
    if not d_tokens:
        return []
    seen: set[str] = set()
    matches: list[str] = []
    for t in q_tokens:
        if t in d_tokens and t not in seen:
            seen.add(t)
            matches.append(t)
        if len(matches) >= 4:
            break
    return matches


def matched_terms_for_query(query: str, document: str, scheme: str = "") -> list[str]:
    """Public re-export so search_execution can recompute when stitching responses."""
    return _matched_terms(query, document, scheme=scheme)


def _normalize(scores: list[float]) -> list[float]:
    if not scores:
        return []
    min_s = min(scores)
    max_s = max(scores)
    if max_s - min_s == 0:
        return [0.5 for _ in scores]
    return [(s - min_s) / (max_s - min_s) for s in scores]


def _hybrid_weight_for_query(query: str, base_weight: float) -> float:
    tokens = (query or "").split()
    query_weight = 0.25
    if len(tokens) <= 3:
        query_weight = 0.5
    elif any(ch.isdigit() for ch in (query or "")):
        query_weight = 0.4
    # Blend operator tune and query-adaptive heuristic.
    return max(0.0, min(1.0, (max(0.0, min(1.0, base_weight)) + query_weight) / 2.0))


def _scheme_match_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


_CATALOG_BOOST_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?:\b(?:mgnrega|mnrega|nrega)\b|मनरेगा)", re.I), "mgnrega"),
    (
        re.compile(
            r"\bpm[-\s]?kisan\b|pmkisan|pm[-\s]?kisan\s+samman|"
            r"पीएम\s*किसान|किसान\s*सम्मान|किसान\s*निधि|प्रधानमंत्री\s*किसान",
            re.I,
        ),
        "pmkisan",
    ),
    (re.compile(r"\bayushman\b|pmjay|pm[-\s]?jay|आयुष्मान", re.I), "ayushman bharat"),
    (re.compile(r"\bujjwala\b|lpg\s+yojana|उज्ज्वला", re.I), "ujjwala yojana"),
    (re.compile(r"\bmudra\b|pmmy|pm\s*mudra", re.I), "pm mudra yojana"),
    (re.compile(r"\bsvanidhi\b|svAnidhi|street\s*vendor\s*loan", re.I), "pm svanidhi"),
    (re.compile(r"\bvishwakarma\b|pm\s*vishwakarma|विश्वकर्मा", re.I), "pm vishwakarma"),
    (re.compile(r"\bjan\s*dhan\b|pmjdy|जन\s*धन", re.I), "pm jan dhan yojana"),
)


def _catalog_search_result_for_slug(slug: str) -> SearchResult | None:
    """Return a catalog row as SearchResult; slug is normalized like 'mgnrega' or 'pmkisan'."""
    for row in _load_catalog():
        meta = row.get("metadata") or {}
        scheme = str(meta.get("scheme") or "")
        if _scheme_match_key(scheme) != slug:
            continue
        text = str(row.get("text") or "")
        return SearchResult(
            scheme_name=scheme,
            document=text,
            score=0.78,
            apply_link=meta.get("apply_link"),
            source=meta.get("source"),
            vector_score=0.78,
            keyword_score=0.78,
            blended_score=0.78,
            last_verified_at=meta.get("last_verified_at"),
            state_availability=meta.get("state_availability"),
            # matched_terms is intentionally left empty here — the slug-based catalog
            # boost path doesn't have the user's original query in scope, so we'd be
            # guessing. The hybrid rerank step (when enabled) recomputes it; otherwise
            # the explainer pill simply doesn't render for these spliced results.
        )
    return None


def merge_explicit_catalog_hits(query: str, raw_results: list[SearchResult]) -> list[SearchResult]:
    """
    If the user names a flagship scheme but vector search missed it, splice the local
    catalogue row in with a strong score so RAG + grounding can cite real text.
    """
    merged = list(raw_results or [])
    if not (query or "").strip():
        return merged
    keys = {_scheme_match_key(r.scheme_name) for r in merged}
    for pattern, slug in _CATALOG_BOOST_RULES:
        if not pattern.search(query):
            continue
        if slug in keys:
            continue
        hit = _catalog_search_result_for_slug(slug)
        if hit:
            merged.append(hit)
            keys.add(slug)
    merged.sort(key=lambda r: float(r.score or 0.0), reverse=True)
    return merged


def _dedupe_by_scheme(results: list[SearchResult]) -> list[SearchResult]:
    seen: set[str] = set()
    deduped: list[SearchResult] = []
    for r in results:
        key = (r.scheme_name or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped


def _hybrid_rerank(query: str, results: list[SearchResult]) -> list[SearchResult]:
    """
    Lightweight rerank: blend vector score with keyword overlap.
    score = (1-w)*vector + w*keyword, where w defaults to 0.3.
    """
    if not results:
        return []
    weight = _hybrid_weight_for_query(query, HYBRID_KEYWORD_WEIGHT)
    vector_raw = [float(r.vector_score or r.score) for r in results]
    keyword_raw = [_keyword_overlap_score(query, r.document or "") for r in results]
    vector_norm = _normalize(vector_raw)
    keyword_norm = _normalize(keyword_raw)

    reranked: list[SearchResult] = []
    for i, r in enumerate(results):
        blended = ((1.0 - weight) * vector_norm[i]) + (weight * keyword_norm[i])
        reranked.append(
            SearchResult(
                scheme_name=r.scheme_name,
                document=r.document,
                score=blended,
                apply_link=r.apply_link,
                source=r.source,
                source_id=r.source_id,
                vector_score=vector_norm[i],
                keyword_score=keyword_norm[i],
                blended_score=blended,
                # Preserve metadata-derived fields (F4 freshness, F6 state availability)
                # and the per-query explainer tokens (F7) — without these the rerank
                # silently strips everything downstream depends on.
                last_verified_at=r.last_verified_at,
                state_availability=r.state_availability,
                matched_terms=list(r.matched_terms or []),
            )
        )
    reranked.sort(key=lambda x: x.score, reverse=True)
    return _dedupe_by_scheme(reranked)


def confidence_label_for_score(score: float) -> str:
    """Human-readable retrieval confidence (vector similarity — not legal eligibility proof)."""
    if score > 0.7:
        return "Strong match (based on available data)"
    if score > 0.4:
        return "Moderate match"
    return "Low confidence"


def cta_label_for_score(score: float) -> str:
    """Primary action on official portal link — stronger CTA only when retrieval is confident."""
    return "Apply Now" if score > 0.7 else "Check Eligibility"


def _result_key(result: SearchResult) -> tuple[str, str]:
    return (result.scheme_name, result.document)


_SYNONYM_MAP: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bpmkisan\b|pm[-\s]kisan\b", re.I), "PM Kisan Samman Nidhi"),
    (re.compile(r"\bmgnrega\b|\bnrega\b", re.I), "Mahatma Gandhi Rural Employment Guarantee"),
    (re.compile(r"\bayushman\b|\bpmjay\b", re.I), "Ayushman Bharat PM-JAY health insurance"),
    (re.compile(r"\bujjwala\b", re.I), "Ujjwala Yojana LPG connection women BPL"),
    (re.compile(r"\bmudra\b|\bpmmy\b", re.I), "MUDRA Micro Units Development Refinance Agency loan"),
    (re.compile(r"\bsvanidhi\b", re.I), "PM SVANidhi street vendor working capital loan"),
    (re.compile(r"\bvishwakarma\b", re.I), "PM Vishwakarma artisan craftsperson traditional trade"),
    (re.compile(r"\bjan\s*dhan\b", re.I), "Jan Dhan PMJDY zero-balance bank account"),
)


def _expand_query_synonyms(query: str) -> str:
    """Append canonical English terms for scheme abbreviations/Hindi names to improve recall."""
    extras: list[str] = []
    for pattern, expansion in _SYNONYM_MAP:
        if pattern.search(query) and expansion.lower() not in query.lower():
            extras.append(expansion)
    if not extras:
        return query
    return f"{query} {' '.join(extras)}"


def retrieve_for_rag(
    query: str,
    similarity_threshold: float,
    *,
    use_hybrid: bool = False,
    boost_query: str | None = None,
) -> tuple[list[SearchResult], list[SearchResult], str, str]:
    """
    Top confident matches (up to 3) plus up to two additional high-ranked hits
    for near-miss / gap analysis (not above threshold or not in top-3 set).
    """
    candidate_limit = RAG_VECTOR_CANDIDATE_LIMIT if use_hybrid else RAG_VECTOR_QUERY_LIMIT
    expanded_query = _expand_query_synonyms(query)
    raw_results = search_schemes(expanded_query, limit=candidate_limit)
    boost_blob = f"{query}\n{boost_query or ''}"
    raw_results = merge_explicit_catalog_hits(boost_blob, raw_results)
    if use_hybrid:
        raw_results = _hybrid_rerank(query, raw_results)
    else:
        raw_results = _dedupe_by_scheme(raw_results)
    relevant_results = filter_by_threshold(raw_results, similarity_threshold)[:4]
    rel_keys = {_result_key(r) for r in relevant_results}

    near_miss_results: list[SearchResult] = []
    for result in raw_results:
        if _result_key(result) in rel_keys:
            continue
        if result.score < NEAR_MISS_SCORE_FLOOR:
            continue
        near_miss_results.append(result)
        if len(near_miss_results) >= NEAR_MISS_MAX:
            break

    for i, result in enumerate(relevant_results, start=1):
        result.source_id = f"S{i}"
    for i, result in enumerate(near_miss_results, start=1):
        result.source_id = f"N{i}"

    context = build_context_from_results(relevant_results)
    if near_miss_results:
        near_header = (
            "Lower-confidence retrieval matches (possible near-misses — compare user profile "
            "to eligibility; mention only real gaps, do not invent rules):\n\n"
        )
        near_context = near_header + build_context_from_results(near_miss_results)
    else:
        near_context = ""

    return relevant_results, near_miss_results, context, near_context


def build_retrieval_debug(query: str, results: list[SearchResult]) -> dict:
    return {
        "query": query,
        "top_results": [
            {
                "scheme": r.scheme_name,
                "vector": round(float(r.vector_score or 0.0), 4),
                "keyword": round(float(r.keyword_score or 0.0), 4),
                "blended": round(float(r.blended_score or r.score), 4),
                "final_score": round(float(r.score), 4),
            }
            for r in results[:5]
        ],
    }


def truncate_at_word_boundary(text: str, max_len: int) -> str:
    """Prefer ending on a full word when truncating (avoids 'elig…' mid-token)."""
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rstrip()
    if " " in cut:
        head = cut.rsplit(" ", 1)[0]
        base = head if head else cut
    else:
        base = cut
    # Drop trailing sentence punctuation so we never produce "farmers.…"
    base = re.sub(r"[.,;:]\s*$", "", base).rstrip()
    if not base:
        return "…"
    return base + "…"


def preview_snippet_from_document(document: str, max_len: int = 140) -> str:
    """One-line snippet for UI tooltips (not legal advice)."""
    snippet = (document or "").replace("\n", " ").strip()
    snippet = re.sub(r"\s+([.,;:])", r"\1", snippet)
    return truncate_at_word_boundary(snippet, max_len)


def format_citation_index(results: list[SearchResult]) -> str:
    """Numbered lines for in-answer [1], [2] citations — order must match API `sources`."""
    if not results:
        return ""
    lines: list[str] = []
    for i, result in enumerate(results, start=1):
        snippet = (result.document or "").replace("\n", " ").strip()
        snippet = re.sub(r"\s+([.,;:])", r"\1", snippet)
        snippet = truncate_at_word_boundary(snippet, 180)
        lines.append(f"[{i}] {result.scheme_name}: {snippet}")
    return "\n".join(lines)


def format_source_index(results: list[SearchResult]) -> str:
    """Strict source tags for anti-hallucination JSON contracts."""
    if not results:
        return ""
    lines: list[str] = []
    for i, result in enumerate(results, start=1):
        sid = result.source_id or f"S{i}"
        snippet = (result.document or "").replace("\n", " ").strip()
        snippet = re.sub(r"\s+([.,;:])", r"\1", snippet)
        snippet = truncate_at_word_boundary(snippet, 220)
        lines.append(f"[{sid}] {result.scheme_name}: {snippet}")
    return "\n".join(lines)


def build_context_from_results(results: list[SearchResult]) -> str:
    """RAG context text including verified URLs from metadata (never LLM-invented)."""
    parts: list[str] = []
    for i, result in enumerate(results, start=1):
        sid = result.source_id or f"S{i}"
        chunk = wrap_retrieved_chunk(result.document)
        extras: list[str] = []
        if result.apply_link:
            extras.append(f"Official apply / learn more: {result.apply_link}")
        if result.source:
            extras.append(f"Scheme catalogue (MyScheme / reference): {result.source}")
        extras.append("Freshness date: unknown")
        if extras:
            chunk = f"{chunk}\n" + "\n".join(extras)
        parts.append(f"[{sid}]\n{chunk}")
    return "\n\n".join(parts)
