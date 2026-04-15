-- sql/00_schema.sql
-- Belgian Public Service Freshness Tracker
-- PostgreSQL schema for MVP

BEGIN;

-- =========================================================
-- 1) SOURCES
-- Master list of monitored pages
-- =========================================================
CREATE TABLE IF NOT EXISTS sources (
    source_id            TEXT PRIMARY KEY,
    organization_name    TEXT NOT NULL,
    page_name            TEXT NOT NULL,
    category             TEXT NOT NULL,
    language             TEXT NOT NULL,
    url                  TEXT NOT NULL UNIQUE,
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    expected_fields      TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =========================================================
-- 2) INGESTION RUNS
-- Metadata for each batch pipeline execution
-- =========================================================
CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id               BIGSERIAL PRIMARY KEY,
    started_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at          TIMESTAMPTZ,
    status               TEXT NOT NULL DEFAULT 'running',
    sources_total        INTEGER NOT NULL DEFAULT 0 CHECK (sources_total >= 0),
    sources_succeeded    INTEGER NOT NULL DEFAULT 0 CHECK (sources_succeeded >= 0),
    sources_failed       INTEGER NOT NULL DEFAULT 0 CHECK (sources_failed >= 0),
    error_summary        TEXT,
    CHECK (status IN ('running', 'success', 'failed', 'partial_success'))
);

-- =========================================================
-- 3) RAW SNAPSHOTS
-- Raw or near-raw fetched content for each source/run
-- =========================================================
CREATE TABLE IF NOT EXISTS raw_snapshots (
    snapshot_id              BIGSERIAL PRIMARY KEY,
    source_id                TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    run_id                   BIGINT NOT NULL REFERENCES ingestion_runs(run_id) ON DELETE CASCADE,
    fetched_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    http_status              INTEGER,
    final_url                TEXT,
    content_type             TEXT,
    content_hash             TEXT,
    page_title               TEXT,
    raw_storage_path         TEXT,
    raw_text                 TEXT,
    etag                     TEXT,
    last_modified_header     TEXT,
    response_headers_json    JSONB NOT NULL DEFAULT '{}'::JSONB
);

-- =========================================================
-- 4) EXTRACTED FIELDS
-- Structured fields extracted from a snapshot
-- One row per snapshot in MVP
-- =========================================================
CREATE TABLE IF NOT EXISTS extracted_fields (
    extraction_id            BIGSERIAL PRIMARY KEY,
    snapshot_id              BIGINT NOT NULL UNIQUE REFERENCES raw_snapshots(snapshot_id) ON DELETE CASCADE,
    source_id                TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    extracted_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    phone                    TEXT,
    email                    TEXT,
    address                  TEXT,
    opening_hours            TEXT,
    update_date_text         TEXT,
    fee_text                 TEXT,
    pdf_links_json           JSONB NOT NULL DEFAULT '[]'::JSONB,
    important_links_json     JSONB NOT NULL DEFAULT '[]'::JSONB
);

-- =========================================================
-- 5) CHANGE EVENTS
-- Field-level differences between successive snapshots
-- =========================================================
CREATE TABLE IF NOT EXISTS change_events (
    change_id                BIGSERIAL PRIMARY KEY,
    source_id                TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    previous_snapshot_id     BIGINT REFERENCES raw_snapshots(snapshot_id) ON DELETE SET NULL,
    current_snapshot_id      BIGINT NOT NULL REFERENCES raw_snapshots(snapshot_id) ON DELETE CASCADE,
    detected_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    field_name               TEXT NOT NULL,
    old_value                TEXT,
    new_value                TEXT,
    change_type              TEXT NOT NULL,
    severity                 TEXT NOT NULL,
    CHECK (severity IN ('low', 'medium', 'high')),
    CHECK (
        previous_snapshot_id IS NULL
        OR previous_snapshot_id <> current_snapshot_id
    )
);

-- =========================================================
-- INDEXES
-- =========================================================

-- sources
CREATE INDEX IF NOT EXISTS idx_sources_category
    ON sources (category);

CREATE INDEX IF NOT EXISTS idx_sources_organization_name
    ON sources (organization_name);

CREATE INDEX IF NOT EXISTS idx_sources_is_active
    ON sources (is_active);

-- ingestion_runs
CREATE INDEX IF NOT EXISTS idx_ingestion_runs_started_at
    ON ingestion_runs (started_at DESC);

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_status
    ON ingestion_runs (status);

-- raw_snapshots
CREATE INDEX IF NOT EXISTS idx_raw_snapshots_source_fetched_at
    ON raw_snapshots (source_id, fetched_at DESC);

CREATE INDEX IF NOT EXISTS idx_raw_snapshots_run_id
    ON raw_snapshots (run_id);

CREATE INDEX IF NOT EXISTS idx_raw_snapshots_content_hash
    ON raw_snapshots (content_hash);

-- extracted_fields
CREATE INDEX IF NOT EXISTS idx_extracted_fields_snapshot_id
    ON extracted_fields (snapshot_id);

CREATE INDEX IF NOT EXISTS idx_extracted_fields_source_id
    ON extracted_fields (source_id);

-- change_events
CREATE INDEX IF NOT EXISTS idx_change_events_source_detected_at
    ON change_events (source_id, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_change_events_change_type
    ON change_events (change_type);

CREATE INDEX IF NOT EXISTS idx_change_events_severity
    ON change_events (severity);

-- =========================================================
-- COMMENTS
-- =========================================================
COMMENT ON TABLE sources IS
'Master list of monitored public-service pages';

COMMENT ON TABLE ingestion_runs IS
'Metadata for each batch pipeline execution';

COMMENT ON TABLE raw_snapshots IS
'Fetched page snapshots with raw text and HTTP metadata';

COMMENT ON TABLE extracted_fields IS
'Structured values extracted from each snapshot';

COMMENT ON TABLE change_events IS
'Detected differences between successive snapshots';

COMMIT;