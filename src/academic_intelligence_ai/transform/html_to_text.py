"""Transform raw HTML files into structured JSON with clean text."""

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


def build_purpose_map(config: dict) -> dict[str, str]:
    """Build a mapping of domain name -> purpose from crawl_domains config."""
    result = {}
    for d in config.get("crawl_domains", []):
        result[d["name"]] = d.get("purpose", "unknown")
    # Also include legacy single-page sources
    for s in config.get("sources", []):
        result[s["name"]] = s.get("purpose", "unknown")
    return result


def process_html_file(
    file_path: Path,
    domain_name: str,
    purpose: str,
    strip_tags: list[str],
    min_text_length: int,
) -> bool:
    """Process a single raw HTML file into a structured JSON output.

    Returns True if processed successfully, False if skipped.
    """
    html = file_path.read_text(encoding="utf-8")
    if not html.strip():
        logger.warning("Empty raw file detected: %s", file_path.name)
        return False

    text = clean_html(html, strip_tags)

    if len(text) < min_text_length:
        logger.warning("Skipping %s: text too short (%d chars, minimum %d)",
                        file_path.name, len(text), min_text_length)
        return False

    processed_dir = PROJECT_ROOT / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Use domain__filename to avoid collisions across domains
    output_name = f"{domain_name}__{file_path.stem}"
    output_path = processed_dir / f"{output_name}.json"

    payload = {
        "text": text,
        "metadata": {
            "source": domain_name,
            "purpose": purpose,
            "raw_filename": file_path.name,
            "file_type": "html",
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "text_length": len(text),
        },
    }

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info("Processed %s -> %s (%d chars)", file_path.name, output_path.name, len(text))
    return True


def run():
    """Process all raw HTML files from crawled domains (data/raw/{domain}/html/)."""
    with PipelineTracker("transform_html") as tracker:
        config = load_config()
        purpose_map = build_purpose_map(config)

        transform_cfg = config.get("transform", {})
        min_text_length = transform_cfg.get("min_text_length", 200)
        strip_tags = transform_cfg.get("strip_tags", ["script", "style", "noscript", "header", "footer", "nav"])

        raw_dir = PROJECT_ROOT / "data" / "raw"
        processed = 0
        skipped = 0
        total = 0

        # Process crawled domain directories: data/raw/{domain}/html/*.html
        for domain_dir in sorted(raw_dir.iterdir()):
            if not domain_dir.is_dir():
                continue

            html_dir = domain_dir / "html"
            if not html_dir.exists():
                continue

            domain_name = domain_dir.name
            purpose = purpose_map.get(domain_name, "unknown")
            html_files = list(html_dir.glob("*.html"))

            logger.info("Found %d HTML file(s) for domain: %s", len(html_files), domain_name)
            total += len(html_files)

            for file_path in html_files:
                try:
                    if process_html_file(file_path, domain_name, purpose, strip_tags, min_text_length):
                        processed += 1
                    else:
                        skipped += 1
                except Exception as e:
                    logger.error("Failed to process %s: %s", file_path.name, e)
                    skipped += 1

        # Also process any legacy flat HTML files in data/raw/*.html
        legacy_files = list(raw_dir.glob("*.html"))
        if legacy_files:
            logger.info("Found %d legacy HTML file(s) in data/raw/", len(legacy_files))
            total += len(legacy_files)
            for file_path in legacy_files:
                try:
                    domain_name = file_path.stem
                    purpose = purpose_map.get(domain_name, "unknown")
                    if process_html_file(file_path, domain_name, purpose, strip_tags, min_text_length):
                        processed += 1
                    else:
                        skipped += 1
                except Exception as e:
                    logger.error("Failed to process %s: %s", file_path.name, e)
                    skipped += 1

        logger.info("HTML transform complete: %d processed, %d skipped out of %d total",
                     processed, skipped, total)
        tracker.record(items_in=total, items_out=processed, items_skipped=skipped)


if __name__ == "__main__":
    run()
