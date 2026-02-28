from academic_intelligence_ai.ingest.run_extract import run as run_extract
from academic_intelligence_ai.transform.html_to_text import run as run_transform
from academic_intelligence_ai.transform.chunker import run as run_chunk
from academic_intelligence_ai.load.load_documents import run as run_load
from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.monitoring.report import print_report

logger = get_logger("main")


def main():
    """Run the full pipeline: extract -> transform -> chunk -> load."""
    logger.info("=== Pipeline START ===")

    steps = [
        ("extract", run_extract),
        ("transform", run_transform),
        ("chunk", run_chunk),
        ("load", run_load),
    ]

    for name, step_fn in steps:
        logger.info("--- Running step: %s ---", name)
        try:
            step_fn()
        except Exception as e:
            logger.error("Step %s failed: %s", name, e)
            logger.error("=== Pipeline ABORTED ===")
            raise

    logger.info("=== Pipeline COMPLETE ===")
    print_report()


if __name__ == "__main__":
    main()
