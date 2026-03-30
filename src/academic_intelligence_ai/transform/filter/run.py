"""Orchestrator — run all filters across raw data and report results."""

from pathlib import Path
from typing import Callable

import yaml

from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.transform.filter.filter_html import filter_html
from academic_intelligence_ai.transform.filter.filter_pdf import filter_pdf
from academic_intelligence_ai.transform.filter.filter_procurement import filter_procurement
from academic_intelligence_ai.transform.filter.models import FilterResult, KeptFile

logger = get_logger("transform.filter.run")

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def load_config() -> dict:
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def run(limit: int = 0) -> tuple[list[KeptFile], dict[str, dict[str, int]]]:
    """Filter raw files across all domains. Limit=0 means no limit.

    Returns (kept_files, stats) where stats is {stats_key: {reason: count}}.
    """
    config = load_config()
    transform_cfg = config.get("transform", {})
    strip_tags = transform_cfg.get(
        "strip_tags", ["script", "style", "noscript", "header", "footer", "nav"]
    )
    min_text_length = transform_cfg.get("min_text_length", 200)
    pdf_max_pages = transform_cfg.get("pdf_max_pages", 500)

    raw_dir = PROJECT_ROOT / "data" / "raw"
    seen_hashes: set[str] = set()
    stats: dict[str, dict[str, int]] = {}
    kept: list[KeptFile] = []

    # --- Run filters (comment out a line to skip a file type) ---
    _run_html_filter(raw_dir, strip_tags, seen_hashes, stats, limit, kept)
    # PDF crawling disabled (html-only crawl) — PDF filter skipped
    # _run_pdf_filter(raw_dir, min_text_length, pdf_max_pages, seen_hashes, stats, limit, kept)
    # _run_docs_filter(raw_dir, ..., seen_hashes, stats, limit, kept)

    _print_report(stats)
    return kept, stats


# --- Per-type filter runners ---


def _run_html_filter(
    raw_dir: Path,
    strip_tags: list[str],
    seen_hashes: set[str],
    stats: dict,
    limit: int,
    kept: list[KeptFile],
):
    """Filter all HTML files across domains."""
    for domain_dir in sorted(raw_dir.iterdir()):
        if not domain_dir.is_dir():
            continue
        _filter_files(
            file_dir=domain_dir / "html",
            glob_pattern="*.html",
            filter_fn=lambda fp: filter_html(fp, strip_tags),
            file_type="html",
            domain=domain_dir.name,
            stats_key=f"{domain_dir.name}/html",
            seen_hashes=seen_hashes,
            stats=stats,
            limit=limit,
            kept=kept,
        )


def _run_pdf_filter(
    raw_dir: Path,
    min_text_length: int,
    pdf_max_pages: int,
    seen_hashes: set[str],
    stats: dict,
    limit: int,
    kept: list[KeptFile],
):
    """Filter all PDF files across domains."""
    for domain_dir in sorted(raw_dir.iterdir()):
        if not domain_dir.is_dir():
            continue
        _filter_files(
            file_dir=domain_dir / "pdf",
            glob_pattern="*.pdf",
            filter_fn=lambda fp: filter_pdf(fp, min_text_length, pdf_max_pages),
            post_filter=filter_procurement,
            file_type="pdf",
            domain=domain_dir.name,
            stats_key=f"{domain_dir.name}/pdf",
            seen_hashes=seen_hashes,
            stats=stats,
            limit=limit,
            kept=kept,
        )


# --- Shared filtering logic ---


def _filter_files(
    file_dir: Path,
    glob_pattern: str,
    filter_fn: Callable[[Path], FilterResult],
    file_type: str,
    domain: str,
    stats_key: str,
    seen_hashes: set[str],
    stats: dict,
    limit: int,
    kept: list[KeptFile],
    post_filter: Callable[[FilterResult], FilterResult] | None = None,
):
    """Run a filter function on all matching files in a directory."""
    if not file_dir.exists():
        return

    files = list(file_dir.glob(glob_pattern))
    if not files:
        return

    reason_counts: dict[str, int] = {}
    stats[stats_key] = reason_counts
    logger.info("[%s] Found %d files", stats_key, len(files))
    print()

    processed = 0
    for file_path in files:
        if limit and processed >= limit:
            break
        try:
            result = filter_fn(file_path)
            processed += 1

            if result.status == "discard":
                reason_counts[result.reason] = reason_counts.get(result.reason, 0) + 1
                continue

            # Apply post-filter (e.g. procurement detection) on kept results
            if post_filter:
                result = post_filter(result)
                if result.status == "discard":
                    reason_counts[result.reason] = reason_counts.get(result.reason, 0) + 1
                    continue

            if result.text_hash in seen_hashes:
                reason_counts["duplicate"] = reason_counts.get("duplicate", 0) + 1
                continue

            seen_hashes.add(result.text_hash)
            reason_counts["keep"] = reason_counts.get("keep", 0) + 1

            kept.append(KeptFile(
                file_path=file_path,
                domain=domain,
                file_type=file_type,
                clean_text=result.clean_text,
                text_hash=result.text_hash,
            ))

        except Exception as e:
            logger.error("[%s] Failed to filter %s: %s", stats_key, file_path.name, e)
            processed += 1

        kept_so_far = reason_counts.get("keep", 0)
        print(f"\r  [{stats_key}] {processed}/{len(files)}  kept: {kept_so_far}", end="", flush=True)


def _print_report(stats: dict[str, dict[str, int]]):
    """Log a summary table of filter results."""
    logger.info("=" * 60)
    logger.info("FILTER REPORT")
    logger.info("=" * 60)

    totals: dict[str, int] = {}

    for key, counts in stats.items():
        total = sum(counts.values())
        parts = " | ".join(f"{r}={c}" for r, c in sorted(counts.items()))
        logger.info("[%s] total=%d | %s", key, total, parts)
        for reason, count in counts.items():
            totals[reason] = totals.get(reason, 0) + count

    grand_total = sum(totals.values())
    logger.info("-" * 60)
    parts = " | ".join(f"{r}={c}" for r, c in sorted(totals.items()))
    logger.info("[TOTAL] total=%d | %s", grand_total, parts)


if __name__ == "__main__":
    kept, stats = run(limit=100)
    logger.info("Kept %d files ready for processing", len(kept))
