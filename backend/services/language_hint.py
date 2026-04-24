"""Lightweight script hints for BCP-47 tags (moderation / defaults)."""

from __future__ import annotations

import re

# Order: Devanagari and major Indic scripts before Latin default.
_SCRIPT_LANG: list[tuple[str, re.Pattern[str]]] = [
    ("hi-IN", re.compile(r"[\u0900-\u097F]")),
    ("kn-IN", re.compile(r"[\u0C80-\u0CFF]")),
    ("te-IN", re.compile(r"[\u0C00-\u0C7F]")),
    ("ta-IN", re.compile(r"[\u0B80-\u0BFF]")),
    ("bn-IN", re.compile(r"[\u0980-\u09FF]")),
]


def infer_bcp47(text: str) -> str:
    """Best-effort locale from visible script; aligns with web client speech heuristics."""
    if not text or not text.strip():
        return "hi-IN"
    for lang, pat in _SCRIPT_LANG:
        if pat.search(text):
            return lang
    return "en-IN"
