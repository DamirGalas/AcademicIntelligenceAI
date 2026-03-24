# FAISS is used only in this module. All vector index operations
# (build, save, load) must stay here to keep engine swappable.

"""Embedding generation and FAISS index management."""

import pickle
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from academic_intelligence_ai.monitoring.logger import get_logger

logger = get_logger("load.embeddings")


def encode_chunks(
    texts: list[str],
    model_name: str,
    batch_size: int,
    dimension: int,
) -> tuple[np.ndarray, int]:
    """Encode texts into embeddings using a sentence-transformer model.

    Args:
        texts: Chunk texts to encode.
        model_name: HuggingFace model name.
        batch_size: Number of texts per encoding batch.
        dimension: Expected embedding dimension (used for zero-vector fallback).

    Returns:
        Tuple of (embeddings array [N x dimension], number of failures).
    """
    logger.info("Loading embedding model: %s", model_name)
    model = SentenceTransformer(model_name)

    all_embeddings = []
    failures = 0
    total_batches = (len(texts) + batch_size - 1) // batch_size

    logger.info(
        "Encoding %d chunks (batch_size=%d, batches=%d)", len(texts), batch_size, total_batches
    )
    for batch_num, i in enumerate(range(0, len(texts), batch_size), 1):
        batch = texts[i : i + batch_size]
        pct = batch_num / total_batches * 100
        print(f"\r  embedding: {batch_num}/{total_batches} batches  {pct:.1f}%  ({i + len(batch)}/{len(texts)} chunks)", end="", flush=True)
        try:
            # E5 models require "passage: " prefix for indexed documents
            prefixed = [f"passage: {t}" for t in batch]
            vectors = model.encode(prefixed, show_progress_bar=False)
            all_embeddings.append(np.array(vectors).astype("float32"))
        except Exception as e:
            logger.error(
                "Embedding failed for batch %d-%d: %s",
                i, i + len(batch), e,
            )
            failures += len(batch)
            all_embeddings.append(
                np.zeros((len(batch), dimension), dtype="float32")
            )

    if failures > 0:
        logger.warning(
            "ALERT: %d chunks failed embedding (out of %d total)",
            failures, len(texts),
        )

    print()
    embeddings = np.vstack(all_embeddings).astype("float32")
    return embeddings, failures


def build_faiss_index(embeddings: np.ndarray) -> faiss.Index:
    """Build a FAISS inner-product index from L2-normalized embeddings."""
    faiss.normalize_L2(embeddings)
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    logger.info(
        "FAISS index built: %d vectors, dim=%d",
        index.ntotal, embeddings.shape[1],
    )
    return index


def save_index(
    index: faiss.Index,
    metadata: list[dict],
    index_path: Path,
):
    """Save FAISS index and metadata pickle to disk.

    Args:
        index: The FAISS index to persist.
        metadata: List of dicts (chunk_id, doc_id, source, url, file_type)
                  aligned with the index vectors.
        index_path: Path for the FAISS index file.
                    Metadata is saved as <index_path>.parent / metadata.pkl.
    """
    index_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(index_path))

    meta_path = index_path.parent / "metadata.pkl"
    meta_path.write_bytes(pickle.dumps(metadata))

    index_size = index_path.stat().st_size
    logger.info(
        "Saved FAISS index (%d bytes) and metadata (%d entries) to %s",
        index_size, len(metadata), index_path.parent,
    )
    return index_size
