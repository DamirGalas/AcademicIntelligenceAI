"""Transform orchestrator — filter, save, and chunk processed results."""

from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.transform.chunker import run as run_chunker
from academic_intelligence_ai.transform.filter.run import run as run_filters
from academic_intelligence_ai.transform.save_processed import save

logger = get_logger("transform.run")


def run(limit: int = 0):
    """Run the full transform pipeline: filter → save → chunk."""
    logger.info("Starting transform pipeline (limit=%d)", limit)

    # Step 1: Filter raw files
    kept = run_filters(limit=limit)
    logger.info("Filter complete: %d files kept", len(kept))

    # Step 2: Save kept files as structured JSON
    saved = save(kept)
    logger.info("Saved %d files to data/processed/", saved)

    # Step 3: Chunk processed files for embedding
    total_chunks = run_chunker()
    logger.info("Transform complete: %d chunks in data/chunked/", total_chunks)


if __name__ == "__main__":
    run(limit=0)
