"""
Compute silhouette scores for existing KMeans label files.
Temporary exploratory script — not part of the pipeline.
"""

from pathlib import Path

import faiss
import numpy as np
from sklearn.metrics import silhouette_score

EMBEDDINGS_INDEX_PATH = Path("data/embeddings/faiss_index")
LABELS_DIR = Path("data/embeddings")
SAMPLE_SIZE = 10_000


def load_embeddings(index_path: Path) -> np.ndarray:
    index = faiss.read_index(str(index_path))
    print(f"Loaded {index.ntotal} vectors (dim={index.d})")
    embeddings = np.zeros((index.ntotal, index.d), dtype=np.float32)
    for i in range(index.ntotal):
        embeddings[i] = index.reconstruct(i)
    return embeddings


def main():
    embeddings = load_embeddings(EMBEDDINGS_INDEX_PATH)

    print(f"\nSilhouette scores (sample_size={SAMPLE_SIZE})\n")
    print(f"{'K':<5} {'Silhouette':>12}")
    print("-" * 20)

    results = []
    for k in range(2, 16):
        label_path = LABELS_DIR / f"kmeans_labels_K{k}.npy"
        if not label_path.exists():
            print(f"{k:<5} {'missing':>12}")
            continue
        labels = np.load(label_path)
        # Labels may have been generated on a subset — match embeddings to label count
        emb_subset = embeddings[:len(labels)]
        score = silhouette_score(emb_subset, labels, sample_size=SAMPLE_SIZE, random_state=42)
        results.append((k, score))
        print(f"{k:<5} {score:>12.4f}")

    if results:
        best_k, best_score = max(results, key=lambda x: x[1])
        print(f"\nBest K = {best_k} (silhouette = {best_score:.4f})")


if __name__ == "__main__":
    main()
