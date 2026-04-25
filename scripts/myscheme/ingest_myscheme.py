"""
Read scraped data from data/raw/, parse into the canonical Mongo doc, embed the
search-relevant text, and upsert into:

  - MongoDB ``myscheme.schemes``  (full doc; source of truth)
  - Qdrant ``schemes`` collection  (lean payload + 384-dim vector for retrieval)

Idempotent: re-running upserts (deterministic UUIDv5 from slug) — never duplicates.
Resumable: a single failed slug doesn't crash the run.

Uses MYSCHEME_QDRANT_URL / MYSCHEME_QDRANT_API_KEY for the new cluster (the original
QDRANT_URL stays untouched). Mongo connection comes from MONGODB_URL.

Usage:
    python scripts/myscheme/ingest_myscheme.py --dry-run
    python scripts/myscheme/ingest_myscheme.py --limit 50
    python scripts/myscheme/ingest_myscheme.py --recreate
    python scripts/myscheme/ingest_myscheme.py --skip-qdrant     # Mongo only
"""

from __future__ import annotations

import argparse
import gc
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.myscheme.parsers import (  # noqa: E402  — import after sys.path tweak
    build_embedding_text,
    build_qdrant_payload,
    build_short_summary,
    parse_scheme,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ingest")

DATA = REPO_ROOT / "data" / "raw"
SCHEMES_DIR = DATA / "schemes"
FAQS_DIR = DATA / "faqs"
DOCS_DIR = DATA / "docs"

QDRANT_COLLECTION = "schemes"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"  # 384 dim — keeps grounding service compatible
EMBED_BATCH = 32

# Stable namespace for UUIDv5 derived from slug — same slug → same point id forever.
_NAMESPACE = uuid.UUID("8b8c8c00-2f12-4c61-9a0e-1a5fa1b2b3c4")


def _load_pair(slug: str) -> tuple[dict, dict | None, dict | None] | None:
    detail_path = SCHEMES_DIR / f"{slug}.json"
    if not detail_path.exists() or detail_path.stat().st_size == 0:
        return None
    detail = json.load(detail_path.open(encoding="utf-8"))
    faq_path = FAQS_DIR / f"{slug}.json"
    docs_path = DOCS_DIR / f"{slug}.json"
    faqs = json.load(faq_path.open(encoding="utf-8")) if faq_path.exists() else None
    docs = json.load(docs_path.open(encoding="utf-8")) if docs_path.exists() else None
    return detail, faqs, docs


def _slug_iter(limit: int | None):
    files = sorted(SCHEMES_DIR.glob("*.json"))
    if limit is not None:
        files = files[:limit]
    for f in files:
        yield f.stem


# --- Mongo --------------------------------------------------------------------

def _connect_mongo(uri: str | None, db_name: str | None):
    from pymongo import MongoClient
    uri = uri or os.environ.get("MONGODB_URL") or os.environ.get("MONGO_URI")
    if not uri:
        raise RuntimeError("MONGODB_URL not set in env and --mongo-uri not provided")
    # Default to the same DB the rest of the app uses (sahayaksetu) — no reason to
    # spawn a second database in the same cluster. Override with --mongo-db or
    # the MONGODB_DB env var if you want catalog data isolated.
    db_name = db_name or os.environ.get("MONGODB_DB") or "sahayaksetu"
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    return client, client[db_name]


def _ensure_mongo_indexes(coll) -> None:
    """Best-effort index creation.

    Mongo refuses `createIndex` when free disk is below ~500 MB even though normal
    inserts work fine (WiredTiger reserves scratch space for materialising the new
    index file). On Railway's small-volume plan this trips constantly, so we treat
    each index as optional and warn instead of crashing the run. After you bump
    the disk (Railway → Volumes), re-run ingest and the missing ones will be
    created on the next pass.

    Note: ``_id`` is unique by default and we set ``_id = scheme_id`` from the API,
    so de-duplication is enforced regardless of whether the slug index lands.
    """
    wanted = [
        ("slug",                          {"unique": True}),
        ([("level", 1), ("state", 1)],    {}),
        ("categories",                    {}),
        ("tags",                          {}),
    ]
    skipped: list[str] = []
    for keys, opts in wanted:
        try:
            coll.create_index(keys, **opts)
        except Exception as e:
            msg = str(e)
            if "OutOfDiskSpace" in msg or "available disk space" in msg:
                skipped.append(str(keys))
            else:
                log.warning("create_index(%s) failed: %s", keys, msg[:160])
    if skipped:
        log.warning(
            "skipped %d index(es) due to disk pressure: %s — re-run after bumping the volume",
            len(skipped), ", ".join(skipped),
        )


# --- Qdrant -------------------------------------------------------------------

def _connect_qdrant(url: str | None, api_key: str | None):
    from qdrant_client import QdrantClient
    url = url or os.environ.get("MYSCHEME_QDRANT_URL")
    api_key = api_key or os.environ.get("MYSCHEME_QDRANT_API_KEY")
    if not url:
        raise RuntimeError("MYSCHEME_QDRANT_URL not set in env and --qdrant-url not provided")
    return QdrantClient(url=url, api_key=api_key or None)


def _ensure_qdrant_collection(client, *, recreate: bool) -> None:
    """Create the collection with on-disk vectors + INT8 quantization. Idempotent.

    Lean memory: the bulk of the vector lives on disk; only INT8-quantized copies
    are kept in RAM for similarity rescoring. Fits well below 1 GB RSS even at
    ~5k schemes × 384d.
    """
    from qdrant_client.models import (
        Distance,
        OptimizersConfigDiff,
        PayloadSchemaType,
        ScalarQuantization,
        ScalarQuantizationConfig,
        ScalarType,
        VectorParams,
    )

    existing = {c.name for c in client.get_collections().collections}
    if QDRANT_COLLECTION in existing:
        if not recreate:
            log.info("qdrant collection '%s' exists — keeping (use --recreate to drop)", QDRANT_COLLECTION)
            _ensure_payload_indexes(client)
            return
        log.warning("qdrant collection '%s' exists — dropping (per --recreate)", QDRANT_COLLECTION)
        client.delete_collection(QDRANT_COLLECTION)

    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE, on_disk=True),
        on_disk_payload=True,
        optimizers_config=OptimizersConfigDiff(memmap_threshold=20000),
        quantization_config=ScalarQuantization(
            scalar=ScalarQuantizationConfig(type=ScalarType.INT8, always_ram=True)
        ),
    )
    log.info("created qdrant collection '%s'", QDRANT_COLLECTION)
    _ensure_payload_indexes(client)


