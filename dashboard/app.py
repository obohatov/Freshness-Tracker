"""
Belgian Public Service Freshness Tracker — Dashboard
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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
    col3.metric("Total Change Events", int(row["total_change_events"]))
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
# Section 2 – Changes Over Time
# ──────────────────────────────────────────────────────────────
st.subheader("Detected Changes Over Time")

try:
    cot = query_df("SELECT * FROM vw_changes_over_time ORDER BY change_date")
    if cot.empty:
        st.info("No change events recorded yet.")
    else:
        cot["change_date"] = pd.to_datetime(cot["change_date"])
        st.bar_chart(
            cot.set_index("change_date")[
                ["high_severity_changes", "medium_severity_changes", "low_severity_changes"]
            ]
        )
except Exception as e:
    st.error(f"Could not load changes over time: {e}")

st.divider()

# ──────────────────────────────────────────────────────────────
# Section 3 – Changes By Type
# ──────────────────────────────────────────────────────────────
st.subheader("Change Events by Type")

try:
    cbt = query_df("SELECT * FROM vw_changes_by_type")
    if cbt.empty:
        st.info("No change events recorded yet.")
    else:
        st.bar_chart(cbt.set_index("change_type")["total_changes"])
except Exception as e:
    st.error(f"Could not load changes by type: {e}")

st.divider()

# ──────────────────────────────────────────────────────────────
# Section 4 – Latest Alerts
# ──────────────────────────────────────────────────────────────
st.subheader("Latest Freshness Alerts")

try:
    alerts = query_df("SELECT * FROM vw_latest_alerts LIMIT 50")
    if alerts.empty:
        st.info("No alerts detected yet. Run the pipeline to populate this table.")
    else:
        display_cols = [
            "detected_at",
            "organization_name",
            "page_name",
            "field_name",
            "old_value",
            "new_value",
            "severity",
        ]
        existing = [c for c in display_cols if c in alerts.columns]
        st.dataframe(alerts[existing], use_container_width=True)
except Exception as e:
    st.error(f"Could not load latest alerts: {e}")

st.divider()

# ──────────────────────────────────────────────────────────────
# Section 5 – Most Changed Pages
# ──────────────────────────────────────────────────────────────
st.subheader("Most Frequently Changing Pages")

try:
    mcp = query_df("""
        SELECT organization_name, page_name, url, total_changes, high_severity_changes, latest_change_at
        FROM vw_most_changed_pages
        ORDER BY total_changes DESC
        LIMIT 20
    """)
    if mcp.empty:
        st.info("No page change data yet.")
    else:
        st.dataframe(mcp, use_container_width=True)
except Exception as e:
    st.error(f"Could not load most changed pages: {e}")
