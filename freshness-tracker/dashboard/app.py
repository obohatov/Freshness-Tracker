"""
Belgian Public Service Freshness Tracker — Dashboard
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import pandas as pd
from src.db import query_df

st.set_page_config(
    page_title="Freshness Tracker",
    page_icon="🔍",
    layout="wide",
)

st.title("Belgian Public Service Freshness Tracker")
st.caption("Live data from PostgreSQL — no hardcoded values.")


# ──────────────────────────────────────────────────────────────
# Section 1 – KPI Cards
# ──────────────────────────────────────────────────────────────
st.subheader("Overview")

try:
    kpi = query_df("SELECT * FROM vw_dashboard_kpis")
    row = kpi.iloc[0]

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Active Sources", int(row["active_sources"]))
    col2.metric("Total Snapshots", int(row["total_snapshots"]))
    col3.metric("Change Events", int(row["total_change_events"]))
    col4.metric("High-Severity Changes", int(row["high_severity_change_events"]))

    latest_run = row["latest_successful_run_at"]
    col5.metric(
        "Latest Successful Run",
        str(latest_run)[:16] if latest_run and str(latest_run) != "None" else "No runs yet",
    )

except Exception as e:
    st.error(f"Could not load KPIs: {e}")

st.divider()


# ──────────────────────────────────────────────────────────────
# Section 2 – Recent Ingestion Runs
# ──────────────────────────────────────────────────────────────
st.subheader("Recent Ingestion Runs")

try:
    runs = query_df("""
        SELECT
            run_id,
            started_at,
            status,
            sources_total,
            sources_succeeded,
            sources_failed,
            ROUND(duration_seconds::numeric, 1) AS duration_s,
            error_summary
        FROM vw_ingestion_run_summary
        LIMIT 10
    """)

    if runs.empty:
        st.info("No ingestion runs recorded yet. Run `python3 src/pipeline/run_ingestion.py` to start.")
    else:
        def _status_label(s):
            return {"success": "✅ success", "partial_success": "⚠️ partial", "failed": "❌ failed", "running": "⏳ running"}.get(s, s)

        runs["status"] = runs["status"].apply(_status_label)
        runs["started_at"] = pd.to_datetime(runs["started_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        runs = runs.rename(columns={
            "run_id": "Run",
            "started_at": "Started",
            "status": "Status",
            "sources_total": "Total",
            "sources_succeeded": "OK",
            "sources_failed": "Failed",
            "duration_s": "Duration (s)",
            "error_summary": "Errors",
        })
        st.dataframe(runs, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Could not load ingestion runs: {e}")

st.divider()


# ──────────────────────────────────────────────────────────────
# Section 3 – Source Coverage Summary
# ──────────────────────────────────────────────────────────────
st.subheader("Source Coverage")

try:
    coverage = query_df("""
        SELECT
            organization_name,
            page_name,
            category,
            language,
            total_snapshots,
            latest_http_status   AS last_http,
            latest_snapshot_at
        FROM vw_source_snapshot_summary
        ORDER BY organization_name, page_name
    """)

    if coverage.empty:
        st.info("No sources tracked yet.")
    else:
        snapped  = int((coverage["total_snapshots"] > 0).sum())
        unsnapped = len(coverage) - snapped

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Sources Configured", len(coverage))
        c2.metric("Sources with ≥1 Snapshot", snapped)
        c3.metric("Sources Not Yet Fetched", unsnapped)

        coverage["latest_snapshot_at"] = pd.to_datetime(
            coverage["latest_snapshot_at"]
        ).dt.strftime("%Y-%m-%d %H:%M").where(coverage["latest_snapshot_at"].notna(), "—")

        coverage = coverage.rename(columns={
            "organization_name": "Organisation",
            "page_name": "Page",
            "category": "Category",
            "language": "Lang",
            "total_snapshots": "Snapshots",
            "last_http": "Last HTTP",
            "latest_snapshot_at": "Last Fetched",
        })

        with st.expander("Show all sources", expanded=False):
            st.dataframe(coverage, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Could not load source coverage: {e}")

st.divider()


# ──────────────────────────────────────────────────────────────
# Section 4 – Recent Extracted Snapshots
# ──────────────────────────────────────────────────────────────
st.subheader("Recent Extracted Snapshots")

try:
    snaps = query_df("""
        SELECT
            s.organization_name,
            s.page_name,
            rs.fetched_at,
            rs.http_status,
            rs.page_title,
            ef.email,
            ef.phone,
            CASE WHEN ef.opening_hours IS NOT NULL THEN 'yes' ELSE '—' END AS hours_found,
            CASE WHEN ef.fee_text      IS NOT NULL THEN 'yes' ELSE '—' END AS fee_found
        FROM extracted_fields ef
        JOIN raw_snapshots rs ON rs.snapshot_id = ef.snapshot_id
        JOIN sources s        ON s.source_id    = ef.source_id
        ORDER BY rs.fetched_at DESC
        LIMIT 15
    """)

    if snaps.empty:
        st.info("No extracted snapshots yet. Run ingestion then extraction.")
    else:
        snaps["fetched_at"] = pd.to_datetime(snaps["fetched_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        snaps = snaps.rename(columns={
            "organization_name": "Organisation",
            "page_name": "Page",
            "fetched_at": "Fetched At",
            "http_status": "HTTP",
            "page_title": "Page Title",
            "email": "Email",
            "phone": "Phone",
            "hours_found": "Hours?",
            "fee_found": "Fee?",
        })
        st.dataframe(snaps, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Could not load extracted snapshots: {e}")

st.divider()


# ──────────────────────────────────────────────────────────────
# Section 5 – Change Detection Summary
# ──────────────────────────────────────────────────────────────
st.subheader("Change Detection")

try:
    total_changes = query_df("SELECT COUNT(*) AS n FROM change_events").iloc[0]["n"]
    sources_compared = query_df("""
        SELECT COUNT(DISTINCT current_snapshot_id) AS n FROM change_events
    """).iloc[0]["n"]
    eligible_compared = query_df("""
        SELECT COUNT(DISTINCT source_id) AS n
        FROM raw_snapshots
        GROUP BY source_id
        HAVING COUNT(*) >= 2
    """)
    eligible_count = len(eligible_compared)

    if int(total_changes) == 0:
        st.info(
            f"**Change detector ran successfully.** "
            f"{eligible_count} source(s) had enough snapshots to compare — "
            f"no field-level differences were found. "
            f"This is expected when both snapshots were captured within a short time window. "
            f"Fetch the same pages again after some time has passed, re-run extraction and "
            f"change detection, and real differences will appear here."
        )
    else:
        # Changes over time
        cot = query_df("SELECT * FROM vw_changes_over_time ORDER BY change_date")
        if not cot.empty:
            cot["change_date"] = pd.to_datetime(cot["change_date"])
            st.markdown("**Changes over time**")
            st.bar_chart(
                cot.set_index("change_date")[
                    ["high_severity_changes", "medium_severity_changes", "low_severity_changes"]
                ]
            )

        # Changes by type
        cbt = query_df("SELECT * FROM vw_changes_by_type")
        if not cbt.empty:
            st.markdown("**Changes by type**")
            st.bar_chart(cbt.set_index("change_type")["total_changes"])

except Exception as e:
    st.error(f"Could not load change detection summary: {e}")

st.divider()


# ──────────────────────────────────────────────────────────────
# Section 6 – Latest Alerts
# ──────────────────────────────────────────────────────────────
st.subheader("Latest Freshness Alerts")

try:
    alerts = query_df("SELECT * FROM vw_latest_alerts LIMIT 50")
    if alerts.empty:
        st.info(
            "No alerts yet. Alerts appear here once the change detector finds "
            "a field that differs between two successive snapshots of the same page."
        )
    else:
        display_cols = [
            "detected_at", "organization_name", "page_name",
            "field_name", "old_value", "new_value", "severity", "change_type",
        ]
        existing = [c for c in display_cols if c in alerts.columns]
        alerts["detected_at"] = pd.to_datetime(alerts["detected_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        st.dataframe(alerts[existing], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Could not load latest alerts: {e}")

st.divider()


# ──────────────────────────────────────────────────────────────
# Section 7 – Most Frequently Changing Pages
# ──────────────────────────────────────────────────────────────
st.subheader("Most Frequently Changing Pages")

try:
    mcp = query_df("""
        SELECT
            organization_name,
            page_name,
            category,
            total_changes,
            high_severity_changes,
            latest_change_at
        FROM vw_most_changed_pages
        WHERE total_changes > 0
        ORDER BY total_changes DESC
        LIMIT 20
    """)
    if mcp.empty:
        st.info("No changes recorded yet — this table will fill once the detector finds differences.")
    else:
        mcp["latest_change_at"] = pd.to_datetime(mcp["latest_change_at"]).dt.strftime("%Y-%m-%d %H:%M")
        mcp = mcp.rename(columns={
            "organization_name": "Organisation",
            "page_name": "Page",
            "category": "Category",
            "total_changes": "Total Changes",
            "high_severity_changes": "High Severity",
            "latest_change_at": "Latest Change",
        })
        st.dataframe(mcp, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Could not load most changed pages: {e}")
