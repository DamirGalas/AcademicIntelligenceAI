"""Extract text from downloaded PDF files and produce structured JSON output."""

import json
from pathlib import Path
from datetime import datetime, timezone

import yaml
import pymupdf

from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.monitoring.pipeline_tracker import PipelineTracker

logger = get_logger("transform.pdf_to_text")

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_config() -> dict:
    """Load configuration from config/config.yaml."""
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract all text from a PDF file using PyMuPDF."""
    doc = pymupdf.open(str(pdf_path))
    pages = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            pages.append(text)
    doc.close()
    return "\n\n".join(pages)


def build_purpose_map(config: dict) -> dict[str, str]:
    """Map domain name -> purpose from crawl_domains config."""
    return {
        d["name"]: d.get("purpose", "unknown")
        for d in config.get("crawl_domains", [])
    }


def process_pdf(pdf_path: Path, domain_name: str, purpose: str, min_text_length: int) -> bool:
    """Process a single PDF file into a structured JSON output.

    Returns True if processed successfully, False if skipped.
    """
    text = extract_pdf_text(pdf_path)

    if len(text) < min_text_length:
        logger.warning(
            "Skipping %s: text too short (%d chars, minimum %d)",
            pdf_path.name, len(text), min_text_length,
        )
        return False

    processed_dir = PROJECT_ROOT / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Use domain__filename as the output name to avoid collisions
    output_name = f"{domain_name}__pdf__{pdf_path.stem}"
    output_path = processed_dir / f"{output_name}.json"

    payload = {
        "text": text,
        "metadata": {
            "source": domain_name,
            "purpose": purpose,
            "raw_filename": pdf_path.name,
            "file_type": "pdf",
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "text_length": len(text),
        },
    }

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info("Processed PDF %s -> %s (%d chars)", pdf_path.name, output_path.name, len(text))
    return True


def run():
    """Process all PDF files from crawled domains."""
    with PipelineTracker("transform_pdf") as tracker:
        config = load_config()
        purpose_map = build_purpose_map(config)
        min_text_length = config.get("transform", {}).get("min_text_length", 200)

        raw_dir = PROJECT_ROOT / "data" / "raw"
        processed = 0
        skipped = 0
        total = 0

        # Iterate over domain directories
        for domain_dir in sorted(raw_dir.iterdir()):
            if not domain_dir.is_dir():
                continue

            pdf_dir = domain_dir / "pdf"
            if not pdf_dir.exists():
                continue

            domain_name = domain_dir.name
            purpose = purpose_map.get(domain_name, "unknown")
            pdf_files = list(pdf_dir.glob("*.pdf"))

            logger.info("Found %d PDF(s) for domain: %s", len(pdf_files), domain_name)
            total += len(pdf_files)

            for pdf_path in pdf_files:
                try:
                    if process_pdf(pdf_path, domain_name, purpose, min_text_length):
                        processed += 1
                    else:
                        skipped += 1
                except Exception as e:
                    logger.error("Failed to process PDF %s: %s", pdf_path.name, e)
                    skipped += 1

        logger.info("PDF transform complete: %d processed, %d skipped out of %d total",
                     processed, skipped, total)
        tracker.record(items_in=total, items_out=processed, items_skipped=skipped)


if __name__ == "__main__":
    run()
