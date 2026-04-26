"""Language enforcement and state-filter contract tests.

Covers the two invariants that must never regress:
1. The LLM is always instructed to reply in the UI language (not the query language).
2. State extraction from natural language works for all Indian states and common
   abbreviations — ensuring the Qdrant filter always has a state to filter on even
   when `profile.state` is not sent by the client.

These are unit / integration tests — they do NOT hit external services.
"""

from __future__ import annotations

import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("ENV", "development")


# ---------------------------------------------------------------------------
# 1. State extractor — natural language → canonical state name
# ---------------------------------------------------------------------------

from backend.services.search_execution import _extract_state_from_query  # noqa: E402


@pytest.mark.parametrize(
    "query,expected",
    [
        # English — explicit "from / in"
        ("I am from Punjab, looking for schemes", "Punjab"),
        ("schemes available in Rajasthan", "Rajasthan"),
        ("I live in Tamil Nadu and need help", "Tamil Nadu"),
        ("student from West Bengal looking for scholarships", "West Bengal"),
        ("farmer in Madhya Pradesh", "Madhya Pradesh"),
        ("find me schemes in Uttar Pradesh", "Uttar Pradesh"),
        ("looking for housing help in Maharashtra", "Maharashtra"),
        ("I'm in Gujarat, 25 years old", "Gujarat"),
        ("schemes for Haryana farmers", "Haryana"),
        ("healthcare schemes for Kerala residents", "Kerala"),
        # Common abbreviations
        ("help for UP farmers", "Uttar Pradesh"),
        ("schemes in MP", "Madhya Pradesh"),
        ("I am from AP", "Andhra Pradesh"),
        ("HP state schemes", "Himachal Pradesh"),
        # Mixed Hindi + English
        ("mujhe maharashtra ki yojanaen chahiye", "Maharashtra"),
        ("Chhattisgarh mein mahila yojana", "Chhattisgarh"),
        ("rajasthan ke kisan ke liye yojana", "Rajasthan"),
        ("delhi mein student scholarship", "Delhi"),
        # Union territories
        ("I live in Delhi", "Delhi"),
        ("schemes for chandigarh residents", "Chandigarh"),
        ("Puducherry state schemes", "Puducherry"),
        ("jammu and kashmir pension scheme", "Jammu and Kashmir"),
        # Alternate spellings
        ("I'm from Orissa", "Odisha"),
        ("Uttaranchal schemes", "Uttarakhand"),
        ("Pondicherry residents", "Puducherry"),
        ("Chattisgarh women scheme", "Chhattisgarh"),
        # Numeric / age in query (regression guard)
        ("I am 24 yrs old from punjab. find me schemes", "Punjab"),
        ("25 year old from Karnataka needs help", "Karnataka"),
        # No state — must return None
        ("find me schemes for farmers", None),
        ("what is PM Kisan", None),
        ("show me all schemes", None),
    ],
)
def test_extract_state_from_query(query: str, expected: str | None) -> None:
    assert _extract_state_from_query(query) == expected


# ---------------------------------------------------------------------------
# 2. Language rule is first in system prompt and names the language in English
# ---------------------------------------------------------------------------

from backend.services.llm_service import build_messages  # noqa: E402


@pytest.mark.parametrize(
    "lang_code,lang_name",
    [
        ("hi-IN", "Hindi"),
        ("mr-IN", "Marathi"),
        ("gu-IN", "Gujarati"),
        ("kn-IN", "Kannada"),
        ("ta-IN", "Tamil"),
        ("te-IN", "Telugu"),
        ("ml-IN", "Malayalam"),
        ("bn-IN", "Bengali"),
        ("en-IN", "English"),
        ("pa-IN", "Punjabi"),
    ],
)
def test_language_rule_is_first_and_names_language(lang_code: str, lang_name: str) -> None:
    msgs = build_messages("test query", "context", [], lang_code)
    system_content: str = msgs[0]["content"]
    lines = system_content.splitlines()
    # The very first line must be the CRITICAL rule header.
    assert lines[0].startswith("CRITICAL"), (
        f"First line of system prompt is not the CRITICAL language rule for {lang_code}:\n{lines[0]!r}"
    )
    # The human-readable language name must appear in the first 5 lines.
    header = "\n".join(lines[:5])
    assert lang_name in header, (
        f"Language name {lang_name!r} not found in first 5 lines for {lang_code}:\n{header}"
    )


@pytest.mark.parametrize("lang_code", ["hi-IN", "mr-IN", "ta-IN", "kn-IN", "en-IN"])
def test_language_rule_prohibits_english_fallback(lang_code: str) -> None:
    msgs = build_messages("test query", "context", [], lang_code)
    system_content: str = msgs[0]["content"]
    assert "do not fall back to English" in system_content.lower() or \
           "never switch to english" in system_content.lower(), (
        f"System prompt for {lang_code} does not explicitly prohibit English fallback"
    )


@pytest.mark.parametrize("lang_code", ["hi-IN", "mr-IN", "ta-IN"])
def test_language_rule_appears_before_absolute_rules(lang_code: str) -> None:
    msgs = build_messages("test query", "context", [], lang_code)
    system_content: str = msgs[0]["content"]
    critical_pos = system_content.find("CRITICAL")
    absolute_pos = system_content.find("ABSOLUTE RULES")
    assert critical_pos < absolute_pos, (
        f"CRITICAL language rule ({critical_pos}) does not appear before ABSOLUTE RULES "
        f"({absolute_pos}) for {lang_code}"
    )


# ---------------------------------------------------------------------------
# 3. State filter — profile.state takes precedence; query extraction is fallback
# ---------------------------------------------------------------------------

from backend.services.search_execution import _user_state_from_profile  # noqa: E402


def test_profile_state_takes_precedence_over_query():
    profile = {"state": "Karnataka"}
    state = _user_state_from_profile(profile) or _extract_state_from_query("I'm from Punjab")
    assert state == "Karnataka", "profile.state must win over query extraction"


def test_query_extraction_used_when_profile_empty():
    profile: dict = {}
    state = _user_state_from_profile(profile) or _extract_state_from_query("schemes for farmers in Punjab")
    assert state == "Punjab"


def test_query_extraction_used_when_profile_none():
    state = _user_state_from_profile({}) or _extract_state_from_query("I live in Rajasthan")
    assert state == "Rajasthan"


def test_no_state_when_neither_profile_nor_query():
    state = _user_state_from_profile({}) or _extract_state_from_query("show me all schemes")
    assert state is None


# ---------------------------------------------------------------------------
# 4. Grounding service — cross-language (Indic) claims skip token overlap
# ---------------------------------------------------------------------------

from backend.services.grounding_service import _is_indic  # noqa: E402


@pytest.mark.parametrize(
    "text,expected",
    [
        # Clearly Hindi
        ("मनरेगा के तहत साल में 100 दिन काम मिलता है", True),
        ("पीएम आवास योजना में लाभार्थी को सब्सिडी मिलती है", True),
        # Clearly English
        ("MGNREGA provides 100 days of work per year", False),
        ("PM Awas Yojana gives housing subsidy to beneficiaries", False),
        # Mixed Hinglish — less than 25% Indic words → False
        ("MGNREGA ke tahat 100 din ka kaam milta hai", False),
        # Tamil
        ("மனரேகா திட்டத்தின் கீழ் ஆண்டுக்கு 100 நாட்கள் வேலை", True),
    ],
)
def test_is_indic(text: str, expected: bool) -> None:
    assert _is_indic(text) == expected
