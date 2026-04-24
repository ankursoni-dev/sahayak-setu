import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient

__test__ = False

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
qdrant.set_model("BAAI/bge-small-en-v1.5")


def test_search(query: str):
    print(f"\n[TESTING] Query: '{query}'")
    results = qdrant.query(collection_name="sahayak_schemes", query_text=query, limit=3)

    confident_results = [r for r in results if r.score > 0.2]

    if not confident_results:
        print("[WARNING] No confident matches found (Score < 0.2)")

    for i, res in enumerate(confident_results):
        print(f"\nResult {i + 1} [Score: {res.score:.4f}]")
        print(f"Scheme: {res.metadata.get('scheme', 'Unknown')}")
        print(f"Snippet: {res.document[:100]}...")


def test_off_topic_no_confident_match():
    """Deliberately off-topic query should not produce confident RAG matches."""
    query = "what is photosynthesis"
    print(f"\n[TESTING] Off-topic query: '{query}'")
    results = qdrant.query(collection_name="sahayak_schemes", query_text=query, limit=3)
    top = max((r.score for r in results), default=0.0)
    assert top < 0.2, f"Expected no confident match (score < 0.2), got top score {top}"
    print(f"[OK] Top score {top:.4f} < 0.2 — no confident scheme match as expected.")


if __name__ == "__main__":
    test_search("Tell me about PM Kisan benefits")
    test_search("Ayushman Bharat card kaise banaye?")
    test_off_topic_no_confident_match()
