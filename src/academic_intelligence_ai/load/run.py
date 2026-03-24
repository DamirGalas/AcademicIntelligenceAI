"""Load pipeline orchestrator.

Reads chunked JSON files, stores them in SQLite, generates embeddings,
and builds the FAISS index.
"""

import json
from pathlib import Path

import yaml

from academic_intelligence_ai.ingest.crawler import keep_awake, release_awake
from academic_intelligence_ai.load import embeddings, store
from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.monitoring.pipeline_tracker import PipelineTracker

logger = get_logger("load.run")

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_config() -> dict:
    """Load configuration from config/config.yaml."""
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def run():
    """Execute the full load pipeline."""
    config = load_config()
    load_cfg = config.get("load", {})
    embedding_cfg = config.get("embedding", {})
    vector_cfg = config.get("vector_db", {})
    chunking_cfg = config.get("chunking", {})

    limit = load_cfg.get("limit", 0)
    model_name = embedding_cfg.get("model", "all-MiniLM-L6-v2")
    batch_size = embedding_cfg.get("batch_size", 32)
    dimension = embedding_cfg.get("dimension", 384)
    chunk_size = chunking_cfg.get("chunk_size", 400)
    chunk_overlap = chunking_cfg.get("chunk_overlap", 80)

    index_path = PROJECT_ROOT / vector_cfg.get(
        "index_path", "data/embeddings/faiss_index"
    )
    chunked_dir = PROJECT_ROOT / config.get("paths", {}).get(
        "chunked_data", "data/chunked/"
    )

    description = f"limit={limit}, chunk_size={chunk_size}, chunk_overlap={chunk_overlap}"

    keep_awake()
    try:
        with PipelineTracker("load", description) as tracker:
            # Discover chunked JSON files
            json_files = sorted(chunked_dir.glob("*.json"))
            if not json_files:
                logger.warning("No chunked JSON files found in %s", chunked_dir)
                tracker.record(items_in=0, items_out=0, items_skipped=0)
                return

            if limit > 0:
                json_files = json_files[:limit]
                logger.info("Limit applied: processing %d of available files", limit)

            logger.info("Found %d chunked file(s) to load", len(json_files))

            # Clear existing data (full reload)
            store.clear_all()

            # Insert documents and chunks into SQLite
            all_texts = []
            metadata = []
            doc_count = 0

            for i, file_path in enumerate(json_files, 1):
                payload = json.loads(file_path.read_text(encoding="utf-8"))

                meta = payload["metadata"]
                file_type = meta.get("file_type", "")
                url = meta.get("url", "")
                doc_id = store.insert_document(
                    source=meta["source"],
                    raw_filename=meta["raw_filename"],
                    full_text_length=meta["full_text_length"],
                    processed_at=meta.get("processed_at", ""),
                    file_type=file_type,
                    url=url,
                    text_hash=meta.get("text_hash", ""),
                )
                doc_count += 1

                chunk_ids = store.insert_chunks(
                    doc_id=doc_id,
                    chunks=payload["chunks"],
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )

                for chunk, chunk_id in zip(payload["chunks"], chunk_ids):
                    all_texts.append(chunk["text"])
                    metadata.append({
                        "chunk_id": chunk_id,
                        "doc_id": doc_id,
                        "source": meta["source"],
                        "url": url,
                        "file_type": file_type,
                    })

                print(
                    f"\r  loading docs: {i}/{len(json_files)}  chunks: {len(all_texts)}",
                    end="", flush=True,
                )

            print()
            logger.info("SQLite load complete: %d docs, %d chunks", doc_count, len(all_texts))

            # Detect empty/whitespace-only chunks
            empty_chunks = sum(1 for t in all_texts if not t.strip())
            if empty_chunks > 0:
                logger.warning("Detected %d empty/whitespace-only chunks", empty_chunks)
            tracker.add_metric("empty_chunks", empty_chunks)

            # Generate embeddings
            logger.info("Generating embeddings with model: %s", model_name)
            embeddings_np, failures = embeddings.encode_chunks(
                texts=all_texts,
                model_name=model_name,
                batch_size=batch_size,
                dimension=dimension,
            )

            tracker.add_metric("embedding_failures", failures)
            tracker.add_metric("total_chunks_embedded", len(all_texts) - failures)

            # Build and save FAISS index
            index = embeddings.build_faiss_index(embeddings_np)
            index_size = embeddings.save_index(index, metadata, index_path)

            # Record metrics
            chunk_lengths = [len(t) for t in all_texts]
            avg_chunk_length = sum(chunk_lengths) / len(chunk_lengths) if chunk_lengths else 0
            std_chunk_length = (
                (sum((l - avg_chunk_length) ** 2 for l in chunk_lengths) / len(chunk_lengths)) ** 0.5
                if chunk_lengths else 0
            )
            tracker.add_metric("total_docs", doc_count)
            tracker.add_metric("total_chunks", len(all_texts))
            tracker.add_metric("chunk_size", chunk_size)
            tracker.add_metric("chunk_overlap", chunk_overlap)
            tracker.add_metric("avg_chunk_length", round(avg_chunk_length, 1))
            tracker.add_metric("std_chunk_length", round(std_chunk_length, 1))
            tracker.add_metric("index_size_bytes", index_size)

            logger.info(
                "Load complete: %d docs, %d chunks, %d vectors (dim=%d)",
                doc_count, len(all_texts), index.ntotal, embeddings_np.shape[1],
            )

            tracker.record(
                items_in=len(json_files),
                items_out=len(all_texts) - failures,
                items_skipped=failures,
            )
    finally:
        release_awake()


if __name__ == "__main__":
    run()
