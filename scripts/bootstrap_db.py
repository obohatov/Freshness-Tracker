"""
Bootstrap the freshness-tracker database.

Steps:
  1. Apply 00_schema.sql   (tables + indexes)
  2. Apply 01_views.sql    (analytical views)
  3. Upsert seed_sources.csv into sources table
"""

import csv
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text
from src.db import get_engine

SQL_DIR = os.path.join(os.path.dirname(__file__), "..", "sql")
SEED_CSV = os.path.join(SQL_DIR, "seed_sources.csv")


def apply_sql_file(engine, filename: str) -> None:
    filepath = os.path.join(SQL_DIR, filename)
    print(f"Applying {filename} ...")
    with open(filepath, "r", encoding="utf-8") as f:
        sql = f.read()
    with engine.begin() as conn:
        conn.execute(text(sql))
    print(f"  done.")


def upsert_sources(engine) -> None:
    print("Loading seed_sources.csv into sources ...")
    with open(SEED_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    upsert_sql = """
        INSERT INTO sources (
            source_id, organization_name, page_name, category,
            language, url, is_active, expected_fields
        )
        VALUES (
            :source_id, :organization_name, :page_name, :category,
            :language, :url, :is_active, :expected_fields
        )
        ON CONFLICT (source_id) DO UPDATE SET
            organization_name = EXCLUDED.organization_name,
            page_name         = EXCLUDED.page_name,
            category          = EXCLUDED.category,
            language          = EXCLUDED.language,
            url               = EXCLUDED.url,
            is_active         = EXCLUDED.is_active,
            expected_fields   = EXCLUDED.expected_fields
    """

    with engine.begin() as conn:
        for row in rows:
            params = {
                "source_id":        row["source_id"].strip(),
                "organization_name": row["organization_name"].strip(),
                "page_name":        row["page_name"].strip(),
                "category":         row["category"].strip(),
                "language":         row["language"].strip(),
                "url":              row["url"].strip(),
                "is_active":        row["is_active"].strip() in ("1", "true", "True"),
                "expected_fields":  row.get("expected_fields", "").strip() or None,
            }
            conn.execute(text(upsert_sql), params)

    print(f"  inserted/updated {len(rows)} source rows.")


def main() -> None:
    engine = get_engine()
    apply_sql_file(engine, "00_schema.sql")
    apply_sql_file(engine, "01_views.sql")
    upsert_sources(engine)
    print("\nBootstrap complete.")


if __name__ == "__main__":
    main()
