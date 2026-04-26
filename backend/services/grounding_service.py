"""Deterministic post-LLM grounding verification."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from typing import Iterable

from fastembed import TextEmbedding
from pydantic import BaseModel, ValidationError

from backend.services.retrieval_service import SearchResult

EMBED_SIM_MIN = 0.60
EMBED_SIM_MIN_CROSS_LANG = 0.42  # bge-small-en-v1.5 scores cross-lingual pairs lower
TOKEN_OVERLAP_MIN = 0.30
CLAIM_DROP_LIMIT = 0.50
MIN_ANSWER_CHARS = 30


class Claim(BaseModel):
    text: str
    source_id: str
    span: str = ""


class LLMOutput(BaseModel):
    status: str
    answer: str | None = None
    claims: list[Claim] = []
    next_step: str | None = None
    why_it_fits: list[str] = []
    near_miss: str | None = None


@dataclass
class VerificationResult:
    status: str
    answer: str | None
    verified_claims: list[Claim]
    dropped_claims: list[tuple[Claim, str]]
    next_step: str | None
    why_it_fits: list[str]
    near_miss: str | None


_WORD_RE = re.compile(r"[A-Za-z\u0900-\u097F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0980-\u09FF]+")
_STOPWORDS = {"the", "a", "an", "is", "are", "of", "to", "for", "in", "and", "or", "hai", "ke", "ki", "ka", "ko", "se", "me"}
_NUMBER_RE = re.compile(r"\b\d[\d,./-]*\b")
_URL_RE = re.compile(r"https?://\S+")
_DATE_RE = re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4})\b")
# Detects Indic-script text (Devanagari, Tamil, Telugu, Kannada, Bengali, Gujarati, Gurmukhi).
# Source documents are English-only; token overlap against an Indic claim is always 0 —
# meaningless cross-language comparison, so we skip it and rely on embedding similarity.
_INDIC_SCRIPT_RE = re.compile(r"[ऀ-ॿ஀-௿ఀ-౿ಀ-೿ঀ-৿઀-૿਀-੿]")

# Lazy-load the embedder on first use so startup is not blocked by a model download.
# The lock guards against two concurrent requests each kicking off the (slow, ~50MB)
# model download — without it, both threads see _EMBEDDER is None and race.
_EMBEDDER: TextEmbedding | None = None
_EMBEDDER_LOCK = threading.Lock()


def _get_embedder() -> TextEmbedding:
    global _EMBEDDER
    if _EMBEDDER is not None:
        return _EMBEDDER
    with _EMBEDDER_LOCK:
        if _EMBEDDER is None:
            _EMBEDDER = TextEmbedding("BAAI/bge-small-en-v1.5")
    return _EMBEDDER


def _tokens(text: str) -> set[str]:
    return {
        t.lower()
        for t in _WORD_RE.findall(text or "")
        if t.lower() not in _STOPWORDS and len(t) > 2
    }


def _token_overlap(claim: str, source: str) -> float:
    claim_tokens = _tokens(claim)
    if not claim_tokens:
        return 0.0
    src_tokens = _tokens(source)
    return len(claim_tokens & src_tokens) / len(claim_tokens)


def _is_indic(text: str) -> bool:
    """True when the claim is predominantly in an Indic script (Hindi, Tamil, etc.).
    Token overlap against English-only source docs is always ~0 for these claims,
    making the check a false negative — skip it and rely on embedding similarity instead."""
    words = re.findall(r"\w+", text or "")
    if not words:
        return False
    indic = sum(1 for w in words if _INDIC_SCRIPT_RE.search(w))
    return indic / len(words) >= 0.25


def _embed(text: str) -> list[float]:
    return list(next(_get_embedder().embed([text])))


def _cosine(a: Iterable[float], b: Iterable[float]) -> float:
    va, vb = list(a), list(b)
    dot = sum(x * y for x, y in zip(va, vb))
    na = sum(x * x for x in va) ** 0.5
    nb = sum(x * x for x in vb) ** 0.5
    return dot / (na * nb + 1e-9)


def _numbers_dates_urls_grounded(claim: str, source: str) -> tuple[bool, str]:
    for num in _NUMBER_RE.findall(claim):
        if num not in source:
            return False, f"number_not_in_source:{num}"
    for dt in _DATE_RE.findall(claim):
        if dt not in source:
            return False, f"date_not_in_source:{dt}"
    for url in _URL_RE.findall(claim):
        if url not in source:
            return False, f"url_not_in_source:{url}"
    return True, ""


def _source_map(sources: list[SearchResult]) -> dict[str, SearchResult]:
    return {f"S{i+1}": src for i, src in enumerate(sources)}


_FALLBACK_BY_LANG = {
    "hi": "मेरे पास इस बारे में सत्यापित जानकारी नहीं है। कृपया आधिकारिक पोर्टल देखें या निकटतम CSC जाएं।",
    "mr": "माझ्याकडे याबद्दल सत्यापित माहिती नाही. कृपया अधिकृत पोर्टल पहा किंवा जवळच्या CSC ला भेट द्या.",
    "gu": "મારી પાસે આ વિશે ચકાસાયેલ માહિતી નથી. કૃપા કરીને અધિકૃત પોર્ટલ તપાસો અથવા નજીકના CSC ની મુલાકાત લો.",
    "kn": "ಈ ಬಗ್ಗೆ ನನ್ನ ಬಳಿ ದೃಢೀಕೃತ ಮಾಹಿತಿ ಇಲ್ಲ. ದಯವಿಟ್ಟು ಅಧಿಕೃತ ಪೋರ್ಟಲ್ ಪರಿಶೀಲಿಸಿ ಅಥವಾ ಹತ್ತಿರದ CSC ಗೆ ಭೇಟಿ ನೀಡಿ.",
    "ta": "இதைப் பற்றி என்னிடம் சரிபார்க்கப்பட்ட தகவல் இல்லை. அதிகாரப்பூர்வ போர்ட்டலைப் பார்க்கவும் அல்லது அருகிலுள்ள CSC-க்குச் செல்லவும்.",
    "te": "దీని గురించి నా వద్ద ధృవీకరించబడిన సమాచారం లేదు. దయచేసి అధికారిక పోర్టల్‌ను చూడండి లేదా సమీప CSCని సందర్శించండి.",
    "ml": "ഇതിനെക്കുറിച്ച് എന്റെ പക്കൽ സ്ഥിരീകരിച്ച വിവരങ്ങളില്ല. ദയവായി ഔദ്യോഗിക പോർട്ടൽ പരിശോധിക്കുക അല്ലെങ്കിൽ അടുത്തുള്ള CSC സന്ദർശിക്കുക.",
    "bn": "এ বিষয়ে আমার কাছে যাচাইকৃত তথ্য নেই। অনুগ্রহ করে অফিসিয়াল পোর্টাল দেখুন বা নিকটবর্তী CSC-তে যান।",
}


def fallback_text_for_language(language: str) -> str:
    lang = (language or "").lower().split("-")[0]
    return _FALLBACK_BY_LANG.get(lang) or (
        "I don't have verified information on this. Please check the official portal or visit your nearest CSC."
    )


def verify(raw_llm_output: dict, sources: list[SearchResult], fallback_message: str) -> VerificationResult:
    try:
        parsed = LLMOutput.model_validate(raw_llm_output)
    except ValidationError:
        return VerificationResult("insufficient", fallback_message, [], [], None, [], None)

    if parsed.status != "ok" or not parsed.answer or not parsed.claims:
        return VerificationResult("insufficient", fallback_message, [], [], None, [], None)

    source_map = _source_map(sources)
    verified: list[Claim] = []
    dropped: list[tuple[Claim, str]] = []

    source_embeds = {sid: _embed(src.document or "") for sid, src in source_map.items()}

    for claim in parsed.claims:
        src = source_map.get(claim.source_id)
        if not src:
            dropped.append((claim, "bad_source_id"))
            continue

        ok_num, reason = _numbers_dates_urls_grounded(claim.text, src.document or "")
        if not ok_num:
            dropped.append((claim, reason))
            continue

        cross_lang = _is_indic(claim.text)
        if not cross_lang:
            # Token overlap is only meaningful when claim and source share the same script.
            overlap = _token_overlap(claim.text, src.document or "")
            if overlap < TOKEN_OVERLAP_MIN:
                dropped.append((claim, f"token_overlap_{overlap:.2f}"))
                continue

        sim = _cosine(_embed(claim.text), source_embeds[claim.source_id])
        # bge-small-en-v1.5 is English-focused; cross-lingual pairs score lower.
        sim_threshold = EMBED_SIM_MIN_CROSS_LANG if cross_lang else EMBED_SIM_MIN
        if sim < sim_threshold:
            dropped.append((claim, f"embed_sim_{sim:.2f}"))
            continue

        verified.append(claim)

    drop_ratio = len(dropped) / len(parsed.claims) if parsed.claims else 1.0
    if drop_ratio > CLAIM_DROP_LIMIT or not verified:
        return VerificationResult("insufficient", fallback_message, [], dropped, None, [], None)

    answer = parsed.answer
    for claim, _reason in dropped:
        answer = answer.replace(claim.text, "")
    answer = re.sub(r"\s+", " ", answer).strip()
    if len(answer) < MIN_ANSWER_CHARS:
        return VerificationResult("insufficient", fallback_message, [], dropped, None, [], None)

    status = "partial" if dropped else "ok"
    return VerificationResult(
        status,
        answer,
        verified,
        dropped,
        parsed.next_step,
        parsed.why_it_fits,
        parsed.near_miss,
    )
