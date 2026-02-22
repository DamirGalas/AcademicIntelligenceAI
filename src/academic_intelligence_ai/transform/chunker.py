import json
from pathlib import Path

import yaml

from academic_intelligence_ai.monitoring.logger import get_logger

logger = get_logger("transform.chunker")

# Project root: 4 levels up (transform -> academic_intelligence_ai -> src -> root)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_config() -> dict:
    """Load configuration from config/config.yaml."""
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def chunk_text(text: str, chunk_size: int, chunk_overlap: int, min_chunk_size: int) -> list[dict]:
    """Split text into overlapping chunks respecting word boundaries.

    Uses a character-based sliding window. When the window end lands
    mid-word, it backs up to the last whitespace so no word is cut.
    Chunks shorter than min_chunk_size are discarded.

    Returns a list of dicts with keys: chunk_index, text, char_offset, chunk_length.
    """
    if len(text) <= chunk_size:
        if len(text) >= min_chunk_size:
            return [{"chunk_index": 0, "text": text, "char_offset": 0, "chunk_length": len(text)}]
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            # Last chunk: take everything remaining
            chunk = text[start:].strip()
            if len(chunk) >= min_chunk_size:
                chunks.append({
                    "chunk_index": len(chunks),
                    "text": chunk,
                    "char_offset": start,
                    "chunk_length": len(chunk),
                })
            break

        # Back up to last space to avoid cutting mid-word
        boundary = end
        while boundary > start and text[boundary] != " ":
            boundary -= 1

        # If no space found (one huge word), force-cut at chunk_size
        if boundary == start:
            boundary = end

        chunk = text[start:boundary].strip()
        if len(chunk) >= min_chunk_size:
            chunks.append({
                "chunk_index": len(chunks),
                "text": chunk,
                "char_offset": start,
                "chunk_length": len(chunk),
            })

        step = boundary - start - chunk_overlap
        if step <= 0:
            step = 1
        start = start + step

    return chunks


def process_file(file_path: Path, chunk_cfg: dict, output_dir: Path) -> int:
    """Chunk a single processed JSON file. Returns number of chunks produced."""
    chunk_size = chunk_cfg.get("chunk_size", 400)
    chunk_overlap = chunk_cfg.get("chunk_overlap", 80)
    min_chunk_size = chunk_cfg.get("min_chunk_size", 50)

    payload = json.loads(file_path.read_text(encoding="utf-8"))
    text = payload["text"]
    meta = payload["metadata"]

    chunks = chunk_text(text, chunk_size, chunk_overlap, min_chunk_size)

    if not chunks:
        logger.warning("No chunks produced for %s (text_length=%d)", meta["source"], len(text))
        return 0

    output = {
        "source": meta["source"],
        "purpose": meta.get("purpose", "unknown"),
        "raw_filename": meta["raw_filename"],
        "processed_at": meta["processed_at"],
        "full_text_length": meta["text_length"],
        "chunk_config": {
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "min_chunk_size": min_chunk_size,
        },
        "chunks": chunks,
    }

    output_path = output_dir / f"{meta['source']}.json"
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info(
        "Chunked %s -> %d chunks (avg %.0f chars)",
        meta["source"], len(chunks), sum(c["chunk_length"] for c in chunks) / len(chunks),
    )
    return len(chunks)


def run():
    """Chunk all processed JSON files in data/processed/."""
    config = load_config()
    chunk_cfg = config.get("chunking", {})

    processed_dir = PROJECT_ROOT / "data" / "processed"
    output_dir = PROJECT_ROOT / "data" / "chunked"
    output_dir.mkdir(parents=True, exist_ok=True)

    json_files = list(processed_dir.glob("*.json"))
    if not json_files:
        logger.warning("No processed JSON files found in %s", processed_dir)
        return

    logger.info("Found %d processed file(s) to chunk", len(json_files))

    total_chunks = 0
    skipped = 0

    for file_path in json_files:
        try:
            count = process_file(file_path, chunk_cfg, output_dir)
            if count > 0:
                total_chunks += count
            else:
                skipped += 1
        except Exception as e:
            logger.error("Failed to chunk %s: %s", file_path.name, e)
            skipped += 1

    logger.info(
        "Chunking complete: %d files -> %d total chunks, %d skipped",
        len(json_files), total_chunks, skipped,
    )


if __name__ == "__main__":
    run()
