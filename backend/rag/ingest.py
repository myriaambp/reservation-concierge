"""RAG ingest — builds restaurant editorial corpus + embeddings.

Run once before deploy:
    python -m backend.rag.ingest

In production, embeds with Vertex AI `text-embedding-005` (GCP-native).
For local dev without GCP, falls back to a hashed-token vector so the system
runs end-to-end without external services. Either way, output is the same JSON
schema, consumed by retriever.py.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

from backend.config import get_settings

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RESTAURANTS_PATH = _REPO_ROOT / "seed_data" / "restaurants.json"
_OUT_PATH = _REPO_ROOT / "seed_data" / "embeddings.json"

_VECTOR_DIM = 384  # arbitrary fallback dim; Vertex returns 768


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _hashed_vector(text: str, dim: int = _VECTOR_DIM) -> list[float]:
    """Lexical fallback: hashed token frequencies, L2-normalized."""
    vec = [0.0] * dim
    for tok in _tokenize(text):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = sum(v * v for v in vec) ** 0.5 or 1.0
    return [v / norm for v in vec]


def _doc_text(r: dict) -> str:
    return " | ".join(
        [
            r["name"],
            r["cuisine"],
            r["neighborhood"],
            r["vibe"],
            " ".join(r.get("tags", [])),
            r["editorial"],
        ]
    )


def _vertex_embed(texts: list[str]) -> list[list[float]] | None:
    """Embed via Vertex text-embedding-005. Returns None on any failure."""
    settings = get_settings()
    if not settings.gcp_project_id:
        return None
    try:
        from google.cloud import aiplatform  # type: ignore
        from vertexai.preview.language_models import TextEmbeddingModel  # type: ignore

        aiplatform.init(
            project=settings.gcp_project_id, location=settings.gcp_region
        )
        model = TextEmbeddingModel.from_pretrained(settings.embedding_model)
        # API takes batches; safest to chunk.
        out: list[list[float]] = []
        for i in range(0, len(texts), 5):
            chunk = texts[i : i + 5]
            embs = model.get_embeddings(chunk)
            out.extend(e.values for e in embs)
        return out
    except Exception as exc:
        print(f"[ingest] Vertex unavailable ({exc}); using lexical fallback.")
        return None


def ingest() -> None:
    with _RESTAURANTS_PATH.open() as f:
        restaurants = json.load(f)

    texts = [_doc_text(r) for r in restaurants]
    embeddings = _vertex_embed(texts)
    mode = "vertex"
    if embeddings is None:
        embeddings = [_hashed_vector(t) for t in texts]
        mode = "lexical"

    docs = []
    for r, emb in zip(restaurants, embeddings):
        docs.append(
            {
                "id": r["id"],
                "text": _doc_text(r),
                "embedding": emb,
                "meta": {
                    "name": r["name"],
                    "cuisine": r["cuisine"],
                    "neighborhood": r["neighborhood"],
                    "difficulty": r["difficulty"],
                    "tags": r.get("tags", []),
                },
            }
        )

    _OUT_PATH.write_text(json.dumps({"mode": mode, "docs": docs}))
    print(f"[ingest] wrote {len(docs)} docs ({mode}) -> {_OUT_PATH}")


if __name__ == "__main__":
    ingest()
