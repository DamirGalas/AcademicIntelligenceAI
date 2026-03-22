"""BFS web crawler that downloads HTML pages, PDF files, and Office documents from configured domains."""

import argparse
import ctypes
import json
import platform
import re
import sys
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

import requests
import yaml
from bs4 import BeautifulSoup
from datetime import datetime, timezone

from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.monitoring.pipeline_tracker import PipelineTracker


def keep_awake():
    """Prevent Windows from going to sleep while crawling."""
    if platform.system() == "Windows":
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ES_DISPLAY_REQUIRED = 0x00000002
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        )


def release_awake():
    """Allow Windows to sleep again after crawling."""
    if platform.system() == "Windows":
        ES_CONTINUOUS = 0x80000000
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)

logger = get_logger("ingest.crawler")

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_config() -> dict:
    """Load configuration from config/config.yaml."""
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def slugify_url(url: str) -> str:
    """Convert a URL into a safe filename.

    Example: https://www.pmf.uns.ac.rs/vesti/page/2/ -> vesti__page__2
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        path = "index"
    # Replace path separators with double underscore
    slug = path.replace("/", "__")
    # Remove query string characters that are not filename-safe
    if parsed.query:
        safe_query = re.sub(r"[^\w\-.]", "_", parsed.query)
        slug = f"{slug}__{safe_query}"
    # Limit length
    if len(slug) > 200:
        slug = slug[:200]
    return slug


def is_same_domain(url: str, base_url: str) -> bool:
    """Check if a URL belongs to the same domain as the base URL."""
    return urlparse(url).netloc == urlparse(base_url).netloc


def should_skip(url: str, skip_extensions: list[str]) -> bool:
    """Check if URL points to a file type we want to skip."""
    parsed = urlparse(url)
    path_lower = parsed.path.lower()
    return any(path_lower.endswith(ext) for ext in skip_extensions)


def is_pdf_url(url: str) -> bool:
    """Check if URL points to a PDF file."""
    return urlparse(url).path.lower().endswith(".pdf")


DOC_EXTENSIONS = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}


def is_doc_url(url: str) -> bool:
    """Check if URL points to an Office document."""
    path_lower = urlparse(url).path.lower()
    return any(path_lower.endswith(ext) for ext in DOC_EXTENSIONS)


def normalize_url(url: str) -> str:
    """Normalize a URL by removing fragment and trailing whitespace."""
    url = url.strip()
    url, _ = urldefrag(url)
    # Remove trailing slash inconsistency for dedup (but keep root slash)
    return url


def extract_links(html: str, page_url: str) -> list[str]:
    """Extract all href links from HTML content."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absolute = urljoin(page_url, href)
        links.append(normalize_url(absolute))
    return links


def fetch_robots_txt(base_url: str, session: requests.Session, timeout: int) -> set[str]:
    """Fetch robots.txt and return set of disallowed paths (simple parser)."""
    disallowed = set()
    robots_url = urljoin(base_url, "/robots.txt")
    try:
        resp = session.get(robots_url, timeout=timeout)
        if resp.status_code == 200:
            for line in resp.text.splitlines():
                line = line.strip()
                if line.lower().startswith("disallow:"):
                    path = line.split(":", 1)[1].strip()
                    if path:
                        disallowed.add(path)
            logger.info("robots.txt: %d disallowed paths for %s", len(disallowed), base_url)
    except Exception:
        logger.debug("No robots.txt found for %s", base_url)
    return disallowed


def is_disallowed(url: str, disallowed_paths: set[str]) -> bool:
    """Check if URL path matches any disallowed pattern from robots.txt."""
    path = urlparse(url).path
    return any(path.startswith(d) for d in disallowed_paths)


def _guess_doc_extension(content_type: str) -> str:
    """Guess file extension from Content-Type header for Office documents."""
    ct = content_type.lower()
    if "spreadsheetml" in ct or "ms-excel" in ct:
        return ".xlsx" if "openxmlformats" in ct else ".xls"
    if "presentationml" in ct or "ms-powerpoint" in ct:
        return ".pptx" if "openxmlformats" in ct else ".ppt"
    if "wordprocessingml" in ct or "msword" in ct:
        return ".docx" if "openxmlformats" in ct else ".doc"
    return ".doc"


