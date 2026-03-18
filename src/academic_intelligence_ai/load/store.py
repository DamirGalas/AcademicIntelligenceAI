"""Document and chunk persistence layer.

All SQL for the documents/chunks tables lives here.
Other modules call these functions — they never write SQL directly.
"""

import hashlib

from academic_intelligence_ai.db.connection import get_connection
from academic_intelligence_ai.monitoring.logger import get_logger

logger = get_logger("load.store")


def clear_all():
    """Delete all rows from chunks and documents (full reload)."""
    conn = get_connection()
    conn.execute("DELETE FROM chunks")
    conn.execute("DELETE FROM documents")
    conn.commit()
    conn.close()
    logger.info("Cleared documents and chunks tables")


def insert_document(
    source: str,
    raw_filename: str,
    full_text_length: int,
    processed_at: str,
    url: str = "",
    file_type: str = "",
    text_hash: str = "",
) -> int:
    """Insert a document record and return its id."""
    if not text_hash:
        text_hash = hashlib.sha256(
            f"{source}:{raw_filename}".encode()
        ).hexdigest()

    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO documents (source, url, file_type, raw_filename, text_hash, full_text_length, processed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (source, url, file_type, raw_filename, text_hash, full_text_length, processed_at),
    )
    doc_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return doc_id


def insert_chunks(
    doc_id: int,
    chunks: list[dict],
    chunk_size: int,
    chunk_overlap: int,
) -> list[int]:
    """Insert chunk records for a document and return their ids.

    Args:
        doc_id: Parent document id.
        chunks: List of dicts with keys: chunk_index, text, chunk_length, char_offset.
        chunk_size: The chunk_size config value used to produce these chunks.
        chunk_overlap: The chunk_overlap config value used to produce these chunks.
    """
    conn = get_connection()
    chunk_ids = []
    for chunk in chunks:
        cursor = conn.execute(
            "INSERT INTO chunks (doc_id, chunk_index, text, chunk_length, char_offset, chunk_size, chunk_overlap) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                doc_id,
                chunk["chunk_index"],
                chunk["text"],
                chunk["chunk_length"],
                chunk["char_offset"],
                chunk_size,
                chunk_overlap,
            ),
        )
        chunk_ids.append(cursor.lastrowid)
    conn.commit()
    conn.close()
    return chunk_ids


def get_all_chunks() -> list[dict]:
    """Return all chunks with document metadata for embedding.

    Returns a list of dicts: {chunk_id, doc_id, text, source, url, file_type}.
    """
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT c.id, c.doc_id, c.text, d.source, d.url, d.file_type
        FROM chunks c
        JOIN documents d ON c.doc_id = d.id
        ORDER BY c.id
        """
    ).fetchall()
    conn.close()
    return [
        {
            "chunk_id": r[0],
            "doc_id": r[1],
            "text": r[2],
            "source": r[3],
            "url": r[4],
            "file_type": r[5],
        }
        for r in rows
    ]
