"""Query language detection for LLM context hints."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


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



def register_hint(detected_iso: str, ui_bcp47: str) -> str:
    """Short instruction for the LLM system bundle."""
    ui = (ui_bcp47 or "hi-IN").lower()
    if detected_iso == "hi" and ui.startswith("hi"):
        return "User query may mix English words with Hindi (Hinglish). Answer in clear Hindi (Devanagari) matching TARGET_LANGUAGE."
    if detected_iso != "en" and ui.startswith("en"):
        return f"Query may be partly in language '{detected_iso}'. Keep TARGET_LANGUAGE but borrow natural terms from that register if helpful."
    return f"Detected dominant query language (ISO): {detected_iso}. Align tone and examples with TARGET_LANGUAGE while respecting that mix."
