"""Assign category, relevance, and department labels to all documents.

Reads every document URL from SQLite, classifies it using URL patterns,
and writes the result back. Safe to re-run — overwrites existing labels.

blog-post-unclassified documents undergo a second pass: chunk text is
fetched from SQLite and a noise score is computed (ratio of date/month
tokens to total words). Documents with noise < BLOG_NOISE_THRESHOLD are
upgraded to news-announcements (high). The rest stay as none.
"""

import re
from urllib.parse import urlparse

from academic_intelligence_ai.db.connection import get_connection
from academic_intelligence_ai.load.url_classifier import (
    MAYBE_RELEVANT,
    RELEVANT,
    classify,
)
from academic_intelligence_ai.monitoring.logger import get_logger

logger = get_logger("load.label_documents")

# Noise scoring for blog-post-unclassified refinement
BLOG_NOISE_THRESHOLD = 0.20

_MONTH_NAMES = {
    # Serbian Latin (nominative + genitive forms)
    "januar", "januara", "februar", "februara", "mart", "marta",
    "april", "aprila", "maj", "maja", "jun", "juna", "jul", "jula",
    "avgust", "avgusta", "septembar", "septembra", "oktobar", "oktobra",
    "novembar", "novembra", "decembar", "decembra",
    # English
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    # Common abbreviations
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
}
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _noise_score(text: str) -> float:
    """Return ratio of date/month tokens to total words (0.0–1.0)."""
    words = text.lower().split()
    if not words:
        return 0.0
    month_hits = sum(1 for w in words if w.strip(".,;:!?\"'()[]") in _MONTH_NAMES)
    year_hits = len(_YEAR_RE.findall(text))
    return (month_hits + year_hits) / len(words)


def _refine_blog_posts(conn, doc_ids: list) -> dict:
    """Return {doc_id: (category, relevance)} for blog docs that pass noise check."""
    if not doc_ids:
        return {}

    upgraded = {}
    for doc_id in doc_ids:
        chunks = conn.execute(
            "SELECT text FROM chunks WHERE doc_id = ?", (doc_id,)
        ).fetchall()
        if not chunks:
            continue
        full_text = " ".join(row[0] for row in chunks)
        if _noise_score(full_text) < BLOG_NOISE_THRESHOLD:
            upgraded[doc_id] = ("news-announcements", "high")

    logger.info(
        "Blog refinement: %d/%d upgraded to news-announcements (noise < %.0f%%)",
        len(upgraded), len(doc_ids), BLOG_NOISE_THRESHOLD * 100,
    )
    return upgraded


DOMAIN_TO_DEPT = {
    "www.dgt.uns.ac.rs":      "DGT",
    "dgt.uns.ac.rs":          "DGT",
    "www.dmi.uns.ac.rs":      "DMI",
    "dmi.uns.ac.rs":          "DMI",
    "www.dbe.pmf.uns.ac.rs":  "DBE",
    "wwwold.dbe.pmf.uns.ac.rs": "DBE",
    "www.dh.uns.ac.rs":       "DH",
    "dh.uns.ac.rs":           "DH",
    "www.df.uns.ac.rs":       "DF",
    "df.uns.ac.rs":           "DF",
    "www.pmf.uns.ac.rs":      "PMF",
    "pmf.uns.ac.rs":          "PMF",
}


def get_department(url: str) -> str:
    try:
        domain = urlparse(url).netloc.lower()
        return DOMAIN_TO_DEPT.get(domain, "")
    except Exception:
        return ""


def get_relevance(category: str) -> str:
    if category in RELEVANT:
        return "high"
    if category in MAYBE_RELEVANT:
        return "medium"
    return "none"


def run():
    conn = get_connection()
    rows = conn.execute("SELECT id, url FROM documents").fetchall()
    logger.info("Labeling %d documents...", len(rows))

    # First pass: URL-based classification
    updates = []
    blog_doc_ids = []
    for doc_id, url in rows:
        category = classify(url or "")
        relevance = get_relevance(category)
        department = get_department(url or "")
        updates.append([category, relevance, department, doc_id])
        if category == "blog-post-unclassified":
            blog_doc_ids.append(doc_id)

    # Second pass: content-based refinement for blog-post-unclassified
    if blog_doc_ids:
        refinements = _refine_blog_posts(conn, blog_doc_ids)
        id_to_idx = {row[3]: i for i, row in enumerate(updates)}
        for doc_id, (cat, rel) in refinements.items():
            i = id_to_idx[doc_id]
            updates[i][0] = cat
            updates[i][1] = rel

    conn.executemany(
        "UPDATE documents SET category = ?, relevance = ?, department = ? WHERE id = ?",
        updates,
    )
    conn.commit()

    total = len(updates)
    high = sum(1 for row in updates if row[1] == "high")
    medium = sum(1 for row in updates if row[1] == "medium")
    none_ = sum(1 for row in updates if row[1] == "none")
    logger.info(
        "Labeled %d documents: high=%d, medium=%d, none=%d",
        total, high, medium, none_,
    )
    print(f"Labeled {total} documents: high={high}, medium={medium}, none={none_}")
    conn.close()


if __name__ == "__main__":
    run()
