import argparse
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()

SCRIPT_DIR = Path(__file__).resolve().parent
SCHEMES_PATH = SCRIPT_DIR / "data" / "schemes.json"
COLLECTION = "sahayak_schemes"

_qdrant: QdrantClient | None = None


def _get_qdrant() -> QdrantClient:
    """Connect to Qdrant only when ingestion runs (not for --dry-run)."""
    global _qdrant
    if _qdrant is not None:
        return _qdrant

    qdrant_url = os.getenv("QDRANT_URL")
    if not qdrant_url:
        print("[ERROR] Missing QDRANT_URL. Set it in .env locally, or rely on Render env for deploy.")
        print("        (Not required for: python scripts/ingest.py --dry-run)")
        sys.exit(1)

    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    _qdrant = QdrantClient(url=qdrant_url, api_key=qdrant_api_key or None)
    _qdrant.set_model("BAAI/bge-small-en-v1.5")
    return _qdrant


def _is_local_host(qdrant_url: str) -> bool:
    try:
        host = (urlparse(qdrant_url).hostname or "").lower()
    except Exception:
        return False
    return host in {"localhost", "127.0.0.1", "::1", "qdrant"}


def _confirm_destructive(qdrant_url: str, *, assume_yes: bool) -> None:
    if assume_yes or _is_local_host(qdrant_url):
        return
    print(f"[WARN] About to DROP collection '{COLLECTION}' at {qdrant_url}.")
    print("       This deletes every chunk in the production knowledge base.")
    answer = input("       Type 'yes' to continue: ").strip().lower()
    if answer != "yes":
        print("[ABORT] Destructive ingest cancelled.")
        sys.exit(1)


def _collection_exists(qdrant) -> bool:
    """Compatibility shim — qdrant-client 1.7.x has no ``collection_exists``."""
    if hasattr(qdrant, "collection_exists"):
        return qdrant.collection_exists(COLLECTION)
    try:
        qdrant.get_collection(COLLECTION)
        return True
    except Exception:
        return False


def recreate_collection() -> None:
    import time
    qdrant = _get_qdrant()
    print("[INFO] Dropping existing collection ...")
    # Best-effort delete — ignore "doesn't exist" errors.
    try:
        qdrant.delete_collection(COLLECTION)
    except Exception as e:
        if "not found" not in str(e).lower() and "doesn't exist" not in str(e).lower():
            print(f"   [WARN] delete_collection raised: {e}")
    # Qdrant Cloud is eventually consistent. Wait for the delete to settle so the
    # subsequent qdrant.add() (which auto-creates) doesn't race the deletion.
    for _ in range(20):
        if not _collection_exists(qdrant):
            break
        time.sleep(0.5)
    # Don't pre-create here — qdrant-client 1.7.x's FastEmbed `add()` wrapper does
    # its own create_collection internally and 409s if we beat it to it. Letting
    # add() handle creation is the path of least resistance with this client version.
    print(f"   [SUCCESS] Collection cleared; ingest will recreate.")


def ensure_collection() -> None:
    qdrant = _get_qdrant()
    if _collection_exists(qdrant):
        return
    qdrant.create_collection(
        collection_name=COLLECTION,
        vectors_config=qdrant.get_fastembed_vector_params(),
    )
    print(f"   [SUCCESS] Created (was missing): {COLLECTION}")


def load_scheme_data() -> list[dict[str, Any]]:
    if not SCHEMES_PATH.is_file():
        print(f"[ERROR] Missing schemes file: {SCHEMES_PATH}")
        sys.exit(1)
    with SCHEMES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _deterministic_id(text: str) -> str:
    """Stable UUID derived from chunk text — re-ingest is idempotent (upsert by ID)."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()[:16]
    return str(uuid.UUID(bytes=digest))


def run_ingestion(*, dry_run: bool = False, recreate: bool = False, assume_yes: bool = False) -> None:
    data = load_scheme_data()
    documents = [item["text"] for item in data]
    metadata = [item["metadata"] for item in data]

    print("\n[STARTUP] SahayakSetu - Definitive Knowledge Lockdown")
    print(f"\n[INFO] Prepared {len(documents)} chunks for ingestion.")

    if dry_run:
        print("[DRY-RUN] No Qdrant connection; Render or local .env not needed for this mode.")
        print(f"   Chunk count: {len(documents)}")
        for i, chunk in enumerate(documents[:3]):
            print(f"   --- chunk {i + 1} ---")
            print(f"   {chunk[:200]}{'...' if len(chunk) > 200 else ''}")
        return

    qdrant_url = os.getenv("QDRANT_URL", "")
    print(f"[INFO] Target: {qdrant_url}")

    qdrant = _get_qdrant()
    if recreate:
        _confirm_destructive(qdrant_url, assume_yes=assume_yes)
        recreate_collection()
    else:
        ensure_collection()

    print(f"\n[INFO] Ingesting {len(data)} chunks ({'recreate' if recreate else 'upsert'})...")
    qdrant.add(
        collection_name=COLLECTION,
        documents=documents,
        metadata=metadata,
        ids=[_deterministic_id(t) for t in documents],
    )
    print("\n[SUCCESS] Repository ready!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest scheme chunks into Qdrant.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print chunk count and first 3 chunks without Qdrant (no env required).",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop the collection before ingest. DESTRUCTIVE — prompts for confirmation on non-local hosts.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt for --recreate against non-local hosts.",
    )
    args = parser.parse_args()
    run_ingestion(dry_run=args.dry_run, recreate=args.recreate, assume_yes=args.yes)


if __name__ == "__main__":
    main()
