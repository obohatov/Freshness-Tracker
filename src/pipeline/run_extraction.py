"""
run_extraction.py — extract structured fields from raw snapshots.

For each source, takes the latest snapshot from raw_snapshots that does not
yet have a row in extracted_fields, runs extract_fields.extract_all(), and
inserts the result into extracted_fields.
"""

import logging
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.db import get_engine
from src.pipeline.extract_fields import extract_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# Latest snapshot per source that has no extracted_fields row yet
PENDING_SNAPSHOTS = text("""
    SELECT DISTINCT ON (rs.source_id)
        rs.snapshot_id,
        rs.source_id,
        rs.raw_text
    FROM raw_snapshots rs
    LEFT JOIN extracted_fields ef ON ef.snapshot_id = rs.snapshot_id
    WHERE ef.snapshot_id IS NULL
    ORDER BY rs.source_id, rs.fetched_at DESC
""")

INSERT_EXTRACTION = text("""
    INSERT INTO extracted_fields (
        snapshot_id, source_id, extracted_at,
        email, phone, opening_hours, fee_text,
        pdf_links_json, important_links_json
    ) VALUES (
        :snapshot_id, :source_id, :extracted_at,
        :email, :phone, :opening_hours, :fee_text,
        CAST(:pdf_links_json AS jsonb), CAST(:important_links_json AS jsonb)
    )
""")


def run() -> None:
    engine = get_engine()

    with engine.connect() as conn:
        pending = conn.execute(PENDING_SNAPSHOTS).fetchall()

    snapshots_considered = len(pending)
    inserted = 0
    skipped  = 0

    logger.info("%d snapshot(s) pending extraction", snapshots_considered)

    for row in pending:
        snapshot_id = row.snapshot_id
        source_id   = row.source_id
        raw_text    = row.raw_text or ""

        fields = extract_all(raw_text)

        try:
            with engine.begin() as conn:
                conn.execute(INSERT_EXTRACTION, {
                    "snapshot_id":          snapshot_id,
                    "source_id":            source_id,
                    "extracted_at":         datetime.now(timezone.utc),
                    "email":                fields["email"],
                    "phone":                fields["phone"],
                    "opening_hours":        fields["opening_hours"],
                    "fee_text":             fields["fee_text"],
                    "pdf_links_json":       fields["pdf_links_json"],
                    "important_links_json": fields["important_links_json"],
                })
            inserted += 1
            logger.info("Extracted snapshot_id=%d source=%s", snapshot_id, source_id)

        except Exception as exc:
            skipped += 1
            logger.warning("Skipped snapshot_id=%d: %s", snapshot_id, exc)

    total_in_db = engine.connect().execute(
        text("SELECT COUNT(*) FROM extracted_fields")
    ).scalar()

    print(f"\n{'─' * 40}")
    print(f"  snapshots considered : {snapshots_considered}")
    print(f"  inserted             : {inserted}")
    print(f"  skipped (errors)     : {skipped}")
    print(f"  total in extracted_fields : {total_in_db}")
    print(f"{'─' * 40}\n")


if __name__ == "__main__":
    run()
