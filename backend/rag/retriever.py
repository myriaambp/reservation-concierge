"""RAG retriever — top-k restaurant editorial passages by cosine similarity.

Loads the embeddings produced by `backend.rag.ingest` once at module init.
At query time, embeds the query (Vertex if available, else hashed lexical) and
returns top-k passages.

If `embeddings.json` doesn't exist yet, the retriever uses the raw editorial
text and a token-overlap score so the agent stack stays bootable.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from backend.rag.ingest import _doc_text, _hashed_vector, _tokenize, _vertex_embed

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EMBEDDINGS_PATH = _REPO_ROOT / "seed_data" / "embeddings.json"
_RESTAURANTS_PATH = _REPO_ROOT / "seed_data" / "restaurants.json"


_DOCS: list[dict] | None = None
_MATRIX: np.ndarray | None = None
_MODE: str = "uninitialized"


def _ensure_loaded() -> None:
    global _DOCS, _MATRIX, _MODE
    if _DOCS is not None:
        return

    if _EMBEDDINGS_PATH.exists():
        data = json.loads(_EMBEDDINGS_PATH.read_text())
        _DOCS = data["docs"]
        _MODE = data.get("mode", "lexical")
        _MATRIX = np.array([d["embedding"] for d in _DOCS], dtype=np.float32)
        return

    # No ingest done yet — fall back to raw text token-overlap retrieval.
    with _RESTAURANTS_PATH.open() as f:
        restaurants = json.load(f)
    _DOCS = [
        {
            "id": r["id"],
            "text": _doc_text(r),
            "embedding": None,
            "meta": {
                "name": r["name"],
                "cuisine": r["cuisine"],
                "neighborhood": r["neighborhood"],
                "difficulty": r["difficulty"],
                "tags": r.get("tags", []),
            },
        }
        for r in restaurants
    ]
    _MATRIX = None
    _MODE = "tokens-only"


def retrieve(query: str, k: int = 5) -> list[dict[str, Any]]:
    """Return top-k docs. Each dict has {id, text, score, meta}."""
    _ensure_loaded()
    assert _DOCS is not None  # for type-checker; loaded above

    if _MATRIX is not None:
        # Embed the query.
        embs = _vertex_embed([query]) if _MODE == "vertex" else None
        q_vec = (
            np.array(embs[0], dtype=np.float32)
            if embs
            else np.array(_hashed_vector(query), dtype=np.float32)
        )
        q_vec = q_vec / (np.linalg.norm(q_vec) or 1.0)
        # Pre-normalized matrix from ingest.
        scores = _MATRIX @ q_vec
        order = np.argsort(-scores)[:k]
        return [
            {
                "id": _DOCS[i]["id"],
                "text": _DOCS[i]["text"],
                "score": float(scores[i]),
                "meta": _DOCS[i]["meta"],
            }
            for i in order
        ]

    # tokens-only fallback: overlap score.
    q_toks = set(_tokenize(query))
    scored = []
    for d in _DOCS:
        d_toks = set(_tokenize(d["text"]))
        score = len(q_toks & d_toks) / max(1, len(q_toks))
        scored.append((score, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"id": d["id"], "text": d["text"], "score": float(s), "meta": d["meta"]}
        for s, d in scored[:k]
    ]
