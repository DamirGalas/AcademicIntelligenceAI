import requests
from pathlib import Path
from datetime import datetime, timezone

from academic_intelligence_ai.monitoring.logger import get_logger

logger = get_logger("ingest.fetch_html")

# Project root: 4 levels up from this file (ingest -> academic_intelligence_ai -> src -> root)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def fetch_html(url: str) -> str:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.text


def save_raw_html(html: str, source_name: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    raw_dir = PROJECT_ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    file_path = raw_dir / f"{source_name}_{timestamp}.html"
    file_path.write_text(html, encoding="utf-8")

    return file_path


if __name__ == "__main__":
    url = "https://www.pmf.uns.ac.rs"
    source_name = "pmf_uns"

    logger.info("Fetching HTML from %s", url)
    html = fetch_html(url)

    file_path = save_raw_html(html, source_name)
    logger.info("Saved raw HTML to %s", file_path)

    input("\nPress Enter to close...")
