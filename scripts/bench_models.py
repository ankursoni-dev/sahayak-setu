"""Benchmark multilingual LLM behavior on the welfare-scheme RAG task.

Tests each candidate model with the SAME system prompt and source context, varying
input language ↔ target output language. Measures latency, language correctness,
and structural compliance (no markdown, no [Sn] citations, plain prose).

Run: .venv/bin/python3 scripts/bench_models.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Read OPENROUTER_API_KEY from .env
env_text = (ROOT / ".env").read_text()
API_KEY = re.search(r"OPENROUTER_API_KEY=([^\n]+)", env_text).group(1).strip()


# ---------- Models to compare ---------------------------------------------------
MODELS = [
    ("google/gemini-2.0-flash-001", "Gemini 2.0 Flash", 0.100, 0.400),
    ("anthropic/claude-3-5-haiku", "Claude 3.5 Haiku", 0.800, 4.000),
    ("qwen/qwen3-235b-a22b-2507", "Qwen3 235B", 0.071, 0.100),
    ("deepseek/deepseek-v3.2", "DeepSeek v3.2", 0.252, 0.378),
]


# ---------- Common prompt + sources --------------------------------------------
SOURCES = """[S1] Old Age Pension Scheme (P.B.O.C.W.W.B): Punjab Building & Other Construction Workers Welfare Board provides Rs 3000 per month pension to registered construction workers above 60 years of age in Punjab.

[S2] Balri Birth Gift Scheme (P.B.O.C.W.W.B): Provides Rs 51000 financial assistance for the birth of a girl child to registered construction workers in Punjab.

[S3] Stipend Scheme (P.B.O.C.W.W.B): Monthly stipend of Rs 2000 to children of registered construction workers studying in Class 9-12 in Punjab.

