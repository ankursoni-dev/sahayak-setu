"""Benchmark Sarvam models alongside the OpenRouter winners (Gemini Flash, DeepSeek v3.2).

Same 4 test cases as bench_models.py: en→hi, hi→hi, en→kn, hi→ta.
Sarvam uses a different auth header (api-subscription-key) and endpoint, so it
gets its own caller. Results are appended to the OpenRouter benchmark for direct
comparison.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

env_text = (ROOT / ".env").read_text()
OPENROUTER_KEY = re.search(r"OPENROUTER_API_KEY=([^\n]+)", env_text).group(1).strip()
SARVAM_KEY = re.search(r"SARVAM_API_KEY=([^\n]+)", env_text).group(1).strip()


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


TEST_CASES = [
    {"id": "en_to_hi", "query": "I am 65 years old construction worker in Punjab. Am I eligible for pension?", "target_lang_code": "hi-IN", "target_lang_name": "Hindi", "expected_lang": "hi", "must_contain": ["3000"]},
    {"id": "hi_to_hi", "query": "मैं पंजाब में 65 साल का निर्माण मज़दूर हूँ। क्या मुझे पेंशन मिलेगी?", "target_lang_code": "hi-IN", "target_lang_name": "Hindi", "expected_lang": "hi", "must_contain": ["3000"]},
    {"id": "en_to_kn", "query": "Can you tell me about street vendor loans?", "target_lang_code": "kn-IN", "target_lang_name": "Kannada", "expected_lang": "kn", "must_contain": []},
    {"id": "hi_to_ta", "query": "मेरी बेटी का जन्म हुआ है, क्या कोई योजना है?", "target_lang_code": "ta-IN", "target_lang_name": "Tamil", "expected_lang": "ta", "must_contain": []},
]


def call_openrouter(model: str, messages: list[dict]) -> tuple[float, dict]:
    body = json.dumps({"model": model, "messages": messages, "temperature": 0.2, "response_format": {"type": "json_object"}}).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json", "HTTP-Referer": "https://sahayaksetu.vercel.app", "X-Title": "Bench"},
    )
    t0 = time.monotonic()
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        return time.monotonic() - t0, json.loads(resp.read())
    except Exception as e:
        return time.monotonic() - t0, {"error": str(e)[:200]}


def call_sarvam(model: str, messages: list[dict]) -> tuple[float, dict]:
    body = json.dumps({"model": model, "messages": messages, "temperature": 0.2}).encode()
    req = urllib.request.Request(
        "https://api.sarvam.ai/v1/chat/completions",
        data=body,
        headers={"api-subscription-key": SARVAM_KEY, "Content-Type": "application/json"},
    )
    t0 = time.monotonic()
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        return time.monotonic() - t0, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return time.monotonic() - t0, {"error": f"HTTP {e.code}: {e.read().decode()[:300]}"}
    except Exception as e:
        return time.monotonic() - t0, {"error": str(e)[:300]}


def detect_lang(text: str) -> str:
    try:
        from langdetect import detect
        return detect(text[:400])
    except Exception:
        return "?"


_BAD = [(re.compile(r"\*\*"), "md_bold"), (re.compile(r"\[S?\d+\]"), "cite"), (re.compile(r"—"), "emdash")]


def score(case: dict, response: dict, elapsed: float) -> dict:
    if "error" in response:
        return {"ok": False, "error": response["error"][:120], "elapsed_s": round(elapsed, 2)}
    try:
        choice = response["choices"][0]["message"]["content"]
        # Try parsing as JSON; some models return raw prose if no response_format honored
        try:
            parsed = json.loads(choice)
            answer = parsed.get("answer", choice)
        except Exception:
            answer = choice
    except Exception as e:
        return {"ok": False, "error": f"parse:{e}"[:120], "elapsed_s": round(elapsed, 2)}

    detected = detect_lang(answer)
    issues = [n for p, n in _BAD if p.search(answer)]
    usage = response.get("usage", {})
    return {
        "ok": True,
        "elapsed_s": round(elapsed, 2),
        "detected_lang": detected,
        "lang_ok": detected == case["expected_lang"],
        "facts_ok": all(t in answer for t in case["must_contain"]),
        "structure_ok": not issues,
        "issues": issues,
        "answer_preview": answer[:140],
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
    }


# Models to test — Sarvam first, then OpenRouter winners for direct comparison
TESTS = [
    ("sarvam-m", "Sarvam-M", call_sarvam),
    ("google/gemini-2.0-flash-001", "Gemini Flash", call_openrouter),
    ("deepseek/deepseek-v3.2", "DeepSeek v3.2", call_openrouter),
]


def main() -> None:
    rows = []
    for model_id, name, caller in TESTS:
        print(f"\n--- {name} ({model_id}) ---")
        for case in TEST_CASES:
            messages = build_messages(case["query"], case["target_lang_name"], case["target_lang_code"])
            elapsed, resp = caller(model_id, messages)
            r = score(case, resp, elapsed)
            r["model"] = name
            r["case"] = case["id"]
            rows.append(r)
            ok_lang = r.get("lang_ok")
            mark = "✓" if (r.get("ok") and ok_lang and r.get("structure_ok")) else "✗"
            err = r.get("error", "")
            preview = r.get("answer_preview", "")[:80].replace("\n", " ")
            print(f"  {mark} {case['id']:<10} {r.get('elapsed_s', 0):>5.2f}s  lang={r.get('detected_lang','?')} struct={'Y' if r.get('structure_ok') else 'N'}")
            if err:
                print(f"     ERROR: {err}")
            elif preview:
                print(f"     {preview}")

    print("\n" + "=" * 80)
    print(f'{"Model":<18} {"Pass":<8} {"Avg s":<8} {"Lang ok":<10} {"Struct ok":<10}')
    by_model: dict[str, list] = {}
    for r in rows:
        by_model.setdefault(r["model"], []).append(r)
    for name, mr in by_model.items():
        passed = sum(1 for r in mr if r.get("ok") and r.get("lang_ok") and r.get("structure_ok"))
        avg = sum(r.get("elapsed_s", 0) for r in mr) / len(mr) if mr else 0
        lang = sum(1 for r in mr if r.get("lang_ok"))
        struct = sum(1 for r in mr if r.get("structure_ok"))
        print(f"{name:<18} {passed}/4      {avg:<8.2f} {lang}/4        {struct}/4")


if __name__ == "__main__":
    main()
