"""Filter raw HTML files — decide keep or discard before further processing."""

import hashlib
from pathlib import Path

from bs4 import BeautifulSoup

from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.transform.filter.models import FilterResult

logger = get_logger("transform.filter.html")


def filter_html(
    file_path: Path,
    strip_tags: list[str],
    min_text_length: int,
) -> FilterResult:
    """Run all filter checks on a single HTML file, return on first discard."""
    raw_html = file_path.read_text(encoding="utf-8", errors="replace")

    if result := _check_empty(raw_html):
        return result

    clean_text, title = _parse_and_clean(raw_html, strip_tags)

    if result := _check_error_page(clean_text, title):
        return result

    if result := _check_too_short(clean_text, min_text_length):
        return result

    return FilterResult(
        status="keep",
        reason="ok",
        text_hash=_compute_hash(clean_text),
        clean_text=clean_text,
        text_length=len(clean_text),
    )


# --- Private helpers (called in order by filter_html) ---


def _check_empty(raw_html: str) -> FilterResult | None:
    """Discard if the raw HTML file is empty or whitespace-only."""
    if not raw_html.strip():
        return FilterResult(
            status="discard",
            reason="empty_file",
            text_hash="",
            clean_text="",
            text_length=0,
        )
    return None


def _parse_and_clean(raw_html: str, strip_tags: list[str]) -> tuple[str, str]:
    """Strip unwanted tags and extract clean text. Returns (clean_text, title)."""
    soup = BeautifulSoup(raw_html, "html.parser")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    for tag in soup(strip_tags):
        tag.decompose()

    text = soup.get_text(separator=" ")
    # Collapse whitespace into single spaces
    clean_text = " ".join(text.split())

    return clean_text, title


def _check_error_page(clean_text: str, title: str) -> FilterResult | None:
    """Discard if the page looks like a 404 or error page."""
    error_patterns = [
        "404",
        "not found",
        "page not found",
        "stranica nije pronađena",
        "stranica nije pronadjena",
        "greška",
        "error page",
    ]
    # Only check short pages — a real content page mentioning "404" is fine
    if len(clean_text) > 1000:
        return None

    combined = f"{title} {clean_text}".lower()
    for pattern in error_patterns:
        if pattern in combined:
            return FilterResult(
                status="discard",
                reason="error_page",
                text_hash="",
                clean_text="",
                text_length=0,
            )
    return None


def _check_too_short(clean_text: str, min_text_length: int) -> FilterResult | None:
    """Discard if the extracted text is below the minimum character threshold."""
    if len(clean_text) < min_text_length:
        return FilterResult(
            status="discard",
            reason="too_short",
            text_hash="",
            clean_text="",
            text_length=len(clean_text),
        )
    return None


def _compute_hash(clean_text: str) -> str:
    """SHA-256 hash of clean text for deduplication."""
    return hashlib.sha256(clean_text.encode("utf-8")).hexdigest()
