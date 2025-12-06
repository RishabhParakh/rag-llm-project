# backend/vector_store.py

import os
from typing import List, Optional

from config import (
    gemini_client,
    EMBEDDING_MODEL,
    PINECONE_DIMENSION,
    index,
)


def embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    resp = gemini_client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
    )
    return [emb.values for emb in resp.embeddings]


def upsert_vectors(items: List[dict]) -> None:
    if not items:
        print("⚠️ upsert_vectors called with empty items")
        return
    print(f"⬆️  UPSERTING {len(items)} VECTORS INTO PINECONE")
    index.upsert(vectors=items)


def retrieve_texts(
    query: str,
    top_k: int,
    doc_types: List[str],
    file_id: Optional[str] = None,
    allow_fallback: bool = False,
) -> List[str]:
    """
    Retrieve texts from Pinecone using simple metadata filters:
    - doc_type = "resume_chunk" or "coach_qa"
    - optional file_id for per-resume isolation

    If allow_fallback=True and we filtered by file_id but got no matches,
    we retry with only doc_type (used for debug/self-check).
    """
    vecs = embed_texts([query])
    if not vecs:
        print("⚠️ embed_texts returned no vector in retrieve_texts")
        return []
    vec = vecs[0]

    # Build filter
    filter_dict: dict = {}

    if doc_types:
        if len(doc_types) == 1:
            filter_dict["doc_type"] = doc_types[0]          # equality filter
        else:
            filter_dict["doc_type"] = {"$in": doc_types}

    if file_id:
        filter_dict["file_id"] = file_id

    filter_arg = filter_dict or None
    print("🔍 QUERYING PINECONE with filter:", filter_arg)

    res = index.query(
        vector=vec,
        top_k=top_k,
        include_metadata=True,
        filter=filter_arg,
    )

    print("🔍 PRIMARY QUERY MATCHES:", len(res.matches))
    if res.matches:
        print("🧪 SAMPLE METADATA:", res.matches[0].metadata)

    # ✅ Only fallback if we explicitly allow it
    if allow_fallback and not res.matches and file_id and doc_types:
        fallback_filter = {"doc_type": doc_types[0]}
        print("⚠️ No matches with file_id, retrying with filter:", fallback_filter)

        res = index.query(
            vector=vec,
            top_k=top_k,
            include_metadata=True,
            filter=fallback_filter,
        )
        print("🔍 FALLBACK QUERY MATCHES:", len(res.matches))

    if not res.matches:
        return []

    matches = sorted(res.matches, key=lambda m: m.score, reverse=True)
    texts = [m.metadata.get("text", "") for m in matches]

    print("✅ RETURNING", len(texts), "TEXTS")
    return texts



def seed_coach_qa_if_needed() -> None:
    """
    Seed general career-coach Q&A into doc_type='coach_qa' if none exist.
    """
    res = index.query(
        vector=[0.0] * PINECONE_DIMENSION,
        top_k=1,
        include_metadata=True,
        filter={"doc_type": "coach_qa"},   # simple equality filter
    )
    if res.matches:
        print("✅ coach_qa already seeded")
        return

    qa_path = os.path.join(os.path.dirname(__file__), "coach_qa.txt")
    if not os.path.exists(qa_path):
        print("⚠️ coach_qa.txt not found, skipping seed")
        return

    with open(qa_path, "r") as f:
        data = f.read().strip()

    entries = [x.strip().replace("\n", " ") for x in data.split("\n\n") if x.strip()]
    print(f"📚 SEEDING {len(entries)} coach Q&A entries")

    vecs = embed_texts(entries)

    items = []
    for i, (vec, text) in enumerate(zip(vecs, entries)):
        items.append(
            {
                "id": f"coachqa-{i}",
                "values": vec,
                "metadata": {
                    "text": text,
                    "doc_type": "coach_qa",
                },
            }
        )

    index.upsert(vectors=items)
    print("✅ coach_qa seeded")
