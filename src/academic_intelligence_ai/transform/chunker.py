"""Chunk processed text into retrieval-ready pieces.

Reads JSON files from data/processed/, splits text using a character-based
sliding window with word-boundary respect, and writes chunked JSON files
to data/chunked/.
"""

import json
from pathlib import Path

import yaml

from academic_intelligence_ai.monitoring.logger import get_logger

logger = get_logger("transform.chunker")

PROJECT_ROOT = Path(__file__).resolve().parents[3]


# --- Public API ---


def run(fresh: bool = False):
    """Chunk all processed files and save to data/chunked/.

    Reads chunking config from config.yaml, processes each JSON file in
    data/processed/, and writes one output file per input to data/chunked/.
    When fresh=False, skips files that already exist in data/chunked/.
    """
    config = _load_config()
    chunk_cfg = config.get("chunking", {})
    chunk_size = chunk_cfg.get("chunk_size", 400)
    chunk_overlap = chunk_cfg.get("chunk_overlap", 80)
    min_chunk_size = chunk_cfg.get("min_chunk_size", 50)

    processed_dir = PROJECT_ROOT / "data" / "processed"
    output_dir = PROJECT_ROOT / "data" / "chunked"
    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(processed_dir.glob("*.json"))
    if not files:
        logger.warning("No processed files found in %s", processed_dir)
        return 0

    logger.info("Chunking %d processed files (size=%d, overlap=%d, min=%d, fresh=%s)",
                len(files), chunk_size, chunk_overlap, min_chunk_size, fresh)

    total_chunks = 0
    skipped = 0
    skipped_existing = 0

    for i, file_path in enumerate(files, 1):
        output_path = output_dir / file_path.name

        # Resume: skip if already chunked and fresh mode is off
        if not fresh and output_path.exists():
            skipped_existing += 1
            continue

        try:
            count = _chunk_one(file_path, output_path,
                               chunk_size, chunk_overlap, min_chunk_size)
            total_chunks += count
        except Exception as e:
            logger.error("Failed to chunk %s: %s", file_path.name, e)
            skipped += 1

        print(f"\r  chunking: {i}/{len(files)}  chunks: {total_chunks}", end="", flush=True)

        if i % 2000 == 0:
            logger.info("Progress: %d/%d files chunked (%d chunks so far)",
                        i, len(files), total_chunks)

    print()
    logger.info(
        "Chunking complete: %d files -> %d chunks (%d errors, %d already existed)",
        len(files), total_chunks, skipped, skipped_existing,
    )
    return total_chunks


# --- Core chunking logic ---


def chunk_text(text: str, chunk_size: int, chunk_overlap: int,
               min_chunk_size: int) -> list[dict]:
    """Split text into overlapping chunks respecting word boundaries.

    Returns a list of dicts: {chunk_index, text, char_offset, chunk_length}.
    """
    if not text or len(text) < min_chunk_size:
        return []

    if len(text) <= chunk_size:
        return [{"chunk_index": 0, "text": text,
                 "char_offset": 0, "chunk_length": len(text)}]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # Last chunk: take everything remaining
        if end >= len(text):
            chunk = text[start:].strip()
            if len(chunk) >= min_chunk_size:
                chunks.append(_make_chunk(len(chunks), chunk, start))
            break

        # Back up to last space to avoid cutting mid-word
        boundary = end
        while boundary > start and text[boundary] != " ":
            boundary -= 1

        # If no space found (one huge token), force-cut at chunk_size
        if boundary == start:
            boundary = end

        chunk = text[start:boundary].strip()
        if len(chunk) >= min_chunk_size:
            chunks.append(_make_chunk(len(chunks), chunk, start))

        step = boundary - start - chunk_overlap
        start += max(step, 1)

    return chunks


# --- Internal helpers ---


def _chunk_one(file_path: Path, output_path: Path,
               chunk_size: int, chunk_overlap: int,
               min_chunk_size: int) -> int:
    """Chunk a single processed JSON file and write to output_path."""
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    text = payload["text"]
    meta = payload["metadata"]

    page_title = meta.get("page_title", "")

    chunks = chunk_text(text, chunk_size, chunk_overlap, min_chunk_size)
    if not chunks:
        return 0

    # Prepend page title to each chunk for richer embedding context
    if page_title:
        for chunk in chunks:
            chunk["text"] = f"[{page_title}] {chunk['text']}"
            chunk["chunk_length"] = len(chunk["text"])

    output = {
        "metadata": {
            "source": meta["source"],
            "file_type": meta["file_type"],
            "raw_filename": meta["raw_filename"],
            "url": meta.get("url", ""),
            "text_hash": meta["text_hash"],
            "full_text_length": meta["text_length"],
            "chunk_count": len(chunks),
            "chunk_config": {
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "min_chunk_size": min_chunk_size,
            },
        },
        "chunks": chunks,
    }

    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return len(chunks)


def _make_chunk(index: int, text: str, offset: int) -> dict:
    """Build a single chunk dict."""
    return {
        "chunk_index": index,
        "text": text,
        "char_offset": offset,
        "chunk_length": len(text),
    }


def _load_config() -> dict:
    """Load configuration from config/config.yaml."""
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


if __name__ == "__main__":
    run()
