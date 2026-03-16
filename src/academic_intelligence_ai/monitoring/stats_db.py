"""Repository for filter/pipeline statistics.

Encapsulates all SQL queries for saving and reading filter stats.
Other modules call these Python functions and never write SQL directly.
"""

from academic_intelligence_ai.db.connection import get_connection
from academic_intelligence_ai.monitoring.logger import get_logger

logger = get_logger("monitoring.stats_db")


def save_filter_stats(run_id: int, stats: dict[str, dict[str, int]]):
    """Persist filter breakdown stats for a pipeline run.

    Args:
        run_id: The pipeline_runs.id this data belongs to.
        stats: Nested dict {stats_key: {reason: count}} where
               stats_key is "domain/file_type" (e.g. "pmf_uns/html").
    """
    conn = get_connection()
    rows = []
    for stats_key, reason_counts in stats.items():
        parts = stats_key.split("/", 1)
        domain = parts[0]
        file_type = parts[1] if len(parts) > 1 else "unknown"
        for reason, count in reason_counts.items():
            rows.append((run_id, domain, file_type, reason, count))

    conn.executemany(
        "INSERT INTO filter_stats (run_id, domain, file_type, reason, count) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    logger.info("Saved filter stats for run %d (%d rows)", run_id, len(rows))


def get_filter_stats(run_id: int) -> list[dict]:
    """Retrieve filter stats for a given run.

    Returns a list of dicts with keys: domain, file_type, reason, count.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT domain, file_type, reason, count FROM filter_stats WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    conn.close()
    return [
        {"domain": r[0], "file_type": r[1], "reason": r[2], "count": r[3]}
        for r in rows
    ]


def get_latest_transform_run_id() -> int | None:
    """Return the run_id of the most recent 'transform' pipeline step."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM pipeline_runs WHERE step = 'transform' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row[0] if row else None


def compare_filter_stats(run_id_current: int, run_id_previous: int) -> dict:
    """Compare filter stats between two runs.

    Returns a dict keyed by (domain, file_type, reason) with current/previous counts.
    """
    current = get_filter_stats(run_id_current)
    previous = get_filter_stats(run_id_previous)

    prev_lookup = {
        (r["domain"], r["file_type"], r["reason"]): r["count"]
        for r in previous
    }

    comparison = {}
    all_keys = set()

    for r in current:
        key = (r["domain"], r["file_type"], r["reason"])
        all_keys.add(key)
        comparison[key] = {
            "current": r["count"],
            "previous": prev_lookup.get(key, 0),
        }

    for r in previous:
        key = (r["domain"], r["file_type"], r["reason"])
        if key not in comparison:
            comparison[key] = {"current": 0, "previous": r["count"]}

    return comparison
