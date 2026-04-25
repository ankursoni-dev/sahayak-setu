"""
myscheme.gov.in scraper — populates data/raw/ with verbatim API responses.

Run sequence:
    python scripts/myscheme/scrape.py list                  # paginate the list API
    python scripts/myscheme/scrape.py detail [--limit N]    # fetch per-slug detail+faqs+docs
    python scripts/myscheme/scrape.py all [--limit N]       # both phases

Notes
-----
- The list endpoint's hit `id` is an Elasticsearch index ID, NOT the Mongo ObjectId
  the faqs/docs endpoints expect. We pull `data._id` from each detail response and
  use that for the secondary endpoints. (The pipeline-prompt doc had this wrong.)
- Resumable: if a target file exists and is non-empty, we skip. Pass `--force`
  to refetch.
- Polite by default: 4 concurrent in-flight, 0.4–0.8s jitter, exp-backoff retries
  on 5xx / 429 / connection errors. Never retries 404/412.
- Streams writes to disk; never holds the full corpus in memory.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

API_KEY = "tYTy5eEhlu9rFjyxuCr7ra7ACp4dv1RH8gWuHTDc"
BASE = "https://api.myscheme.gov.in"
HEADERS = {
    "x-api-key": API_KEY,
    "origin": "https://www.myscheme.gov.in",
    "accept": "application/json, text/plain, */*",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data" / "raw"
LIST_DIR = DATA / "list"
SCHEMES_DIR = DATA / "schemes"
FAQS_DIR = DATA / "faqs"
DOCS_DIR = DATA / "docs"
SLUGS_PATH = DATA / "slugs.jsonl"
FAILED_PATH = DATA / "failed.jsonl"
PROGRESS_PATH = DATA / "progress.log"

PAGE_SIZE = 50
CONCURRENCY = 4
JITTER_RANGE = (0.4, 0.8)
TIMEOUT = httpx.Timeout(30.0, connect=10.0)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("myscheme")


# --- HTTP plumbing ---------------------------------------------------------------


class RetryableHTTPError(Exception):
    """Raised on 5xx/429 to trigger tenacity backoff. 404/412 are NOT retryable."""


async def _request(client: httpx.AsyncClient, method: str, url: str, **kw) -> httpx.Response:
    """One attempt — tenacity wraps this for retries."""
    resp = await client.request(method, url, **kw)
    if resp.status_code in (429,) or 500 <= resp.status_code < 600:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                await asyncio.sleep(float(retry_after))
            except ValueError:
                pass
        raise RetryableHTTPError(f"{resp.status_code} on {url}")
    return resp


async def _fetch_with_retry(client: httpx.AsyncClient, url: str, *, params: dict | None = None) -> httpx.Response:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1.0, min=1.0, max=20.0),
        retry=retry_if_exception_type((RetryableHTTPError, httpx.TransportError)),
        reraise=True,
    ):
        with attempt:
            return await _request(client, "GET", url, params=params)
    raise RuntimeError("unreachable")  # tenacity always raises or returns


async def _polite_sleep() -> None:
    await asyncio.sleep(random.uniform(*JITTER_RANGE))


# --- File helpers ---------------------------------------------------------------


def _need_fetch(path: Path, force: bool) -> bool:
    return force or not path.exists() or path.stat().st_size == 0


def _atomic_write_json(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    tmp.replace(path)


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


# --- Phase A: list pagination ---------------------------------------------------


async def fetch_list_page(client: httpx.AsyncClient, *, frm: int, size: int, force: bool) -> dict:
    target = LIST_DIR / f"page_{frm:05d}.json"
    if not _need_fetch(target, force):
        with target.open(encoding="utf-8") as f:
            return json.load(f)
    log.info("list page from=%s size=%s", frm, size)
    resp = await _fetch_with_retry(
        client,
        f"{BASE}/search/v6/schemes",
        params={"lang": "en", "q": "[]", "keyword": "", "sort": "", "from": frm, "size": size},
    )
    data = resp.json()
    _atomic_write_json(target, data)
    await _polite_sleep()
    return data


async def phase_list(force: bool, limit: int | None) -> list[dict]:
    """Iterate the list API, save raw pages, and build slugs.jsonl.

    Returns the full slug list (unique by slug).
    """
    LIST_DIR.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT) as client:
        first = await fetch_list_page(client, frm=0, size=PAGE_SIZE, force=force)
        total = (
            first.get("data", {}).get("summary", {}).get("total")
            or first.get("data", {}).get("hits", {}).get("page", {}).get("total")
            or 0
        )
        log.info("total schemes reported by API: %s", total)

        # Pages are independent; small concurrency keeps us polite.
        sem = asyncio.Semaphore(CONCURRENCY)
        offsets = list(range(PAGE_SIZE, total, PAGE_SIZE))
        if limit is not None:
            offsets = [o for o in offsets if o < limit]

        async def _one(frm: int) -> dict:
            async with sem:
                return await fetch_list_page(client, frm=frm, size=PAGE_SIZE, force=force)

        pages = [first]
        results = await asyncio.gather(*(_one(o) for o in offsets), return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                log.warning("list page failed: %s", r)
                continue
            pages.append(r)

    # Flatten hits → slugs.jsonl, dedup by slug.
    seen: set[str] = set()
    if SLUGS_PATH.exists() and not force:
        for row in _read_jsonl(SLUGS_PATH):
            seen.add(row.get("slug", ""))
    written = 0
    skipped = 0
    for page in pages:
        items = page.get("data", {}).get("hits", {}).get("items", []) or []
        for hit in items:
            fields = hit.get("fields") or {}
            slug = fields.get("slug")
            if not slug:
                continue
            if slug in seen:
                skipped += 1
                continue
            seen.add(slug)
            _append_jsonl(SLUGS_PATH, {
                "slug": slug,
                "list_index_id": hit.get("id"),  # NOT the Mongo _id
                "name": fields.get("schemeName"),
                "level": fields.get("level"),
                "states": fields.get("beneficiaryState") or [],
                "categories": fields.get("schemeCategory") or [],
                "tags": fields.get("tags") or [],
                "brief_description": fields.get("briefDescription"),
            })
            written += 1
    log.info("slugs: %s new written, %s already known. total: %s", written, skipped, len(seen))
    return _read_jsonl(SLUGS_PATH)


# --- Phase B: detail + faqs + docs ----------------------------------------------


async def fetch_detail(client: httpx.AsyncClient, slug: str, *, force: bool) -> dict | None:
    target = SCHEMES_DIR / f"{slug}.json"
    if not _need_fetch(target, force):
        with target.open(encoding="utf-8") as f:
            return json.load(f)
    resp = await _fetch_with_retry(
        client, f"{BASE}/schemes/v6/public/schemes", params={"slug": slug, "lang": "en"}
    )
    if resp.status_code == 404:
        log.warning("detail 404: %s", slug)
        return None
    if resp.status_code != 200:
        raise RuntimeError(f"detail {resp.status_code} for {slug}: {resp.text[:200]}")
    data = resp.json()
    _atomic_write_json(target, data)
    await _polite_sleep()
    return data


async def fetch_faqs(client: httpx.AsyncClient, slug: str, scheme_id: str, *, force: bool) -> dict | None:
    target = FAQS_DIR / f"{slug}.json"
    if not _need_fetch(target, force):
        return None
    resp = await _fetch_with_retry(
        client, f"{BASE}/schemes/v6/public/schemes/{scheme_id}/faqs", params={"lang": "en"}
    )
    # Some schemes have no FAQs and the API returns 412 "Invalid Scheme Id" or
    # 200 with an empty list. We cache whatever we got so re-runs skip it.
    if resp.status_code in (404, 412):
        _atomic_write_json(target, {"_skipped": True, "status": resp.status_code})
        return None
    if resp.status_code != 200:
        raise RuntimeError(f"faqs {resp.status_code} for {slug}: {resp.text[:200]}")
    data = resp.json()
    _atomic_write_json(target, data)
    await _polite_sleep()
    return data


async def fetch_docs(client: httpx.AsyncClient, slug: str, scheme_id: str, *, force: bool) -> dict | None:
    target = DOCS_DIR / f"{slug}.json"
    if not _need_fetch(target, force):
        return None
    resp = await _fetch_with_retry(
        client, f"{BASE}/schemes/v6/public/schemes/{scheme_id}/documents", params={"lang": "en"}
    )
    if resp.status_code in (404, 412):
        _atomic_write_json(target, {"_skipped": True, "status": resp.status_code})
        return None
    if resp.status_code != 200:
        raise RuntimeError(f"docs {resp.status_code} for {slug}: {resp.text[:200]}")
    data = resp.json()
    _atomic_write_json(target, data)
    await _polite_sleep()
    return data


async def fetch_one_scheme(client: httpx.AsyncClient, slug: str, *, force: bool) -> str:
    """Fetch detail + faqs + docs for a single slug. Returns 'ok' / 'skip' / 'fail:<msg>'."""
    detail = await fetch_detail(client, slug, force=force)
    if detail is None:
        return "skip"
    scheme_id = (detail.get("data") or {}).get("_id")
    if not scheme_id:
        log.warning("no _id in detail for %s — skipping faqs/docs", slug)
        return "ok"
    # Run faqs + docs concurrently for this slug; each is independently retried.
    await asyncio.gather(
        fetch_faqs(client, slug, scheme_id, force=force),
        fetch_docs(client, slug, scheme_id, force=force),
        return_exceptions=False,
    )
    return "ok"


async def phase_detail(force: bool, limit: int | None) -> None:
    SCHEMES_DIR.mkdir(parents=True, exist_ok=True)
    FAQS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    rows = _read_jsonl(SLUGS_PATH)
    if not rows:
        log.error("no slugs.jsonl — run `list` phase first")
        return
    if limit is not None:
        rows = rows[:limit]
    log.info("phase B: %s slugs to process", len(rows))

    sem = asyncio.Semaphore(CONCURRENCY)
    counts = {"ok": 0, "skip": 0, "cached": 0, "fail": 0}
    start = time.monotonic()

    async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT) as client:
        async def _one(slug: str) -> None:
            async with sem:
                detail_path = SCHEMES_DIR / f"{slug}.json"
                already_cached = (
                    detail_path.exists()
                    and detail_path.stat().st_size > 0
                    and (FAQS_DIR / f"{slug}.json").exists()
                    and (DOCS_DIR / f"{slug}.json").exists()
                )
                if already_cached and not force:
                    counts["cached"] += 1
                    return
                try:
                    result = await fetch_one_scheme(client, slug, force=force)
                    counts[result] += 1
                    _append_jsonl(PROGRESS_PATH, {"slug": slug, "result": result, "ts": time.time()})
                except Exception as e:
                    counts["fail"] += 1
                    log.warning("FAIL %s: %s", slug, str(e)[:160])
                    _append_jsonl(FAILED_PATH, {"slug": slug, "error": str(e)[:500], "ts": time.time()})

        # Process in batches so progress lines appear regularly.
        BATCH = 100
        for i in range(0, len(rows), BATCH):
            batch = rows[i : i + BATCH]
            await asyncio.gather(*(_one(r["slug"]) for r in batch), return_exceptions=False)
            elapsed = time.monotonic() - start
            done = sum(counts.values())
            rate = done / elapsed if elapsed > 0 else 0
            log.info(
                "progress: %s/%s done | ok=%s cached=%s skip=%s fail=%s | %.1f/s",
                done, len(rows), counts["ok"], counts["cached"], counts["skip"], counts["fail"], rate,
            )

    elapsed = time.monotonic() - start
    log.info(
        "DONE phase B in %.1fs — ok=%s cached=%s skip=%s fail=%s",
        elapsed, counts["ok"], counts["cached"], counts["skip"], counts["fail"],
    )


# --- CLI ------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="myscheme.gov.in scraper")
    parser.add_argument("phase", choices=["list", "detail", "all"])
    parser.add_argument("--force", action="store_true", help="refetch even if cached")
    parser.add_argument("--limit", type=int, default=None, help="cap slugs/pages processed")
    args = parser.parse_args()

    DATA.mkdir(parents=True, exist_ok=True)

    async def _run() -> None:
        if args.phase in ("list", "all"):
            await phase_list(force=args.force, limit=args.limit)
        if args.phase in ("detail", "all"):
            await phase_detail(force=args.force, limit=args.limit)

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        log.warning("interrupted — partial progress is on disk; re-run to resume")
        sys.exit(130)


if __name__ == "__main__":
    main()
