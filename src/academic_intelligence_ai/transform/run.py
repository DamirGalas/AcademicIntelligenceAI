"""Transform orchestrator — filter, save, and chunk processed results."""

import argparse

from academic_intelligence_ai.ingest.crawler import keep_awake, release_awake
from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.monitoring.pipeline_tracker import PipelineTracker
from academic_intelligence_ai.monitoring.stats_db import (
    get_latest_transform_run_id,
    save_filter_stats,
)
from academic_intelligence_ai.transform.chunker import run as run_chunker
from academic_intelligence_ai.transform.filter.run import run as run_filters
from academic_intelligence_ai.transform.save_processed import save

logger = get_logger("transform.run")


def run(limit: int = 0, fresh: bool = False):
    """Run the full transform pipeline: filter → save → chunk.

    Args:
        limit: Max number of raw files to process (0 = all).
        fresh: If True, reprocess all files even if output already exists.
               Use when transform logic has changed (e.g. new transliteration,
               title injection, or chunking strategy).
    """
    keep_awake()
    try:
        with PipelineTracker("transform", "baseline") as tracker:
            # Step 1: Filter raw files
            kept, filter_stats = run_filters(limit=limit)
            logger.info("Filter complete: %d files kept", len(kept))

            # Step 2: Save kept files as structured JSON
            saved = save(kept, fresh=fresh)
            logger.info("Saved %d files to data/processed/", saved)

            # Step 3: Chunk processed files for embedding
            total_chunks = run_chunker(fresh=fresh)
            logger.info("Transform complete: %d chunks in data/chunked/", total_chunks)

            # Record pipeline tracking
            total_raw = sum(sum(c.values()) for c in filter_stats.values())
            tracker.record(
                items_in=total_raw, items_out=len(kept), items_skipped=total_raw - len(kept)
            )
            tracker.add_metric("saved_processed", saved)
            tracker.add_metric("total_chunks", total_chunks)
    finally:
        release_awake()

    # Persist filter breakdown (needs run_id from tracker)
    # PipelineTracker writes the run on __exit__, so we query for it after
    run_id = get_latest_transform_run_id()
    if run_id and filter_stats:
        save_filter_stats(run_id, filter_stats)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0,
                        help="Max files to process (0 = all)")
    parser.add_argument("--fresh", action="store_true", default=False,
                        help="Reprocess all files, ignoring existing output")
    args = parser.parse_args()
    run(limit=args.limit, fresh=args.fresh)
