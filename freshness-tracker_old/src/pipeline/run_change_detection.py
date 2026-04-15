"""
run_change_detection.py — orchestrate the change detection pass.

For each source_id that has at least 2 snapshots and whose latest snapshot
has not yet been compared, fetches the latest and previous snapshot rows
(plus their extracted_fields) and calls detect_changes.compare_snapshots().

Inserts one change_events row per detected difference.
"""

import logging
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.db import get_engine
from src.pipeline.detect_changes import compare_snapshots

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# SQL
# ──────────────────────────────────────────────────────────────────────────────

# Sources that have ≥2 snapshots AND whose latest snapshot has no change_events
# recorded yet (i.e. it has not been used as current_snapshot_id before).
ELIGIBLE_SOURCES = text("""
    SELECT
        rs.source_id,
        COUNT(rs.snapshot_id) AS snapshot_count
    FROM raw_snapshots rs
    GROUP BY rs.source_id
    HAVING COUNT(rs.snapshot_id) >= 2
      AND MAX(rs.snapshot_id) NOT IN (
          SELECT DISTINCT current_snapshot_id
          FROM change_events
          WHERE current_snapshot_id IS NOT NULL
      )
    ORDER BY rs.source_id
""")

# Latest 2 snapshots for a given source, joined with extracted_fields.
# Returns: snapshot_id, source_id, content_hash, page_title,
#          email, phone, opening_hours, fee_text
# Ordered newest-first, so row 0 = current, row 1 = previous.
LATEST_TWO_SNAPSHOTS = text("""
    SELECT
        rs.snapshot_id,
        rs.source_id,
        rs.content_hash,
        rs.page_title,
        ef.email,
        ef.phone,
        ef.opening_hours,
        ef.fee_text
    FROM raw_snapshots rs
    LEFT JOIN extracted_fields ef ON ef.snapshot_id = rs.snapshot_id
    WHERE rs.source_id = :source_id
    ORDER BY rs.fetched_at DESC, rs.snapshot_id DESC
    LIMIT 2
""")

INSERT_CHANGE_EVENT = text("""
    INSERT INTO change_events (
        source_id,
        previous_snapshot_id,
        current_snapshot_id,
        detected_at,
        field_name,
        old_value,
        new_value,
        change_type,
        severity
    ) VALUES (
        :source_id,
        :previous_snapshot_id,
        :current_snapshot_id,
        :detected_at,
        :field_name,
        :old_value,
        :new_value,
        :change_type,
        :severity
    )
""")


# ──────────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────────

def run() -> None:
    engine = get_engine()

    # 1. Find eligible sources
    with engine.connect() as conn:
        eligible_rows = conn.execute(ELIGIBLE_SOURCES).fetchall()

    eligible_count  = len(eligible_rows)
    compared_count  = 0
    total_inserted  = 0

    logger.info("%d eligible source(s) to compare", eligible_count)

    # 2. Per-source comparison
    for row in eligible_rows:
        source_id = row.source_id

        with engine.connect() as conn:
            snaps = conn.execute(
                LATEST_TWO_SNAPSHOTS, {"source_id": source_id}
            ).fetchall()

        if len(snaps) < 2:
            logger.warning("source=%s: fewer than 2 snapshots found, skipping", source_id)
            continue

        # snaps[0] = most recent (current), snaps[1] = previous
        curr = dict(snaps[0]._mapping)
        prev = dict(snaps[1]._mapping)

        events = compare_snapshots(prev, curr)
        compared_count += 1

        if not events:
            logger.info("source=%s: no changes detected", source_id)
            continue

        detected_at = datetime.now(timezone.utc)

        with engine.begin() as conn:
            for event in events:
                conn.execute(INSERT_CHANGE_EVENT, {**event, "detected_at": detected_at})

        total_inserted += len(events)
        logger.info(
            "source=%s: %d change event(s) inserted (%s)",
            source_id,
            len(events),
            ", ".join(e["field_name"] for e in events),
        )

    # 3. Summary
    with engine.connect() as conn:
        total_in_db = conn.execute(
            text("SELECT COUNT(*) FROM change_events")
        ).scalar()

    print(f"\n{'─' * 40}")
    print(f"  eligible sources     : {eligible_count}")
    print(f"  sources compared     : {compared_count}")
    print(f"  change_events inserted this run : {total_inserted}")
    print(f"  total change_events in DB       : {total_in_db}")
    print(f"{'─' * 40}\n")


if __name__ == "__main__":
    run()
