import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from academic_intelligence_ai.ingest.crawler import run

if __name__ == "__main__":
    run()
