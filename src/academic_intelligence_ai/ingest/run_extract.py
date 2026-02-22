import yaml
from pathlib import Path

from academic_intelligence_ai.ingest.fetch_html import fetch_html, save_raw_html
from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.monitoring.pipeline_tracker import PipelineTracker

logger = get_logger("ingest.run_extract")

# Project root: 4 levels up from this file (ingest -> academic_intelligence_ai -> src -> root)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_config() -> dict:
    """Load configuration from config/config.yaml."""
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def run():
    """Run extraction for all enabled sources."""
    with PipelineTracker("extract") as tracker:
        config = load_config()
        sources = config.get("sources", [])

        enabled = [s for s in sources if s.get("enabled", False)]
        logger.info("Found %d enabled source(s) out of %d total", len(enabled), len(sources))

        success_count = 0
        fail_count = 0

        for src in enabled:
            name = src["name"]
            url = src["url"]

            logger.info("Extracting source: %s (%s)", name, url)
            try:
                html = fetch_html(url)
                path = save_raw_html(html, name)
                logger.info("Saved %s (%d bytes)", path, len(html))
                success_count += 1
            except Exception as e:
                logger.error("Failed %s: %s", name, e)
                fail_count += 1

        logger.info("Extraction complete: %d succeeded, %d failed", success_count, fail_count)
        tracker.record(items_in=len(enabled), items_out=success_count, items_skipped=fail_count)


if __name__ == "__main__":
    run()
