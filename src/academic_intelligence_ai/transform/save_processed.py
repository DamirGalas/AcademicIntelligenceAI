"""Save filtered files as structured JSON to data/processed/."""

import json
from datetime import datetime, timezone
from pathlib import Path

from academic_intelligence_ai.load.url_classifier import classify
from academic_intelligence_ai.load.label_documents import get_department, get_relevance
from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.transform.filter.models import KeptFile

logger = get_logger("transform.save_processed")

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def save(kept_files: list[KeptFile]) -> int:
    """Save kept files to data/processed/ as structured JSON.

    Skips files whose URL classifies as not relevant.
    Returns the number of files saved.
    """
    processed_dir = PROJECT_ROOT / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    metadata_cache = _load_all_metadata()
    saved = 0
    skipped_irrelevant = 0

    for entry in kept_files:
        try:
            domain_meta = metadata_cache.get(entry.domain, {})
            file_meta = domain_meta.get(entry.file_path.name, {})
            url = file_meta.get("url", "")

            category = classify(url)
            # blog-post-unclassified passes through here — final label is assigned
            # by label_documents.py using noise scoring on chunk text (load phase)
            if get_relevance(category) == "none" and category != "blog-post-unclassified":
                skipped_irrelevant += 1
                continue

            _save_one(entry, url, category, processed_dir)
            saved += 1
        except Exception as e:
            logger.error("Failed to save %s: %s", entry.file_path.name, e)

    logger.info(
        "Saved %d/%d files to %s (skipped %d not-relevant)",
        saved, len(kept_files), processed_dir, skipped_irrelevant,
    )
    return saved


def _save_one(entry: KeptFile, url: str, category: str, output_dir: Path):
    """Save a single kept file as JSON."""

    # Build output filename: domain__type__original_name.json
    output_name = f"{entry.domain}__{entry.file_type}__{entry.file_path.stem}.json"
    output_path = output_dir / output_name

    payload = {
        "text": entry.clean_text,
        "metadata": {
            "source": entry.domain,
            "file_type": entry.file_type,
            "raw_filename": entry.file_path.name,
            "url": url,
            "category": category,
            "relevance": get_relevance(category),
            "department": get_department(url),
            "text_hash": entry.text_hash,
            "text_length": len(entry.clean_text),
            "processed_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_all_metadata() -> dict[str, dict]:
    """Load metadata.json from each domain into {domain: {filename: meta}}."""
    raw_dir = PROJECT_ROOT / "data" / "raw"
    cache = {}
    for domain_dir in raw_dir.iterdir():
        if not domain_dir.is_dir():
            continue
        meta_path = domain_dir / "metadata.json"
        if meta_path.exists():
            with open(meta_path, encoding="utf-8") as f:
                cache[domain_dir.name] = json.load(f)
    return cache
