"""
KMeans clustering over chunk embeddings with inertia/silhouette scoring for optimal K selection.
Intended for ad-hoc exploratory runs, NOT as part of the main pipeline.
All comments and docstrings must be in English.
"""

import warnings
from pathlib import Path

import faiss
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from academic_intelligence_ai.monitoring.logger import get_logger

logger = get_logger("load.kmeans_cluster")

EMBEDDINGS_INDEX_PATH = Path("data/embeddings/faiss_index")
LABELS_OUT_PATH = Path("data/embeddings/kmeans_labels_K{}.npy")  # K will be formatted in
SAMPLE_SIZE = 20_000
RANDOM_STATE = 42


def load_embeddings_sample(index_path: Path, sample_size: int) -> np.ndarray:
    """Load a random sample of embeddings from a FAISS index."""
    index = faiss.read_index(str(index_path))
    logger.info("Loaded FAISS index with %d vectors, dim=%d", index.ntotal, index.d)
    rng = np.random.default_rng(RANDOM_STATE)
    indices = rng.choice(index.ntotal, size=min(sample_size, index.ntotal), replace=False)
    indices = np.sort(indices)
    embeddings = np.zeros((len(indices), index.d), dtype=np.float32)
    for i, idx in enumerate(indices):
        embeddings[i] = index.reconstruct(int(idx))
        if (i + 1) % (len(indices) // 10) == 0:
            print(f"  Loading vectors: {(i + 1) * 100 // len(indices)}%")
    logger.info("Sampled %d vectors for clustering", len(embeddings))
    return embeddings


def main():
    logger.info("Loading %d random embeddings from FAISS index ...", SAMPLE_SIZE)
    embeddings = load_embeddings_sample(EMBEDDINGS_INDEX_PATH, SAMPLE_SIZE)
    n_samples = embeddings.shape[0]

    min_k = 2
    max_k = 15
    results = []

    logger.info("Running KMeans for K=%d to K=%d...", min_k, max_k)
    for n_clusters in range(min_k, max_k + 1):
        print(f"[{n_clusters - min_k + 1}/{max_k - min_k + 1}] K={n_clusters}: fitting KMeans...")
        logger.info(f"K={n_clusters}: fitting KMeans...")
        kmeans = KMeans(n_clusters=n_clusters, n_init=10, random_state=RANDOM_STATE)
        labels = kmeans.fit_predict(embeddings)
        inertia = kmeans.inertia_
        sil_score = None
        # Silhouette score is valid only if there are 2 or more clusters in use
        try:
            sil_score = silhouette_score(embeddings, labels, random_state=RANDOM_STATE)
        except Exception as e:
            warnings.warn(
                f"Silhouette score could not be calculated for K={n_clusters}: {e}"
            )
        logger.info(
            f"K={n_clusters}: inertia={inertia:.2f}, silhouette_score={sil_score}"
        )
        results.append((n_clusters, inertia, sil_score))
        # Save labels for potential downstream analysis
        np.save(str(LABELS_OUT_PATH).format(n_clusters), labels)

    # Find the best silhouette score (ignore None values)
    silhouette_valid = [(k, s) for (k, _, s) in results if s is not None]
    if silhouette_valid:
        best_k, best_score = max(silhouette_valid, key=lambda x: x[1])
        logger.info(
            f"Optimal number of clusters by silhouette score: K={best_k} (silhouette={best_score:.4f})"
        )
        print(
            f"Optimal number of clusters by silhouette score: K={best_k} (silhouette={best_score:.4f})"
        )
    else:
        logger.warning("Silhouette scoring failed for all K!")

    print("\n--- Results by K ---")
    print("K\tInertia\tSilhouette")
    for k, inertia, sil in results:
        print(f"{k}\t{inertia:.2f}\t{sil}")


if __name__ == "__main__":
    main()
