import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from academic_intelligence_ai.monitoring.logger import get_logger

logger = get_logger("monitoring.pipeline_tracker")

# Project root: 4 levels up (monitoring -> academic_intelligence_ai -> src -> root)
PROJECT_ROOT = Path(__file__).resolve().parents[3]

DB_PATH = PROJECT_ROOT / "data" / "academic.db"


def _init_tracking_table():
    """Create the pipeline_runs table if it does not exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at TEXT NOT NULL,
            step TEXT NOT NULL,
            duration_sec REAL NOT NULL,
            items_in INTEGER NOT NULL,
            items_out INTEGER NOT NULL,
            items_skipped INTEGER NOT NULL,
            status TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


class PipelineTracker:
    """Context manager that tracks pipeline step execution.

    Usage:
        with PipelineTracker("extract") as tracker:
            # ... pipeline work ...
            tracker.record(items_in=6, items_out=6, items_skipped=0)
    """

    def __init__(self, step: str):
        self.step = step
        self.start_time = 0.0
        self.items_in = 0
        self.items_out = 0
        self.items_skipped = 0
        self._recorded = False

    def __enter__(self):
        self.start_time = time.perf_counter()
        logger.info("Starting step: %s", self.step)
        return self

    def record(self, items_in: int, items_out: int, items_skipped: int):
        """Record the results of this step (call before exiting the context)."""
        self.items_in = items_in
        self.items_out = items_out
        self.items_skipped = items_skipped
        self._recorded = True

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.perf_counter() - self.start_time
        status = "failed" if exc_type else ("success" if self._recorded else "no_data")

        if self.items_skipped > 0 and exc_type is None:
            status = "partial"

        logger.info(
            "Step %s finished in %.1fs — in=%d, out=%d, skipped=%d, status=%s",
            self.step, duration, self.items_in, self.items_out, self.items_skipped, status,
        )

        try:
            _init_tracking_table()
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "INSERT INTO pipeline_runs (run_at, step, duration_sec, items_in, items_out, items_skipped, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    datetime.now(timezone.utc).isoformat(),
                    self.step,
                    round(duration, 2),
                    self.items_in,
                    self.items_out,
                    self.items_skipped,
                    status,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("Failed to write pipeline_runs: %s", e)

        # Do not suppress exceptions
        return False