def _build_file_metadata(url: str, resp: requests.Response, file_type: str) -> dict:
    """Build metadata entry for a downloaded file."""
    return {
        "url": url,
        "content_type": resp.headers.get("Content-Type", ""),
        "last_modified": resp.headers.get("Last-Modified", ""),
        "file_type": file_type,
        "crawled_at": datetime.now(timezone.utc).isoformat(),
        "content_length": len(resp.content),
    }


def _save_metadata(metadata: dict, metadata_path: Path) -> None:
    """Persist metadata dict to disk."""
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _print_progress(domain_name: str, stats: dict) -> None:
    """Print a single-line progress bar to stdout, overwriting the previous line."""
    line = (
        f"[{domain_name}]  visited: {stats['pages_visited']:>5}  "
        f"HTML: {stats['html_saved']:>4}  "
        f"skipped: {stats['skipped']:>4}  "
        f"errors: {stats['errors']:>3}"
    )
    print(f"\r{line}", end="", flush=True)


def crawl_domain(
    domain_name: str,
    base_url: str,
    config: dict,
    fresh: bool = False,
    html_only: bool = False,
    dry_run: bool = False,
) -> dict:
    """Crawl a single domain using BFS. Returns stats dict.

    Downloads HTML pages to data/raw/{domain_name}/html/
    Downloads PDF files to data/raw/{domain_name}/pdf/
    Downloads Office docs to data/raw/{domain_name}/docs/

    Args:
        fresh: Disable resume mode. Start BFS from scratch and overwrite existing HTML.
        html_only: Skip PDF and Office document downloads regardless of config.
        dry_run: Traverse and fetch pages but do not write any files to disk.
    """
    crawler_cfg = config.get("crawler", {})
    delay = crawler_cfg.get("delay_seconds", 0.5)
    max_pages = crawler_cfg.get("max_pages_per_domain", 1000)
    timeout = crawler_cfg.get("request_timeout", 15)
    user_agent = crawler_cfg.get("user_agent", "AcademicIntelligenceAI/0.1")
    download_pdfs = crawler_cfg.get("download_pdfs", True)
    download_docs = crawler_cfg.get("download_docs", True)
    max_pdf_mb = crawler_cfg.get("max_pdf_size_mb", 50)
    respect_robots = crawler_cfg.get("respect_robots_txt", True)
    skip_extensions = crawler_cfg.get("skip_extensions", [])

    # html_only flag overrides config
    if html_only:
        download_pdfs = False
        download_docs = False
        logger.info("html_only mode: PDF and doc downloads disabled")

    if dry_run:
        logger.info("dry_run mode: no files will be written")

    # Output directories
    domain_dir = PROJECT_ROOT / "data" / "raw" / domain_name
    html_dir = domain_dir / "html"
    pdf_dir = domain_dir / "pdf"
    docs_dir = domain_dir / "docs"
    html_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    # Rich metadata: filename -> {url, content_type, last_modified, crawled_at, ...}
    metadata_path = domain_dir / "metadata.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    else:
        metadata = {}

    # Migrate legacy url_map.json if it exists
    legacy_map_path = domain_dir / "url_map.json"
    if legacy_map_path.exists() and not metadata:
        legacy = json.loads(legacy_map_path.read_text(encoding="utf-8"))
        for filename, url in legacy.items():
            metadata[filename] = {"url": url, "content_type": "", "last_modified": "",
                                  "file_type": "pdf" if filename.endswith(".pdf") else "html",
                                  "crawled_at": "", "content_length": 0}
        logger.info("Migrated %d entries from url_map.json -> metadata.json", len(legacy))

    # Session for connection reuse
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    session.verify = False  # Some PMF subdomains have SSL issues

    # Suppress SSL warnings for these academic sites
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # robots.txt
    disallowed = set()
    if respect_robots:
        disallowed = fetch_robots_txt(base_url, session, timeout)

    # BFS state
    visited: set[str] = set()
    queue: deque[str] = deque()
    queue.append(normalize_url(base_url))

    stats = {"html_saved": 0, "pdf_saved": 0, "docs_saved": 0, "pages_visited": 0,
             "errors": 0, "skipped": 0, "resumed": 0}

    queue_path = domain_dir / "queue.json"

    # Resume support: skipped entirely when --fresh is set
    if not fresh:
        existing_html = list(html_dir.glob("*.html"))
        existing_pdf = {p.stem for p in pdf_dir.glob("*.pdf")}
        if existing_html:
            logger.info("Resume mode: found %d existing HTML, %d existing PDF files",
                         len(existing_html), len(existing_pdf))
            if metadata_path.exists():
                try:
                    with open(metadata_path, encoding="utf-8") as f:
                        existing_meta = json.load(f)
                    visited.update(existing_meta.keys())
                    metadata.update(existing_meta)
                    stats["resumed"] = len(existing_meta)
                    logger.info("Resume: loaded %d visited URLs from metadata.json", len(visited))
                except Exception:
                    pass
            if queue_path.exists():
                try:
                    with open(queue_path, encoding="utf-8") as f:
                        saved_queue = json.load(f)
                    queue = deque(u for u in saved_queue if u not in visited)
                    logger.info("Resume: restored %d pending URLs from queue.json", len(queue))
                except Exception:
                    pass
            # Clear the initial base_url seed — we'll rebuild queue from saved state or frontier
            queue.clear()
            if not queue:
                # No saved queue: reconstruct frontier from most recently crawled HTML files.
                # Sort by mtime descending and parse the newest 300 — they were at the BFS edge.
                frontier_files = sorted(existing_html, key=lambda p: p.stat().st_mtime, reverse=True)[:300]
                logger.info("Resume: reconstructing frontier from %d recent HTML files", len(frontier_files))
                for html_file in frontier_files:
                    try:
                        content = html_file.read_text(encoding="utf-8")
                        for link in extract_links(content, base_url):
                            normalized = normalize_url(link)
                            if is_same_domain(normalized, base_url) and normalized not in visited:
                                queue.append(normalized)
                    except Exception:
                        pass
                logger.info("Resume: frontier queue seeded with %d URLs", len(queue))
    else:
        logger.info("Fresh mode: ignoring existing files, starting BFS from scratch")

    logger.info("Starting crawl: %s (%s), max_pages=%s, queue_size=%d",
                domain_name, base_url,
                max_pages if max_pages else "unlimited",
                len(queue))

    while queue and (max_pages == 0 or stats["pages_visited"] < max_pages):
        url = queue.popleft()

        if url in visited:
            continue
        visited.add(url)

        if not is_same_domain(url, base_url):
            continue

        if disallowed and is_disallowed(url, disallowed):
            stats["skipped"] += 1
            continue

        if should_skip(url, skip_extensions):
            stats["skipped"] += 1
            continue

        # Handle PDF downloads
        if is_pdf_url(url):
            if not download_pdfs:
                stats["skipped"] += 1
                continue
            slug = slugify_url(url)
            if not slug.endswith(".pdf"):
                slug += ".pdf"
            pdf_path = pdf_dir / slug
            if pdf_path.exists():
                stats["skipped"] += 1
                stats["pages_visited"] += 1
                continue
            try:
                resp = session.get(url, timeout=timeout, stream=True)
                resp.raise_for_status()

                content_length = resp.headers.get("Content-Length")
                if content_length and int(content_length) > max_pdf_mb * 1024 * 1024:
                    logger.warning("Skipping large PDF (%s MB): %s",
                                   int(content_length) // (1024 * 1024), url)
                    stats["skipped"] += 1
                    continue

                content = resp.content
                if not dry_run:
                    pdf_path.write_bytes(content)
                    metadata[pdf_path.name] = _build_file_metadata(url, resp, "pdf")
                stats["pdf_saved"] += 1
                logger.info("PDF saved: %s (%d KB)", pdf_path.name, len(content) // 1024)
            except Exception as e:
                logger.error("Failed to download PDF %s: %s", url, e)
                stats["errors"] += 1
            stats["pages_visited"] += 1
            _print_progress(domain_name, stats)
            time.sleep(delay)
            continue

        # Handle Office document downloads
        if is_doc_url(url):
            if not download_docs:
                stats["skipped"] += 1
                continue
            slug = slugify_url(url)
            # Preserve original extension
            ext = Path(urlparse(url).path).suffix.lower()
            if not slug.endswith(ext):
                slug += ext
            doc_path = docs_dir / slug
            if doc_path.exists():
                stats["skipped"] += 1
                stats["pages_visited"] += 1
                continue
            try:
                resp = session.get(url, timeout=timeout)
                resp.raise_for_status()
                if not dry_run:
                    doc_path.write_bytes(resp.content)
                    metadata[doc_path.name] = _build_file_metadata(url, resp, ext.lstrip("."))
                stats["docs_saved"] += 1
                logger.info("Doc saved: %s (%d KB)", doc_path.name, len(resp.content) // 1024)
            except Exception as e:
                logger.error("Failed to download doc %s: %s", url, e)
                stats["errors"] += 1
            stats["pages_visited"] += 1
            _print_progress(domain_name, stats)
            time.sleep(delay)
            continue

        # Skip HTML if already downloaded — unless fresh mode is active
        slug = slugify_url(url)
        html_path = html_dir / f"{slug}.html"
        if html_path.exists() and not fresh:
            stats["skipped"] += 1
            stats["pages_visited"] += 1
            continue

        # Fetch HTML page
        try:
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                # PDF served without .pdf extension
                if "application/pdf" in content_type and download_pdfs:
                    slug = slugify_url(url) + ".pdf"
                    pdf_path = pdf_dir / slug
                    if not dry_run:
                        pdf_path.write_bytes(resp.content)
                        metadata[pdf_path.name] = _build_file_metadata(url, resp, "pdf")
                    stats["pdf_saved"] += 1
                    logger.info("PDF saved (by content-type): %s", pdf_path.name)
                # Office doc served without proper extension
                elif download_docs and any(ct in content_type for ct in [
                    "application/msword", "application/vnd.openxmlformats",
                    "application/vnd.ms-excel", "application/vnd.ms-powerpoint",
                ]):
                    ext = _guess_doc_extension(content_type)
                    slug = slugify_url(url) + ext
                    doc_path = docs_dir / slug
                    if not dry_run:
                        doc_path.write_bytes(resp.content)
                        metadata[doc_path.name] = _build_file_metadata(url, resp, ext.lstrip("."))
                    stats["docs_saved"] += 1
                    logger.info("Doc saved (by content-type): %s", doc_path.name)
                else:
                    stats["skipped"] += 1
                stats["pages_visited"] += 1
                _print_progress(domain_name, stats)
                time.sleep(delay)
                continue

            # Some academic sites declare ISO-8859-1 in HTTP headers (or omit charset
            # entirely, causing requests to default to ISO-8859-1 per RFC 2616).
            # Override with content-based detection when header charset is unreliable.
            declared = (resp.encoding or "").upper()
            if declared in ("ISO-8859-1", "LATIN-1", "ASCII", ""):
                detected = resp.apparent_encoding
                logger.debug(
                    "Encoding override: declared=%s detected=%s for %s",
                    declared or "(none)", detected, url
                )
                resp.encoding = detected

            html = resp.text
            slug = slugify_url(url)
            html_path = html_dir / f"{slug}.html"
            if not dry_run:
                html_path.write_text(html, encoding="utf-8")
                metadata[html_path.name] = _build_file_metadata(url, resp, "html")
            stats["html_saved"] += 1
            stats["pages_visited"] += 1

            # Extract links and add to queue
            links = extract_links(html, url)
            for link in links:
                if link not in visited and is_same_domain(link, base_url):
                    queue.append(link)

            _print_progress(domain_name, stats)

            if stats["html_saved"] % 50 == 0:
                # Print on new line so the periodic log doesn't overwrite the progress bar
                print()
                logger.info("Progress [%s]: %d HTML, %d PDF, %d docs, %d visited",
                            domain_name, stats["html_saved"], stats["pdf_saved"],
                            stats["docs_saved"], stats["pages_visited"])

        except Exception as e:
            logger.error("Failed to fetch %s: %s", url, e)
            stats["errors"] += 1
            stats["pages_visited"] += 1
            _print_progress(domain_name, stats)

        time.sleep(delay)

        # Save metadata and queue periodically (every 100 pages) to avoid data loss on crash
        if not dry_run and stats["pages_visited"] % 100 == 0:
            _save_metadata(metadata, metadata_path)
            queue_path.write_text(json.dumps(list(queue), ensure_ascii=False), encoding="utf-8")

    # End of BFS — move to new line after the progress bar
    print()

    # Final saves
    if not dry_run:
        _save_metadata(metadata, metadata_path)
        logger.info("Metadata saved: %d entries -> %s", len(metadata), metadata_path.name)
        # Remove queue file on clean completion (no pending URLs)
        if queue_path.exists():
            queue_path.unlink()

    logger.info(
        "Crawl complete [%s]: %d HTML, %d PDF, %d docs, %d errors, %d skipped, %d resumed (%d visited)",
        domain_name,
        stats["html_saved"],
        stats["pdf_saved"],
        stats["docs_saved"],
        stats["errors"],
        stats["skipped"],
        stats["resumed"],
        stats["pages_visited"],
    )

    return stats


def run():
    """Crawl all enabled domains from config."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", help="Crawl only this domain name (e.g. pmf_uns)")
    parser.add_argument(
        "--fresh",
        action="store_true",
        default=False,
        help="Disable resume mode. Start BFS from scratch and overwrite existing HTML files.",
    )
    parser.add_argument(
        "--html-only",
        action="store_true",
        default=False,
        help="Download only HTML pages. Skip PDF and Office document downloads.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Fetch pages but do not write any files to disk. For verification only.",
    )
    args, _ = parser.parse_known_args()

    config = load_config()
    domains = config.get("crawl_domains", [])
    enabled = [d for d in domains if d.get("enabled", False)]

    if args.domain:
        enabled = [d for d in enabled if d["name"] == args.domain]
        if not enabled:
            logger.error("Domain '%s' not found or not enabled in config", args.domain)
            return

    if not enabled:
        logger.warning("No enabled crawl domains found in config")
        return

    mode_flags = []
    if args.fresh:
        mode_flags.append("fresh")
    if args.html_only:
        mode_flags.append("html-only")
    if args.dry_run:
        mode_flags.append("dry-run")
    mode_str = f" [{', '.join(mode_flags)}]" if mode_flags else ""

    logger.info("Starting crawl for %d domain(s)%s", len(enabled), mode_str)
    keep_awake()
    logger.info("System sleep prevention enabled")

    try:
        with PipelineTracker("crawl", "Web crawler — BFS over configured domains") as tracker:
            total_html = 0
            total_pdf = 0
            total_docs = 0
            total_errors = 0

            for domain in enabled:
                name = domain["name"]
                base_url = domain["base_url"]
                logger.info("=" * 60)
                logger.info("Crawling domain: %s (%s)", name, base_url)
                logger.info("=" * 60)

                stats = crawl_domain(
                    name,
                    base_url,
                    config,
                    fresh=args.fresh,
                    html_only=args.html_only,
                    dry_run=args.dry_run,
                )
                total_html += stats["html_saved"]
                total_pdf += stats["pdf_saved"]
                total_docs += stats["docs_saved"]
                total_errors += stats["errors"]

            tracker.add_metric("html_pages", total_html)
            tracker.add_metric("pdf_files", total_pdf)
            tracker.add_metric("doc_files", total_docs)
            tracker.add_metric("crawl_errors", total_errors)
            tracker.record(
                items_in=len(enabled),
                items_out=total_html + total_pdf + total_docs,
                items_skipped=total_errors,
            )

            logger.info("=" * 60)
            logger.info("CRAWL SUMMARY: %d HTML, %d PDFs, %d docs, %d errors across %d domains",
                         total_html, total_pdf, total_docs, total_errors, len(enabled))
            logger.info("=" * 60)
    finally:
        release_awake()
        logger.info("System sleep prevention released")


if __name__ == "__main__":
    run()
