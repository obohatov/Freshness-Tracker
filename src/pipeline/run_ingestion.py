"""
run_ingestion.py — run one batch ingestion pass.

Steps:
  1. Open an ingestion_runs row (status='running').
  2. Pull up to MAX_SOURCES active sources.
  3. Fetch each page via fetch_pages.fetch_page().
  4. Insert one raw_snapshots row per page (success or failure).
  5. Close the ingestion_runs row with final counts and status.
"""

import logging
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.db import get_engine
from src.pipeline.fetch_pages import fetch_page

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

MAX_SOURCES = 3

INSERT_SNAPSHOT = text("""
    INSERT INTO raw_snapshots (
        source_id, run_id, fetched_at,
        http_status, final_url, content_type,
        content_hash, page_title, raw_text
    ) VALUES (
        :source_id, :run_id, :fetched_at,
        :http_status, :final_url, :content_type,
        :content_hash, :page_title, :raw_text
    )
""")

UPDATE_RUN = text("""
    UPDATE ingestion_runs SET
        finished_at       = NOW(),
        status            = :status,
        sources_total     = :sources_total,
        sources_succeeded = :sources_succeeded,
        sources_failed    = :sources_failed,
        error_summary     = :error_summary
    WHERE run_id = :run_id
""")


def run() -> None:
    engine = get_engine()

    # 1. Open ingestion run
    with engine.begin() as conn:
        run_id = conn.execute(
            text("INSERT INTO ingestion_runs (status) VALUES ('running') RETURNING run_id")
        ).scalar()

    logger.info("Ingestion run %d started", run_id)

    # 2. Load active sources
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT source_id, url FROM sources WHERE is_active = TRUE LIMIT :limit"),
            {"limit": MAX_SOURCES},
        ).fetchall()

    sources = [dict(r._mapping) for r in rows]
    sources_total = len(sources)
    logger.info("Processing %d source(s)", sources_total)

    # 3. Fetch and store
    succeeded = 0
    failed    = 0
    errors    = []

    for source in sources:
        logger.info("→ %s", source["url"])
        data = fetch_page(source)

        is_error = (
            data["http_status"] is None
            or (data["raw_text"] or "").startswith("ERROR:")
        )

        with engine.begin() as conn:
            conn.execute(INSERT_SNAPSHOT, {
                "source_id":    data["source_id"],
                "run_id":       run_id,
                "fetched_at":   datetime.now(timezone.utc),
                "http_status":  data["http_status"],
                "final_url":    data["final_url"],
                "content_type": data["content_type"],
                "content_hash": data["content_hash"],
                "page_title":   data["page_title"],
                "raw_text":     data["raw_text"],
            })

        if is_error:
            failed += 1
            errors.append(f"{source['url']}: {data.get('raw_text', 'unknown error')}")
            logger.warning("  FAILED")
        else:
            succeeded += 1
            logger.info("  OK (HTTP %s)", data["http_status"])

    # 4. Close ingestion run
    status = (
        "success"        if failed == 0
        else "partial_success" if succeeded > 0
        else "failed"
    )
    error_summary = "; ".join(errors) if errors else None

    with engine.begin() as conn:
        conn.execute(UPDATE_RUN, {
            "status":            status,
            "sources_total":     sources_total,
            "sources_succeeded": succeeded,
            "sources_failed":    failed,
            "error_summary":     error_summary,
            "run_id":            run_id,
        })

    logger.info(
        "Run %d done — status=%s  total=%d  succeeded=%d  failed=%d",
        run_id, status, sources_total, succeeded, failed,
    )

    # 5. Print summary
    print(f"\n{'─' * 40}")
    print(f"  run_id     : {run_id}")
    print(f"  attempted  : {sources_total}")
    print(f"  succeeded  : {succeeded}")
    print(f"  failed     : {failed}")
    print(f"  status     : {status}")
    if error_summary:
        print(f"  errors     : {error_summary}")
    print(f"{'─' * 40}\n")


if __name__ == "__main__":
    run()
