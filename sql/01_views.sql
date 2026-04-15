-- sql/01_views.sql
-- Analytical views for dashboard

BEGIN;

-- =========================================================
-- 1) LATEST ALERTS
-- Most recent detected change events with source metadata
-- =========================================================
CREATE OR REPLACE VIEW vw_latest_alerts AS
SELECT
    ce.change_id,
    ce.detected_at,
    ce.source_id,
    s.organization_name,
    s.page_name,
    s.category,
    s.language,
    s.url,
    ce.field_name,
    ce.old_value,
    ce.new_value,
    ce.change_type,
    ce.severity
FROM change_events ce
JOIN sources s
    ON ce.source_id = s.source_id
ORDER BY ce.detected_at DESC, ce.change_id DESC;

-- =========================================================
-- 2) CHANGES OVER TIME
-- Number of detected changes per day
-- =========================================================
CREATE OR REPLACE VIEW vw_changes_over_time AS
SELECT
    DATE_TRUNC('day', ce.detected_at)::date AS change_date,
    COUNT(*) AS total_changes,
    COUNT(*) FILTER (WHERE ce.severity = 'high') AS high_severity_changes,
    COUNT(*) FILTER (WHERE ce.severity = 'medium') AS medium_severity_changes,
    COUNT(*) FILTER (WHERE ce.severity = 'low') AS low_severity_changes
FROM change_events ce
GROUP BY 1
ORDER BY 1;

-- =========================================================
-- 3) CHANGES BY TYPE
-- Distribution of change events by type
-- =========================================================
CREATE OR REPLACE VIEW vw_changes_by_type AS
SELECT
    ce.change_type,
    COUNT(*) AS total_changes,
    COUNT(*) FILTER (WHERE ce.severity = 'high') AS high_severity_changes,
    COUNT(*) FILTER (WHERE ce.severity = 'medium') AS medium_severity_changes,
    COUNT(*) FILTER (WHERE ce.severity = 'low') AS low_severity_changes
FROM change_events ce
GROUP BY ce.change_type
ORDER BY total_changes DESC, ce.change_type;

-- =========================================================
-- 4) MOST CHANGED PAGES
-- Which monitored pages generated the most change events
-- =========================================================
CREATE OR REPLACE VIEW vw_most_changed_pages AS
SELECT
    s.source_id,
    s.organization_name,
    s.page_name,
    s.category,
    s.language,
    s.url,
    COUNT(ce.change_id) AS total_changes,
    COUNT(ce.change_id) FILTER (WHERE ce.severity = 'high') AS high_severity_changes,
    MAX(ce.detected_at) AS latest_change_at
FROM sources s
LEFT JOIN change_events ce
    ON s.source_id = ce.source_id
GROUP BY
    s.source_id,
    s.organization_name,
    s.page_name,
    s.category,
    s.language,
    s.url
ORDER BY total_changes DESC, latest_change_at DESC NULLS LAST;

-- =========================================================
-- 5) MOST CHANGED ORGANIZATIONS
-- Useful optional dashboard aggregate
-- =========================================================
CREATE OR REPLACE VIEW vw_most_changed_organizations AS
SELECT
    s.organization_name,
    COUNT(ce.change_id) AS total_changes,
    COUNT(DISTINCT s.source_id) AS affected_sources,
    COUNT(ce.change_id) FILTER (WHERE ce.severity = 'high') AS high_severity_changes,
    MAX(ce.detected_at) AS latest_change_at
FROM sources s
LEFT JOIN change_events ce
    ON s.source_id = ce.source_id
GROUP BY s.organization_name
ORDER BY total_changes DESC, latest_change_at DESC NULLS LAST;

-- =========================================================
-- 6) PIPELINE RUN SUMMARY
-- Health/status overview of ingestion runs
-- =========================================================
CREATE OR REPLACE VIEW vw_ingestion_run_summary AS
SELECT
    ir.run_id,
    ir.started_at,
    ir.finished_at,
    ir.status,
    ir.sources_total,
    ir.sources_succeeded,
    ir.sources_failed,
    CASE
        WHEN ir.finished_at IS NOT NULL THEN EXTRACT(EPOCH FROM (ir.finished_at - ir.started_at))
        ELSE NULL
    END AS duration_seconds,
    ir.error_summary
FROM ingestion_runs ir
ORDER BY ir.started_at DESC, ir.run_id DESC;

-- =========================================================
-- 7) SOURCE SNAPSHOT SUMMARY
-- Monitoring coverage by source
-- =========================================================
CREATE OR REPLACE VIEW vw_source_snapshot_summary AS
SELECT
    s.source_id,
    s.organization_name,
    s.page_name,
    s.category,
    s.language,
    s.url,
    s.is_active,
    COUNT(rs.snapshot_id) AS total_snapshots,
    MIN(rs.fetched_at) AS first_snapshot_at,
    MAX(rs.fetched_at) AS latest_snapshot_at,
    MAX(rs.http_status) FILTER (
        WHERE rs.fetched_at = (
            SELECT MAX(rs2.fetched_at)
            FROM raw_snapshots rs2
            WHERE rs2.source_id = s.source_id
        )
    ) AS latest_http_status
FROM sources s
LEFT JOIN raw_snapshots rs
    ON s.source_id = rs.source_id
GROUP BY
    s.source_id,
    s.organization_name,
    s.page_name,
    s.category,
    s.language,
    s.url,
    s.is_active
ORDER BY s.organization_name, s.page_name;

-- =========================================================
-- 8) DASHBOARD KPI SUMMARY
-- Single-row summary for top-level metrics
-- =========================================================
CREATE OR REPLACE VIEW vw_dashboard_kpis AS
SELECT
    (SELECT COUNT(*) FROM sources WHERE is_active = TRUE) AS active_sources,
    (SELECT COUNT(*) FROM raw_snapshots) AS total_snapshots,
    (SELECT COUNT(*) FROM change_events) AS total_change_events,
    (SELECT COUNT(*) FROM change_events WHERE severity = 'high') AS high_severity_change_events,
    (SELECT MAX(fetched_at) FROM raw_snapshots) AS latest_snapshot_at,
    (SELECT MAX(finished_at) FROM ingestion_runs WHERE status IN ('success', 'partial_success')) AS latest_successful_run_at;

COMMIT;