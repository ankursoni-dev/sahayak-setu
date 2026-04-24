"""
One-time reindex script: swap BAAI/bge-small-en-v1.5 (384-dim, English-centric)
for intfloat/multilingual-e5-base (768-dim, 100 languages including Hindi/Tamil/Telugu).

Usage:
    pip install sentence-transformers qdrant-client python-dotenv
    python scripts/reindex_multilingual.py

The script reads the same schemes.json that the existing ingest.py uses,
re-embeds every chunk with the multilingual model, and upserts into a NEW
Qdrant collection (sahayak_schemes_v2) without touching the live collection.

To go live: set QDRANT_COLLECTION=sahayak_schemes_v2 in your .env or Render env vars.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. Load environment
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parents[1] / ".env")
except ImportError:
    pass  # dotenv optional; env vars must already be set

QDRANT_URL = os.environ.get("QDRANT_URL", "")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
TARGET_COLLECTION = os.environ.get("REINDEX_TARGET_COLLECTION", "sahayak_schemes_v2")
SCHEMAS_PATH = Path(__file__).parent / "data" / "schemes.json"

if not QDRANT_URL:
    sys.exit("ERROR: QDRANT_URL not set. Export it or add to .env.")

# ---------------------------------------------------------------------------
# 2. Load model
# ---------------------------------------------------------------------------
print("Loading intfloat/multilingual-e5-base (~560 MB first run, cached after)…")
from sentence_transformers import SentenceTransformer  # noqa: E402

MODEL = SentenceTransformer("intfloat/multilingual-e5-base")
VECTOR_SIZE = 768


def embed_passage(text: str) -> list[float]:
    """multilingual-e5 requires 'passage: ' prefix for documents."""
    return MODEL.encode(f"passage: {text}", normalize_embeddings=True).tolist()


# ---------------------------------------------------------------------------
# 3. Connect to Qdrant
# ---------------------------------------------------------------------------
from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.models import (  # noqa: E402
    Distance,
    PointStruct,
    VectorParams,
)

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None, timeout=30)

# ---------------------------------------------------------------------------
# 4. (Re)create target collection
# ---------------------------------------------------------------------------
existing = {c.name for c in client.get_collections().collections}
if TARGET_COLLECTION in existing:
    ans = input(f"Collection '{TARGET_COLLECTION}' already exists. Delete and recreate? [y/N]: ")
    if ans.strip().lower() != "y":
        sys.exit("Aborted.")
    client.delete_collection(TARGET_COLLECTION)
    print(f"Deleted existing '{TARGET_COLLECTION}'.")

client.create_collection(
    collection_name=TARGET_COLLECTION,
    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
)
print(f"Created collection '{TARGET_COLLECTION}' (dim={VECTOR_SIZE}, cosine).")

# ---------------------------------------------------------------------------
# 5. Load schemes data
# ---------------------------------------------------------------------------
if not SCHEMAS_PATH.exists():
    sys.exit(f"ERROR: schemes.json not found at {SCHEMAS_PATH}")

rows: list[dict] = json.loads(SCHEMAS_PATH.read_text(encoding="utf-8"))
print(f"Loaded {len(rows)} scheme chunks from {SCHEMAS_PATH}.")

# ---------------------------------------------------------------------------
# 6. Embed + upsert in batches
# ---------------------------------------------------------------------------
BATCH = 16
points: list[PointStruct] = []

for i, row in enumerate(rows):
    text = str(row.get("text") or "")
    meta = row.get("metadata") or {}
    if not text.strip():
        print(f"  [SKIP] row {i}: empty text")
        continue

    vec = embed_passage(text)
    points.append(
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vec,
            payload={
                "scheme": meta.get("scheme", ""),
                "apply_link": meta.get("apply_link", ""),
                "source": meta.get("source", ""),
                "document": text,
            },
        )
    )

    if len(points) >= BATCH:
        client.upsert(collection_name=TARGET_COLLECTION, points=points)
        print(f"  Upserted {i + 1}/{len(rows)} chunks…")
        points = []

if points:
    client.upsert(collection_name=TARGET_COLLECTION, points=points)

count = client.count(TARGET_COLLECTION).count
print(f"\nDone. {count} points in '{TARGET_COLLECTION}'.")
print(f"\nNext step: set  QDRANT_COLLECTION={TARGET_COLLECTION}  in your Render env vars.")
print("Also update GROUNDING_EMBED_MODEL=intfloat/multilingual-e5-base in config if using grounding_service.")
