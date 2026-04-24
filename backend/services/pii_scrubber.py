"""Lightweight PII redaction for logs/LLM safety."""

from __future__ import annotations

import re

_PATTERNS: dict[str, re.Pattern[str]] = {
    "AADHAAR": re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
    "PAN": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    "PHONE": re.compile(r"\b(?:\+91[\s-]?)?[6-9]\d{9}\b"),
    "EMAIL": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "BANK": re.compile(r"\b\d{9,18}\b"),
}


def scrub(text: str) -> tuple[str, dict[str, int]]:
    out = text or ""
    counts: dict[str, int] = {}
    for name, pat in _PATTERNS.items():
        matches = pat.findall(out)
        if matches:
            counts[name] = len(matches)
            out = pat.sub(f"[{name}_REDACTED]", out)
    return out, counts
