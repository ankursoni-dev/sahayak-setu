"""Query language detection + light Hinglish → Hindi token hints for retrieval and LLM."""

from __future__ import annotations

import logging
import re
from typing import Final

logger = logging.getLogger(__name__)

# Common Roman tokens in Indian welfare chat → Devanagari (retrieval + LLM register).
_HINGLISH_TOKEN_MAP: Final[tuple[tuple[str, str], ...]] = (
    (" yojana ", " योजना "),
    (" yojna ", " योजना "),
    (" loan ", " लोन "),
    (" mahila ", " महिला "),
    (" mahilao ", " महिलाओं "),
    (" sarkari ", " सरकारी "),
    (" sarkar ", " सरकार "),
    (" paisa ", " पैसा "),
    (" labh ", " लाभ "),
    (" kisan ", " किसान "),
    (" kisanon ", " किसानों "),
    (" aavedan ", " आवेदन "),
    (" darj ", " दर्ज "),
    (" suchna ", " सूचना "),
    (" yogyata ", " योग्यता "),
    (" yogy ", " योग्य "),
    (" dastavez ", " दस्तावेज़ "),
    (" dastavej ", " दस्तावेज़ "),
    (" mgnrega ", " मनरेगा "),
    (" mnrega ", " मनरेगा "),
    (" nrega ", " मनरेगा "),
    (" pm kisan ", " पीएम किसान "),
    (" pm-kisan ", " पीएम किसान "),
    (" pmkisan ", " पीएम किसान "),
)


def normalize_hinglish(text: str) -> str:
    """Replace frequent Roman welfare terms so retrieval / rewrite see Hindi forms too."""
    if not text:
        return ""
    padded = f" {text.lower()} "
    for roman, hindi in _HINGLISH_TOKEN_MAP:
        if roman in padded:
            padded = padded.replace(roman, hindi)
    return padded.strip()


def _devanagari_ratio(text: str) -> float:
    if not text:
        return 0.0
    dev = sum(1 for ch in text if "\u0900" <= ch <= "\u097f")
    letters = sum(1 for ch in text if ch.isalpha() or ("\u0900" <= ch <= "\u097f"))
    return (dev / letters) if letters else 0.0


def detect_language_code(text: str) -> str:
    """ISO 639-1 best guess; falls back to script heuristics."""
    sample = (text or "").strip()
    if len(sample) < 3:
        return "en"
    if _devanagari_ratio(sample) > 0.35:
        return "hi"
    try:
        from langdetect import detect

        code = detect(sample)
        if code and len(code) >= 2:
            return code[:2].lower()
    except Exception as e:
        logger.debug("langdetect_skipped", extra={"error": str(e)[:80]})
    return "en"


_LATIN_NAMED_SCHEMES = re.compile(
    r"\b(?:mgnrega|mnrega|nrega|pm[-\s]?kisan|pmkisan|pm[-\s]?kisan\s+samman)\b",
    re.I,
)
_DEVANAGARI_NAMED_SCHEMES = re.compile(
    r"(?:मनरेगा|पीएम\s*किसान|किसान\s*सम्मान|किसान\s*निधि|प्रधानमंत्री\s*किसान)",
)


def prefer_original_for_retrieval(original: str, normalized: str) -> bool:
    """
    When true, skip Gemini query-rewrite for retrieval and embed the user's own wording.

    Short Hindi / Devanagari queries were being rewritten into generic English, which
    skewed vector search away from schemes like MGNREGA / PM-KISAN (English catalog).
    """
    o = (original or "").strip()
    n = (normalized or "").strip()
    blob = f"{o}\n{n}"
    if _devanagari_ratio(o) >= 0.12:
        return True
    if _LATIN_NAMED_SCHEMES.search(blob):
        return True
    if _DEVANAGARI_NAMED_SCHEMES.search(blob):
        return True
    return False


def register_hint(detected_iso: str, ui_bcp47: str) -> str:
    """Short instruction for the LLM system bundle."""
    ui = (ui_bcp47 or "hi-IN").lower()
    if detected_iso == "hi" and ui.startswith("hi"):
        return "User query may mix English words with Hindi (Hinglish). Answer in clear Hindi (Devanagari) matching TARGET_LANGUAGE."
    if detected_iso != "en" and ui.startswith("en"):
        return f"Query may be partly in language '{detected_iso}'. Keep TARGET_LANGUAGE but borrow natural terms from that register if helpful."
    return f"Detected dominant query language (ISO): {detected_iso}. Align tone and examples with TARGET_LANGUAGE while respecting that mix."
