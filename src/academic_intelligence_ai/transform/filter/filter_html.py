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

    # Layer 1: prefer semantic content containers (domain-agnostic)
    content_node = (
        soup.find("main")
        or soup.find("article")
        or soup.find(id="content")
        or soup.find(id="main-content")
        or soup.find(class_="entry-content")
        or soup.find(id="primary")
    )

    source = content_node if content_node else soup
    if content_node:
        logger.debug("Using semantic container <%s> for text extraction", content_node.name)

    text = source.get_text(separator=" ")

    # Layer 2: domain-specific boilerplate strip
    text = _strip_domain_boilerplate(text)

    # Collapse whitespace into single spaces
    clean_text = " ".join(text.split())

    return clean_text, title


def _strip_domain_boilerplate(text: str) -> str:
    """Strip known domain-specific navigation/boilerplate from extracted text.

    Only strips markers found within the first 2000 characters to avoid
    accidentally removing content that happens to contain the same phrases.
    """
    # DF (www.df.uns.ac.rs): heavy nav block starting with "Meni Početak"
    marker_pos = text.find("Meni Po\u010detak")  # Meni Početak
    if marker_pos != -1 and marker_pos < 2000:
        end_marker = "Vesti sa PMF-a Doga\u0111aji"  # Vesti sa PMF-a Događaji
        end_pos = text.find(end_marker, marker_pos)
        if end_pos != -1:
            strip_end = end_pos + len(end_marker)
            logger.debug("DF boilerplate: stripping %d chars (Meni Početak...Događaji)", strip_end - marker_pos)
            text = text[:marker_pos] + text[strip_end:]
        else:
            # Fallback: try shorter end marker
            end_marker_short = "Vesti sa PMF-a"
            end_pos = text.find(end_marker_short, marker_pos)
            if end_pos != -1:
                strip_end = end_pos + len(end_marker_short)
                logger.debug("DF boilerplate: stripping %d chars (Meni Početak...Vesti sa PMF-a)", strip_end - marker_pos)
                text = text[:marker_pos] + text[strip_end:]

    # DH (www.dh.uns.ac.rs): nav from "Skip to content" to "Linkedin-in"
    skip_pos = text.find("Skip to content")
    linkedin_pos = text.find("Linkedin-in")
    if skip_pos != -1 and linkedin_pos != -1 and skip_pos < 2000 and skip_pos < linkedin_pos:
        strip_end = linkedin_pos + len("Linkedin-in")
        logger.debug("DH boilerplate: stripping %d chars (Skip to content...Linkedin-in)", strip_end - skip_pos)
        text = text[:skip_pos] + text[strip_end:]

    # DMI (www.dmi.uns.ac.rs): prefix with department name + "Skip to content"
    dmi_marker = "\u2013 Departman za matematiku i informatiku Skip to content"  # – Departman...
    dmi_pos = text.find(dmi_marker)
    if dmi_pos != -1 and dmi_pos < 2000:
        strip_end = dmi_pos + len(dmi_marker)
        logger.debug("DMI boilerplate: stripping %d chars (prefix through Skip to content)", strip_end)
        text = text[strip_end:]

    # DBE (wwwold.dbe.pmf.uns.ac.rs): English nav header ending with "SEARCH"
    dbe_marker = "Department of Biology and Ecology Faculty of Sciences about STUDYING"
    dbe_pos = text.find(dbe_marker)
    if dbe_pos != -1 and dbe_pos < 2000:
        search_pos = text.find("SEARCH", dbe_pos)
        if search_pos != -1:
            strip_end = search_pos + len("SEARCH")
            logger.debug("DBE boilerplate: stripping %d chars (header through SEARCH)", strip_end - dbe_pos)
            text = text[:dbe_pos] + text[strip_end:]

    # DBE footer
    dbe_footer = "Faculty of Sciences, University of Novi Sad Trg Dositeja Obradovi\u0107a 3"
    footer_pos = text.find(dbe_footer)
    if footer_pos != -1 and footer_pos > len(text) // 2:
        logger.debug("DBE boilerplate: stripping footer from pos %d", footer_pos)
        text = text[:footer_pos]

    # PMF (www.pmf.uns.ac.rs): simple prefix
    pmf_marker = "Skip to main content"
    pmf_pos = text.find(pmf_marker)
    if pmf_pos != -1 and pmf_pos < 200:
        text = text[:pmf_pos] + text[pmf_pos + len(pmf_marker):]
        logger.debug("PMF boilerplate: stripped 'Skip to main content' prefix")

    return text


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