[S4] PM SVANidhi: Collateral-free working capital loan up to Rs 50000 for street vendors. Interest subsidy of 7% on timely repayment. Available across India."""


def build_messages(query: str, target_lang_name: str, target_lang_code: str) -> list[dict]:
    system = (
        f"CRITICAL — LANGUAGE RULE: You MUST respond ENTIRELY in {target_lang_name} ({target_lang_code}). "
        f"Every word of your answer must be in {target_lang_name}. Never switch to English.\n\n"
        "You are SahayakSetu, an assistant for Indian government welfare schemes.\n"
        "Answer ONLY from the SOURCES block. No invented amounts, dates, or eligibility.\n"
        "FORMATTING: Plain prose only. No markdown bold (**), no [S1]/[1] citation markers, no em dashes.\n"
    )
    user = (
        f"SOURCES:\n{SOURCES}\n\n"
        f"Question: {query}\n\n"
        "Return JSON: {\"status\":\"ok|insufficient_context\",\"answer\":\"string\",\"claims\":[{\"text\":\"string\",\"source_id\":\"S1\"}]}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# ---------- Test cases ----------------------------------------------------------
TEST_CASES = [
    {
        "id": "en_to_hi",
        "query": "I am 65 years old construction worker in Punjab. Am I eligible for pension?",
        "target_lang_code": "hi-IN",
        "target_lang_name": "Hindi",
        "expected_lang": "hi",
        "must_contain": ["3000", "60"],
    },
    {
        "id": "hi_to_hi",
        "query": "मैं पंजाब में 65 साल का निर्माण मज़दूर हूँ। क्या मुझे पेंशन मिलेगी?",
        "target_lang_code": "hi-IN",
        "target_lang_name": "Hindi",
        "expected_lang": "hi",
        "must_contain": ["3000"],
    },
    {
        "id": "en_to_kn",
        "query": "Can you tell me about street vendor loans?",
        "target_lang_code": "kn-IN",
        "target_lang_name": "Kannada",
        "expected_lang": "kn",
        "must_contain": ["50000", "SVANidhi"],
    },
    {
        "id": "hi_to_ta",
        "query": "मेरी बेटी का जन्म हुआ है, क्या कोई योजना है?",
        "target_lang_code": "ta-IN",
        "target_lang_name": "Tamil",
        "expected_lang": "ta",
        "must_contain": ["51000"],
    },
]


# ---------- API call ------------------------------------------------------------
def call(model: str, messages: list[dict]) -> tuple[float, dict]:
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
    ).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://sahayaksetu.vercel.app",
            "X-Title": "SahayakSetu Bench",
        },
    )
    t0 = time.monotonic()
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        elapsed = time.monotonic() - t0
        return elapsed, json.loads(resp.read())
    except Exception as e:
        elapsed = time.monotonic() - t0
        return elapsed, {"error": str(e)}


# ---------- Scoring -------------------------------------------------------------
def detect_lang(text: str) -> str:
    try:
        from langdetect import detect
        return detect(text[:400])
    except Exception:
        return "?"


_BAD_PATTERNS = [
    (re.compile(r"\*\*"), "markdown_bold"),
    (re.compile(r"\[S?\d+\]"), "citation_marker"),
    (re.compile(r"—"), "em_dash"),
]


def score(case: dict, response: dict, elapsed: float) -> dict:
    if "error" in response:
        return {"ok": False, "error": response["error"][:80], "elapsed_s": round(elapsed, 2)}
    try:
        choice = response["choices"][0]["message"]["content"]
        parsed = json.loads(choice)
    except Exception as e:
        return {"ok": False, "error": f"parse:{e}"[:80], "elapsed_s": round(elapsed, 2)}

    answer = parsed.get("answer", "")
    detected = detect_lang(answer)
    lang_ok = detected == case["expected_lang"]
    facts_ok = all(t in answer for t in case["must_contain"])
    issues = [name for pat, name in _BAD_PATTERNS if pat.search(answer)]
    structure_ok = not issues

    usage = response.get("usage", {})
    return {
        "ok": True,
        "elapsed_s": round(elapsed, 2),
        "detected_lang": detected,
        "lang_ok": lang_ok,
        "facts_ok": facts_ok,
        "structure_ok": structure_ok,
        "issues": issues,
        "answer_preview": answer[:120],
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
    }


# ---------- Run -----------------------------------------------------------------
def main() -> None:
    rows = []
    total_cost = 0.0
    for model_id, model_name, in_price, out_price in MODELS:
        for case in TEST_CASES:
            messages = build_messages(case["query"], case["target_lang_name"], case["target_lang_code"])
            elapsed, response = call(model_id, messages)
            r = score(case, response, elapsed)
            r["model"] = model_name
            r["case"] = case["id"]
            cost = (
                r.get("prompt_tokens", 0) * in_price / 1_000_000
                + r.get("completion_tokens", 0) * out_price / 1_000_000
            )
            r["cost_usd"] = round(cost, 6)
            total_cost += cost
            rows.append(r)
            status = "✓" if (r.get("ok") and r.get("lang_ok") and r.get("facts_ok") and r.get("structure_ok")) else "✗"
            print(
                f"  {status} {model_name:<22} {case['id']:<12} {r.get('elapsed_s', 0):>5.2f}s "
                f"lang={r.get('detected_lang','?')}({'Y' if r.get('lang_ok') else 'N'}) "
                f"facts={'Y' if r.get('facts_ok') else 'N'} struct={'Y' if r.get('structure_ok') else 'N'} "
                f"${r['cost_usd']:.4f}"
            )

    print("\n" + "=" * 90)
    print("Summary by model")
    print("=" * 90)
    by_model: dict[str, list] = {}
    for r in rows:
        by_model.setdefault(r["model"], []).append(r)
    print(f'{"Model":<22} {"Pass/4":<8} {"Avg s":<8} {"Lang✓":<8} {"Facts✓":<8} {"Struct✓":<10} {"Cost":<10}')
    for name, model_rows in by_model.items():
        passed = sum(1 for r in model_rows if r.get("ok") and r.get("lang_ok") and r.get("facts_ok") and r.get("structure_ok"))
        avg_s = sum(r.get("elapsed_s", 0) for r in model_rows) / len(model_rows)
        lang_ok = sum(1 for r in model_rows if r.get("lang_ok"))
        facts_ok = sum(1 for r in model_rows if r.get("facts_ok"))
        struct_ok = sum(1 for r in model_rows if r.get("structure_ok"))
        cost = sum(r["cost_usd"] for r in model_rows)
        print(f"{name:<22} {passed}/4      {avg_s:<8.2f} {lang_ok}/4      {facts_ok}/4      {struct_ok}/4        ${cost:.4f}")
    print(f"\nTotal benchmark cost: ${total_cost:.4f}")


if __name__ == "__main__":
    main()
