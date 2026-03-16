"""Filter raw PDF files — decide keep or discard before further processing."""

import hashlib
from pathlib import Path

import pymupdf

from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.transform.filter.models import FilterResult

logger = get_logger("transform.filter.pdf")


def filter_pdf(
    file_path: Path,
    min_text_length: int,
    max_pages: int,
) -> FilterResult:
    """Run all filter checks on a single PDF file, return on first discard."""
    try:
        doc = pymupdf.open(str(file_path))
    except Exception:
        return FilterResult(
            status="discard", reason="unreadable",
            text_hash="", clean_text="", text_length=0,
        )

    try:
        if result := _check_too_many_pages(doc, max_pages):
            return result

        text = _extract_text(doc)

        if result := _check_empty_text(text):
            return result

        if result := _check_too_short(text, min_text_length):
            return result

        return FilterResult(
            status="keep",
            reason="ok",
            text_hash=_compute_hash(text),
            clean_text=text,
            text_length=len(text),
        )
    finally:
        doc.close()


# --- Private helpers (called in order by filter_pdf) ---


def _check_too_many_pages(doc: pymupdf.Document, max_pages: int) -> FilterResult | None:
    """Discard if the PDF exceeds the page limit (textbooks, theses)."""
    if len(doc) > max_pages:
        return FilterResult(
            status="discard",
            reason="too_many_pages",
            text_hash="",
            clean_text="",
            text_length=0,
        )
    return None


def _extract_text(doc: pymupdf.Document) -> str:
    """Extract and join text from all pages."""
    pages = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            pages.append(text)
    return "\n\n".join(pages)


def _check_empty_text(text: str) -> FilterResult | None:
    """Discard if no text could be extracted (scanned images without OCR)."""
    if not text.strip():
        return FilterResult(
            status="discard",
            reason="no_text",
            text_hash="",
            clean_text="",
            text_length=0,
        )
    return None


def _check_too_short(text: str, min_text_length: int) -> FilterResult | None:
    """Discard if the extracted text is below the minimum character threshold."""
    if len(text) < min_text_length:
        return FilterResult(
            status="discard",
            reason="too_short",
            text_hash="",
            clean_text="",
            text_length=len(text),
        )
    return None


def _compute_hash(text: str) -> str:
    """SHA-256 hash of extracted text for deduplication."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
