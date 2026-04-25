"""
Per-scheme parser: takes the raw API responses on disk and produces the canonical
Mongo doc + the embedding input + the lean Qdrant payload.

Tested in isolation via ``python -m scripts.myscheme.parsers``  (see ``__main__``).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# --- Slate → markdown (best-effort) ----------------------------------------------
# myscheme returns rich text in two formats: a Slate-style nested tree (e.g.
# `benefits`) and a pre-rendered markdown string (`benefits_md`). We always prefer
# the `_md` form when present and only fall back to flattening Slate when it isn't.

_INLINE_KEYS = ("text",)


def _slate_to_text(node: Any) -> str:
    """Flatten a Slate-ish node to plain text (then we wrap as a paragraph)."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(_slate_to_text(c) for c in node)
    if isinstance(node, dict):
        for k in _INLINE_KEYS:
            if k in node and isinstance(node[k], str):
                return node[k]
        children = node.get("children")
        if children is not None:
            return _slate_to_text(children)
    return ""


def slate_to_markdown(value: Any) -> str:
    """Lossy but readable conversion. Treats every top-level node as one paragraph,
    preserves bullets via ``- ``, and leaves anything else as plain prose."""
    if not value:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        out: list[str] = []
        for node in value:
            t = (node.get("type") if isinstance(node, dict) else None) or ""
            text = _slate_to_text(node).strip()
            if not text:
                continue
            if t in ("bulleted-list", "numbered-list"):
                # The container's children should already be list-items; flatten
                # one extra level so each item gets a bullet.
                items = (node.get("children") or []) if isinstance(node, dict) else []
                for it in items:
                    line = _slate_to_text(it).strip()
                    if line:
                        out.append(f"- {line}")
            elif t == "list-item":
                out.append(f"- {text}")
            else:
                out.append(text)
        return "\n\n".join(out)
    return str(value).strip()


def md_or_slate(content: dict, key: str) -> str:
    """Prefer ``{key}_md``; fall back to converting ``{key}`` (Slate) to markdown."""
    md_key = f"{key}_md"
    if isinstance(content.get(md_key), str) and content[md_key].strip():
        return content[md_key].strip()
    return slate_to_markdown(content.get(key))


# --- Helpers --------------------------------------------------------------------


def _strip_md(text: str) -> str:
    """Quick markdown→plain for short_summary fallback. Drops bullet markers,
    inline asterisks/backticks, and link syntax. Not perfect; good enough."""
    if not text:
        return ""
    t = text
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)  # links
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"\*([^*]+)\*", r"\1", t)
    t = re.sub(r"^\s*[-•]\s*", "", t, flags=re.M)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _first_or_none(value: Any) -> Any:
    """myscheme gives many fields as single-element lists; flatten when sensible."""
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _ensure_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _label(value: Any) -> str | None:
    """myscheme wraps most enum-ish fields as ``{value, label}``. Extract the label
    (human-readable form). Plain strings pass through; lists/None get None."""
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        label = value.get("label")
        if isinstance(label, str) and label.strip():
            return label.strip()
        # Some fields use ``name`` instead of ``label``.
        name = value.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
        return None
    return None


def _labels(value: Any) -> list[str]:
    """Same as ``_label`` but for list-of-{value,label} fields like categories/tags."""
    out: list[str] = []
    for entry in _ensure_list(value):
        lbl = _label(entry)
        if lbl:
            out.append(lbl)
    return out


# --- Main parse -----------------------------------------------------------------


