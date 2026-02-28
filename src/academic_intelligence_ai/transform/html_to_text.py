import json
import re
from pathlib import Path
from datetime import datetime, timezone

import yaml
from bs4 import BeautifulSoup

from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.monitoring.pipeline_tracker import PipelineTracker

logger = get_logger("transform.html_to_text")

# Project root: 4 levels up (transform -> academic_intelligence_ai -> src -> root)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_config() -> dict:
    """Load configuration from config/config.yaml."""
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def clean_html(html: str, strip_tags: list[str]) -> str:
    """Remove unwanted tags and extract clean text from HTML."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(strip_tags):
        tag.decompose()

    text = soup.get_text(separator=" ")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_source_map(config: dict) -> dict[str, str]:
    """Build a mapping of source name -> purpose from config."""
    return {s["name"]: s.get("purpose", "unknown") for s in config.get("sources", [])}


def extract_metadata(file_path: Path, text: str, purpose: str) -> dict:
    """Build metadata dict from the raw file and extracted text."""
    return {
        "source": file_path.stem,
        "purpose": purpose,
        "raw_filename": file_path.name,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "text_length": len(text),
    }


def process_file(file_path: Path, config: dict, source_map: dict[str, str]) -> bool:
    """Process a single raw HTML file into a structured JSON output.

    Returns True if processed successfully, False if skipped.
    """
    transform_cfg = config.get("transform", {})
    min_text_length = transform_cfg.get("min_text_length", 500)
    strip_tags = transform_cfg.get("strip_tags", ["script", "style", "noscript", "header", "footer", "nav"])

    html = file_path.read_text(encoding="utf-8")
    text = clean_html(html, strip_tags)

    if len(text) < min_text_length:
        logger.warning("Skipping %s: text too short (%d chars, minimum %d)", file_path.name, len(text), min_text_length)
        return False

    purpose = source_map.get(file_path.stem, "unknown")
    metadata = extract_metadata(file_path, text, purpose)

    processed_dir = PROJECT_ROOT / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    output_path = processed_dir / f"{file_path.stem}.json"
    payload = {
        "text": text,
        "metadata": metadata,
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info("Processed %s -> %s (%d chars)", file_path.name, output_path.name, len(text))
    return True


def run():
    """Process all raw HTML files in data/raw/."""
    with PipelineTracker("transform") as tracker:
        config = load_config()
        raw_dir = PROJECT_ROOT / "data" / "raw"

        html_files = list(raw_dir.glob("*.html"))
        if not html_files:
            logger.warning("No HTML files found in %s", raw_dir)
            tracker.record(items_in=0, items_out=0, items_skipped=0)
            return

        source_map = build_source_map(config)
        logger.info("Found %d raw HTML file(s) to process", len(html_files))

        processed = 0
        skipped = 0
        empty_files = 0

        for file_path in html_files:
            try:
                raw_html = file_path.read_text(encoding="utf-8")
                if not raw_html.strip():
                    logger.warning("Empty raw file detected: %s", file_path.name)
                    empty_files += 1
                    skipped += 1
                    continue
                if process_file(file_path, config, source_map):
                    processed += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.error("Failed to process %s: %s", file_path.name, e)
                skipped += 1

        tracker.add_metric("empty_files", empty_files)

        logger.info("Transform complete: %d processed, %d skipped", processed, skipped)
        tracker.record(items_in=len(html_files), items_out=processed, items_skipped=skipped)


if __name__ == "__main__":
    run()
