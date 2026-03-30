"""Shared data structures for filter modules."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class FilterResult:
    """Result of filtering a single file."""
    status: str        # "keep" or "discard"
    reason: str        # "ok", "empty_file", "error_page", "too_short", "redirect_page", "auth_page", "navigation_only"
    text_hash: str     # SHA-256 of clean text (empty if discarded early)
    clean_text: str    # extracted text (empty if discarded early)
    text_length: int   # len(clean_text)


@dataclass
class KeptFile:
    """A file that passed all filters, ready for further processing."""
    file_path: Path
    domain: str
    file_type: str     # "html" or "pdf"
    clean_text: str
    text_hash: str