def parse_scheme(
    detail: dict,
    faqs: dict | None,
    docs: dict | None,
    *,
    scraped_at: str | None = None,
) -> dict:
    """Build the canonical Mongo doc from the three raw API payloads.

    Returns a dict ready for ``schemes.update_one({"_id": ...}, {"$set": doc}, upsert=True)``.
    Raises ``ValueError`` on missing required fields (``_id``, ``slug``).
    """
    data = (detail or {}).get("data") or {}
    en = data.get("en") or {}
    bd = en.get("basicDetails") or {}
    sc = en.get("schemeContent") or {}
    ec = en.get("eligibilityCriteria") or {}

    scheme_id = data.get("_id")
    slug = data.get("slug") or bd.get("slug")
    if not scheme_id or not slug:
        raise ValueError(f"detail missing _id or slug (got id={scheme_id!r} slug={slug!r})")

    name = bd.get("schemeName") or ""
    short_title = bd.get("schemeShortTitle") or None

    # ``level`` may be a string ("Central") in list responses or a {value, label}
    # dict ({"value": "state", "label": "State/UT"}) in detail responses.
    level_label = _label(bd.get("level"))
    level = level_label.lower() if level_label else None
    # Normalise "state/ut" → "state" so downstream filters can be uniform.
    if level and level.startswith("state"):
        level = "state"
    elif level and level.startswith("central"):
        level = "central"

    state_label = _label(bd.get("state"))
    state = state_label if (level == "state" and state_label and state_label.lower() != "all") else None

    categories = _labels(bd.get("schemeCategory"))
    sub_categories = _labels(bd.get("schemeSubCategory"))
    # Tags arrive as plain strings in list endpoint, sometimes as labelled dicts in detail.
    tags = [t for t in (_label(x) for x in _ensure_list(bd.get("tags"))) if t]

    brief = (sc.get("briefDescription") or "").strip()
    detailed_md = md_or_slate(sc, "detailedDescription")
    benefits_md = md_or_slate(sc, "benefits")
    exclusions_md = md_or_slate(sc, "exclusions")
    eligibility_md = md_or_slate(ec, "eligibilityDescription")

    application_modes: list[dict] = []
    for proc in en.get("applicationProcess") or []:
        if not isinstance(proc, dict):
            continue
        mode = proc.get("mode")
        process_md = md_or_slate(proc, "process")
        if mode or process_md:
            application_modes.append({"mode": mode, "process_md": process_md})

    references = []
    for ref in sc.get("references") or []:
        if not isinstance(ref, dict):
            continue
        title = ref.get("title") or ref.get("label")
        url = ref.get("url") or ref.get("href")
        if url:
            references.append({"title": title, "url": url})

    documents_required_md = ""
    if docs and not docs.get("_skipped"):
        d_en = (docs.get("data") or {}).get("en") or {}
        documents_required_md = (
            d_en.get("documentsRequired_md")
            or slate_to_markdown(d_en.get("documentsRequired"))
            or ""
        )

    faq_list: list[dict] = []
    if faqs and not faqs.get("_skipped"):
        for f in (faqs.get("data") or {}).get("en", {}).get("faqs") or []:
            if not isinstance(f, dict):
                continue
            q = (f.get("question") or "").strip()
            a_md = (f.get("answer_md") or "").replace("[?]", "₹").strip()
            if not a_md:
                a_md = slate_to_markdown(f.get("answer")).replace("[?]", "₹").strip()
            if q:
                faq_list.append({"question": q, "answer_md": a_md})

    bt_labels = _labels(sc.get("benefitTypes"))
    benefit_types = ", ".join(bt_labels) if bt_labels else None

    target_beneficiaries = _labels(bd.get("targetBeneficiaries")) or None

    now = datetime.now(timezone.utc).isoformat()

    doc: dict = {
        "_id": scheme_id,
        "slug": slug,
        "name": name,
        "short_title": short_title,
        "level": level,
        "state": state,
        "ministry": _label(bd.get("nodalMinistryName")),
        "department": _label(bd.get("nodalDepartmentName")),
        "categories": categories,
        "sub_categories": sub_categories,
        "tags": tags,
        "dbt_scheme": bool(bd.get("dbtScheme")) if bd.get("dbtScheme") is not None else None,
        "benefit_types": benefit_types,
        "target_beneficiaries": target_beneficiaries,
        "brief_description": brief,
        "detailed_description_md": detailed_md,
        "benefits_md": benefits_md,
        "eligibility_md": eligibility_md,
        "exclusions_md": exclusions_md,
        "documents_required_md": documents_required_md,
        "application_modes": application_modes,
        "references": references,
        "faqs": faq_list,
        "scheme_open_date": bd.get("schemeOpenDate"),
        "scheme_close_date": bd.get("schemeCloseDate"),
        "scraped_at": scraped_at or now,
        "ingested_at": now,
        # NOTE: we deliberately do NOT embed the raw API payloads here. The verbatim
        # responses live on disk under data/raw/{schemes,faqs,docs}/{slug}.json — that's
        # already a complete archive. Storing them in Mongo too would roughly 4-5× the
        # collection size for no functional benefit.
    }
    return doc


