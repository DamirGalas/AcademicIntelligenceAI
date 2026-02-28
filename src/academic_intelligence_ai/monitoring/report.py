import sqlite3
from pathlib import Path

from academic_intelligence_ai.monitoring.logger import get_logger

logger = get_logger("monitoring.report")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = PROJECT_ROOT / "data" / "academic.db"

STEPS = ["extract", "transform", "chunk", "load"]


def _get_last_two_runs(conn: sqlite3.Connection, step: str) -> list[dict]:
    """Get the last two runs for a given step, newest first."""
    rows = conn.execute(
        """
        SELECT id, run_at, duration_sec, items_in, items_out, items_skipped, status
        FROM pipeline_runs
        WHERE step = ?
        ORDER BY id DESC
        LIMIT 2
        """,
        (step,),
    ).fetchall()

    runs = []
    for row in rows:
        run_id, run_at, duration, items_in, items_out, items_skipped, status = row
        metrics = dict(
            conn.execute(
                "SELECT metric_name, metric_value FROM run_metrics WHERE run_id = ?",
                (run_id,),
            ).fetchall()
        )
        runs.append({
            "run_id": run_id,
            "run_at": run_at[:16],  # trim seconds
            "duration": duration,
            "items_in": items_in,
            "items_out": items_out,
            "items_skipped": items_skipped,
            "status": status,
            "metrics": metrics,
        })

    return runs


def _format_value(value) -> str:
    """Format a numeric value for display."""
    if isinstance(value, float):
        return f"{value:.1f}" if value != int(value) else str(int(value))
    return str(value)


def _diff_indicator(current, previous) -> str:
    """Return a change indicator comparing current vs previous."""
    if current == previous:
        return ""
    if isinstance(current, (int, float)) and isinstance(previous, (int, float)):
        diff = current - previous
        sign = "+" if diff > 0 else ""
        if isinstance(diff, float):
            return f" ({sign}{diff:.1f})"
        return f" ({sign}{diff})"
    return " (changed)"


def generate_report() -> str:
    """Generate a comparison report of the last two pipeline runs."""
    if not DB_PATH.exists():
        return "No database found. Run the pipeline first."

    conn = sqlite3.connect(DB_PATH)
    lines = ["", "=" * 60, "  PIPELINE REPORT — Last vs Previous", "=" * 60]

    for step in STEPS:
        runs = _get_last_two_runs(conn, step)

        if not runs:
            lines.append(f"\n  {step}: no runs yet")
            continue

        current = runs[0]
        previous = runs[1] if len(runs) > 1 else None

        lines.append("")
        lines.append(f"  [{step.upper()}]")
        lines.append(f"  {'':30s} {'Current':>12s}  {'Previous':>12s}")
        lines.append(f"  {'-' * 56}")

        # Timestamp
        prev_at = previous["run_at"] if previous else "-"
        lines.append(f"  {'Date':30s} {current['run_at']:>12s}  {prev_at:>12s}")

        # Core fields
        fields = [
            ("Duration (s)", "duration"),
            ("Items in", "items_in"),
            ("Items out", "items_out"),
            ("Skipped", "items_skipped"),
            ("Status", "status"),
        ]

        for label, key in fields:
            cur_val = current[key]
            prev_val = previous[key] if previous else "-"
            diff = _diff_indicator(cur_val, prev_val) if previous else ""
            lines.append(f"  {label:30s} {_format_value(cur_val):>12s}  {_format_value(prev_val):>12s}{diff}")

        # Metrics
        all_metric_names = set(current["metrics"].keys())
        if previous:
            all_metric_names |= set(previous["metrics"].keys())

        for metric in sorted(all_metric_names):
            cur_val = current["metrics"].get(metric, "-")
            prev_val = previous["metrics"].get(metric, "-") if previous else "-"
            diff = ""
            if previous and isinstance(cur_val, (int, float)) and isinstance(prev_val, (int, float)):
                diff = _diff_indicator(cur_val, prev_val)
            lines.append(f"  {metric:30s} {_format_value(cur_val):>12s}  {_format_value(prev_val):>12s}{diff}")

    # Total duration
    lines.append("")
    lines.append(f"  {'-' * 56}")

    for label, idx in [("Current total", 0), ("Previous total", 1)]:
        total = 0.0
        has_data = False
        for step in STEPS:
            runs = _get_last_two_runs(conn, step)
            if len(runs) > idx:
                total += runs[idx]["duration"]
                has_data = True
        if has_data:
            lines.append(f"  {label + ' duration':30s} {total:>11.1f}s")

    lines.append("=" * 60)
    lines.append("")

    conn.close()
    return "\n".join(lines)


def print_report():
    """Generate and print the report to console and log."""
    report = generate_report()
    print(report)
    logger.info("Pipeline report generated")


if __name__ == "__main__":
    print_report()
