"""Save filtered files as structured JSON to data/processed/."""

import html as html_lib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from academic_intelligence_ai.load.url_classifier import classify
from academic_intelligence_ai.load.label_documents import get_department, get_relevance
from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.transform.filter.models import KeptFile
from academic_intelligence_ai.utils.text import transliterate

logger = get_logger("transform.save_processed")

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_base_urls() -> dict[str, str]:
    """Load domain -> base_url mapping from config.yaml."""
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return {d["name"]: d["base_url"] for d in config.get("crawl_domains", [])}


def _reconstruct_url(domain: str, raw_filename: str, base_urls: dict[str, str]) -> str:
    """Reconstruct a URL from the raw filename and domain base URL.

    Crawler saves files as {slug}.html where slug = url_path.replace('/', '__').
    Example: o-fakultetu__uprava.html -> https://www.pmf.uns.ac.rs/o-fakultetu/uprava/
    """
    base_url = base_urls.get(domain, "")
    if not base_url:
        return ""
    stem = Path(raw_filename).stem
    path = stem.replace("__", "/")
    return base_url.rstrip("/") + "/" + path + "/"


def _extract_page_title(file_path: Path, file_type: str) -> str:
    """Extract the page-specific title from a raw HTML file.

    Returns the part before the site-name separator (e.g. '–', '|', '>').
    Returns empty string for non-HTML files or on any failure.
    """
    if file_type != "html":
        return ""
    try:
        content = file_path.read_text(encoding="utf-8")
        m = re.search(r"<title[^>]*>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
        if not m:
            return ""
        full_title = html_lib.unescape(m.group(1).strip())
        if not full_title:
            return ""
        # Strip the repeated site-name suffix that follows the separator
        for sep in [" \u2013 ", " \u2014 ", " | ", " > ", " - "]:
            if sep in full_title:
                return full_title.split(sep)[0].strip()
        return full_title
    except Exception:
        return ""


def save(kept_files: list[KeptFile], fresh: bool = False) -> int:
    """Save kept files to data/processed/ as structured JSON.

    Skips files whose URL classifies as not relevant.
    When fresh=False, skips files that already have an output in data/processed/.
    Returns the number of files saved.
    """
    processed_dir = PROJECT_ROOT / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    metadata_cache = _load_all_metadata()
    base_urls = _load_base_urls()
    saved = 0
    skipped_irrelevant = 0
    skipped_existing = 0

    for entry in kept_files:
        try:
            output_name = f"{entry.domain}__{entry.file_type}__{entry.file_path.stem}.json"
            output_path = processed_dir / output_name

            # Resume: skip if already processed and fresh mode is off
            if not fresh and output_path.exists():
                skipped_existing += 1
                continue

            domain_meta = metadata_cache.get(entry.domain, {})
            file_meta = domain_meta.get(entry.file_path.name, {})
            url = file_meta.get("url", "")

            # Fallback: reconstruct URL from filename if metadata.json didn't have it
            if not url and entry.file_type == "html":
                url = _reconstruct_url(entry.domain, entry.file_path.name, base_urls)
                if url:
                    logger.debug("Reconstructed URL for %s: %s", entry.file_path.name, url)

            category = classify(url)
            if get_relevance(category) == "none" and category != "blog-post-unclassified":
                skipped_irrelevant += 1
                continue

            _save_one(entry, url, category, output_path)
            saved += 1
        except Exception as e:
            logger.error("Failed to save %s: %s", entry.file_path.name, e)

        total = len(kept_files)
        print(f"\r  saving: {saved + skipped_irrelevant + skipped_existing}/{total}  saved: {saved}", end="", flush=True)

    print()
    logger.info(
        "Saved %d/%d files to %s (skipped %d not-relevant, %d already exist)",
        saved, len(kept_files), processed_dir, skipped_irrelevant, skipped_existing,
    )
    return saved


def _save_one(entry: KeptFile, url: str, category: str, output_path: Path):
    """Save a single kept file as structured JSON with transliteration and title."""
    page_title = _extract_page_title(entry.file_path, entry.file_type)

    # Transliterate Cyrillic text to Latin for consistent embedding
    clean_text = transliterate(entry.clean_text)
    if page_title:
        page_title = transliterate(page_title)

    payload = {
        "text": clean_text,
        "metadata": {
            "source": entry.domain,
            "file_type": entry.file_type,
            "raw_filename": entry.file_path.name,
            "url": url,
            "category": category,
            "relevance": get_relevance(category),
            "department": get_department(url),
            "text_hash": entry.text_hash,
            "text_length": len(clean_text),
            "page_title": page_title,
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