def _ensure_payload_indexes(client) -> None:
    """Keyword indexes on the fields we expect to filter by — cheap, makes
    structured filters (level=state&state=Karnataka&categories=Health) fast."""
    from qdrant_client.models import PayloadSchemaType
    for field in ("level", "state", "categories", "tags", "slug"):
        try:
            client.create_payload_index(
                collection_name=QDRANT_COLLECTION,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception as e:
            # Index already exists is fine.
            if "already exists" not in str(e).lower():
                log.warning("payload index '%s' failed: %s", field, e)


# --- Embedding ----------------------------------------------------------------

def _make_embedder():
    """Lazy-import + load the embedder. Caller is responsible for releasing it."""
    from fastembed import TextEmbedding
    log.info("loading embedding model '%s' (~50 MB download on first run)", EMBEDDING_MODEL)
    return TextEmbedding(EMBEDDING_MODEL)


def _embed_batch(embedder, texts: list[str]) -> list[list[float]]:
    return [list(v) for v in embedder.embed(texts, batch_size=EMBED_BATCH)]


# --- Pipeline -----------------------------------------------------------------

def run(
    *,
    limit: int | None,
    recreate: bool,
    dry_run: bool,
    skip_mongo: bool,
    skip_qdrant: bool,
    mongo_uri: str | None,
    mongo_db: str | None,
    qdrant_url: str | None,
    qdrant_api_key: str | None,
) -> None:
    if not SCHEMES_DIR.exists():
        log.error("data/raw/schemes is empty — run scrape.py first")
        sys.exit(1)

    if dry_run:
        log.warning("--dry-run: parsing one sample, NOT writing to Mongo or Qdrant")
        for slug in _slug_iter(1):
            triple = _load_pair(slug)
            if triple is None:
                continue
            doc = parse_scheme(*triple)
            payload = build_qdrant_payload(doc, build_short_summary(doc))
            print(json.dumps(
                {"slug": doc["slug"], "_id": doc["_id"], "embedding_text_len": len(build_embedding_text(doc)),
                 "qdrant_payload": payload, "mongo_doc_keys": sorted(doc.keys())},
                indent=2, ensure_ascii=False, default=str,
            ))
        return

    # Mongo
    coll = None
    if not skip_mongo:
        client, db = _connect_mongo(mongo_uri, mongo_db)
        coll = db["schemes"]
        _ensure_mongo_indexes(coll)
        log.info("mongo connected (db=%s, collection=schemes)", db.name)

    # Qdrant
    qclient = None
    if not skip_qdrant:
        qclient = _connect_qdrant(qdrant_url, qdrant_api_key)
        _ensure_qdrant_collection(qclient, recreate=recreate)
        log.info("qdrant connected — collection '%s' ready", QDRANT_COLLECTION)

    embedder = _make_embedder() if not skip_qdrant else None

    counts = {"parsed": 0, "mongo_upserts": 0, "qdrant_upserts": 0, "parse_failures": 0}
    pending_qdrant: list[tuple[str, dict, str]] = []  # (slug, payload, embedding_text)
    start = time.monotonic()

    def _flush_qdrant_batch() -> None:
        if not pending_qdrant or qclient is None or embedder is None:
            pending_qdrant.clear()
            return
        from qdrant_client.models import PointStruct
        texts = [t for _, _, t in pending_qdrant]
        vectors = _embed_batch(embedder, texts)
        points = [
            PointStruct(
                id=str(uuid.uuid5(_NAMESPACE, slug)),
                vector=vec,
                payload=payload,
            )
            for (slug, payload, _), vec in zip(pending_qdrant, vectors)
        ]
        qclient.upsert(collection_name=QDRANT_COLLECTION, points=points, wait=True)
        counts["qdrant_upserts"] += len(points)
        pending_qdrant.clear()

    for slug in _slug_iter(limit):
        triple = _load_pair(slug)
        if triple is None:
            continue
        try:
            doc = parse_scheme(*triple)
        except Exception as e:
            log.warning("parse failure %s: %s", slug, str(e)[:200])
            counts["parse_failures"] += 1
            continue
        counts["parsed"] += 1

        if coll is not None:
            from pymongo import UpdateOne
            coll.update_one({"_id": doc["_id"]}, {"$set": doc}, upsert=True)
            counts["mongo_upserts"] += 1

        if qclient is not None:
            short = build_short_summary(doc)
            payload = build_qdrant_payload(doc, short)
            embedding_text = build_embedding_text(doc)
            pending_qdrant.append((doc["slug"], payload, embedding_text))
            if len(pending_qdrant) >= EMBED_BATCH:
                _flush_qdrant_batch()
                if counts["parsed"] % (EMBED_BATCH * 4) == 0:
                    elapsed = time.monotonic() - start
                    log.info(
                        "progress: %s parsed | mongo=%s qdrant=%s fail=%s | %.1f/s",
                        counts["parsed"], counts["mongo_upserts"], counts["qdrant_upserts"],
                        counts["parse_failures"], counts["parsed"] / elapsed if elapsed else 0,
                    )

    if pending_qdrant:
        _flush_qdrant_batch()

    if embedder is not None:
        del embedder
        gc.collect()

    elapsed = time.monotonic() - start
    log.info(
        "DONE in %.1fs — parsed=%s mongo=%s qdrant=%s fail=%s",
        elapsed, counts["parsed"], counts["mongo_upserts"], counts["qdrant_upserts"], counts["parse_failures"],
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--recreate", action="store_true", help="drop + rebuild qdrant collection")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-mongo", action="store_true")
    p.add_argument("--skip-qdrant", action="store_true")
    p.add_argument("--mongo-uri", default=None)
    p.add_argument("--mongo-db", default=None, help="defaults to MONGODB_DB env or 'sahayaksetu'")
    p.add_argument("--qdrant-url", default=None)
    p.add_argument("--qdrant-api-key", default=None)
    args = p.parse_args()

    run(
        limit=args.limit,
        recreate=args.recreate,
        dry_run=args.dry_run,
        skip_mongo=args.skip_mongo,
        skip_qdrant=args.skip_qdrant,
        mongo_uri=args.mongo_uri,
        mongo_db=args.mongo_db,
        qdrant_url=args.qdrant_url,
        qdrant_api_key=args.qdrant_api_key,
    )


if __name__ == "__main__":
    main()