# --- Embedding text + short summary --------------------------------------------


def build_embedding_text(doc: dict, *, max_chars: int = 1500) -> str:
    """Concatenate the fields that should drive vector search.

    Order matters — the highest-signal fields go first so they survive truncation.
    Tags and state at the end let queries like "scholarship Tamil Nadu disabled"
    rank the right docs without exact phrase matching.
    """
    parts: list[str] = []
    if doc.get("name"):
        parts.append(doc["name"])
    if doc.get("short_title"):
        parts.append(doc["short_title"])
    if doc.get("brief_description"):
        parts.append(doc["brief_description"])
    benefits = (doc.get("benefits_md") or "")[:600]
    if benefits:
        parts.append(_strip_md(benefits))
    eligibility = (doc.get("eligibility_md") or "")[:600]
    if eligibility:
        parts.append(_strip_md(eligibility))
    if doc.get("tags"):
        parts.append(", ".join(str(t) for t in doc["tags"]))
    if doc.get("state"):
        parts.append(f"State: {doc['state']}")
    if doc.get("level"):
        parts.append(f"Level: {doc['level']}")
    text = " | ".join(p for p in parts if p)
    return text[:max_chars]


def build_short_summary(doc: dict, *, max_chars: int = 240) -> str:
    if doc.get("brief_description"):
        return doc["brief_description"][:max_chars]
    benefits_plain = _strip_md((doc.get("benefits_md") or ""))[:max_chars - len(doc.get("name") or "") - 4]
    name = doc.get("name") or ""
    if benefits_plain:
        return f"{name} — {benefits_plain}".strip()
    return name[:max_chars]


def build_qdrant_payload(doc: dict, short_summary: str) -> dict:
    """Lean payload — just what the search list view needs. Rich text stays in Mongo."""
    return {
        "slug": doc["slug"],
        "scheme_id": doc["_id"],
        "name": doc.get("name"),
        "level": doc.get("level"),
        "state": doc.get("state"),
        "categories": doc.get("categories") or [],
        "tags": doc.get("tags") or [],
        "short_summary": short_summary,
    }


# --- Standalone diagnostic ------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    repo_root = Path(__file__).resolve().parents[2]
    raw = repo_root / "data" / "raw"
    schemes_dir = raw / "schemes"
    if not schemes_dir.exists() or not list(schemes_dir.iterdir()):
        print("no scraped schemes yet", file=sys.stderr)
        sys.exit(1)
    sample = next(schemes_dir.iterdir())
    slug = sample.stem
    detail = json.load(sample.open(encoding="utf-8"))
    faq_path = raw / "faqs" / f"{slug}.json"
    doc_path = raw / "docs" / f"{slug}.json"
    faqs = json.load(faq_path.open(encoding="utf-8")) if faq_path.exists() else None
    docs = json.load(doc_path.open(encoding="utf-8")) if doc_path.exists() else None

    parsed = parse_scheme(detail, faqs, docs)
    parsed.pop("raw", None)  # too noisy for stdout
    print(json.dumps(parsed, indent=2, ensure_ascii=False, default=str)[:3000])
    print("\n--- embedding text ---")
    print(build_embedding_text(parsed))
    print("\n--- short summary ---")
    print(build_short_summary(parsed))
