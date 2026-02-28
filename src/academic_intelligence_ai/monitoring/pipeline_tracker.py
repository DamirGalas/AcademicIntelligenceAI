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


def _init_metrics_table():
    """Create the run_metrics table if it does not exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS run_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            FOREIGN KEY (run_id) REFERENCES pipeline_runs(id)
        )
    """)
    conn.commit()
    conn.close()


class PipelineTracker:
    """Context manager that tracks pipeline step execution.

    Usage:
        with PipelineTracker("extract") as tracker:
            # ... pipeline work ...
            tracker.add_metric("fetch_failures", 2)
            tracker.record(items_in=6, items_out=4, items_skipped=2)
    """

    def __init__(self, step: str):
        self.step = step
        self.start_time = 0.0
        self.items_in = 0
        self.items_out = 0
        self.items_skipped = 0
        self.metrics: dict[str, float] = {}
        self._recorded = False

    def __enter__(self):
        self.start_time = time.perf_counter()
        logger.info("Starting step: %s", self.step)
        return self

    def add_metric(self, name: str, value: float):
        """Store an arbitrary metric for this run."""
        self.metrics[name] = value

    def record(self, items_in: int, items_out: int, items_skipped: int):
        """Record the results of this step (call before exiting the context)."""
        self.items_in = items_in
        self.items_out = items_out
        self.items_skipped = items_skipped
        self._recorded = True

    @staticmethod
    def get_previous_metric(step: str, metric_name: str) -> float | None:
        """Retrieve the most recent value for a given metric from a previous run."""
        try:
            _init_metrics_table()
            conn = sqlite3.connect(DB_PATH)
            row = conn.execute(
                """
                SELECT rm.metric_value
                FROM run_metrics rm
                JOIN pipeline_runs pr ON rm.run_id = pr.id
                WHERE pr.step = ? AND rm.metric_name = ?
                ORDER BY pr.id DESC
                LIMIT 1
                """,
                (step, metric_name),
            ).fetchone()
            conn.close()
            return row[0] if row else None
        except Exception:
            return None

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
            _init_metrics_table()
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.execute(
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
            run_id = cursor.lastrowid

            for metric_name, metric_value in self.metrics.items():
                conn.execute(
                    "INSERT INTO run_metrics (run_id, metric_name, metric_value) VALUES (?, ?, ?)",
                    (run_id, metric_name, metric_value),
                )

            conn.commit()
            conn.close()

            if self.metrics:
                metrics_str = ", ".join(f"{k}={v}" for k, v in self.metrics.items())
                logger.info("Step %s metrics: %s", self.step, metrics_str)
        except Exception as e:
            logger.error("Failed to write pipeline_runs/metrics: %s", e)

        # Do not suppress exceptions
        return False
