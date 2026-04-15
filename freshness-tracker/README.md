# Belgian Public Service Freshness Tracker

A batch data pipeline that monitors Belgian public-service web pages, detects field-level changes between successive snapshots, and displays freshness alerts on a Streamlit dashboard.

Built as a data engineering course project.  
Stack: Python 3.11 · PostgreSQL · SQLAlchemy · Streamlit · requests · BeautifulSoup  
No ORM models. No LLMs. No Docker. No Airflow.

---

## Project goal

Belgian municipal and federal service websites publish contact details, opening hours, fee schedules, and procedural documents. These fields change without announcement. This project automates:

1. **Ingestion** — fetch pages on demand, store raw text and HTTP metadata as snapshots.
2. **Extraction** — parse structured fields (phone, email, opening hours, fees, PDF links) from raw text using deterministic regex extractors.
3. **Change detection** — compare successive snapshots of the same page and record every field-level difference as a change event.
4. **Dashboard** — live Streamlit interface over PostgreSQL views showing pipeline health, extraction coverage, and freshness alerts.

---

## Architecture overview

```
             ┌─────────────────────────────────────────┐
             │            PostgreSQL database           │
             │                                         │
  run_       │   sources ──► raw_snapshots             │
  ingestion  │                    │                    │
  ──────────►│                    ▼                    │
             │            extracted_fields             │
  run_       │                    │                    │
  extraction │                    ▼                    │
  ──────────►│             change_events               │
             │                    │                    │
  run_change │                    ▼                    │
  _detection │          analytical views (7)           │
  ──────────►│                    │                    │
             └────────────────────┼────────────────────┘
                                  │
                           Streamlit dashboard
                            (dashboard/app.py)
```

Each stage is a standalone Python script. They are intentionally decoupled — any stage can be run independently and re-run safely.

---

## Schema overview

Authoritative DDL: `sql/00_schema.sql`

| Table | Purpose |
|---|---|
| `sources` | Master list of 32 monitored Belgian public-service pages |
| `ingestion_runs` | One row per pipeline batch; tracks status, counts, and duration |
| `raw_snapshots` | Raw page text + HTTP metadata (status, headers, title, content hash) per source per run |
| `extracted_fields` | Structured fields extracted from each snapshot (phone, email, opening_hours, fee_text, pdf_links) |
| `change_events` | Field-level differences between successive snapshots — the primary output of the pipeline |

### Analytical views

Defined in: `sql/01_views.sql`

| View | Purpose |
|---|---|
| `vw_dashboard_kpis` | Single-row KPI summary (active sources, total snapshots, change events, last run time) |
| `vw_ingestion_run_summary` | Recent pipeline run history with duration |
| `vw_source_snapshot_summary` | Snapshot coverage and last HTTP status per source |
| `vw_latest_alerts` | Most recent change events joined with source metadata |
| `vw_changes_over_time` | Daily change event counts broken down by severity |
| `vw_changes_by_type` | Change event distribution by type (value_changed / value_added / value_removed) |
| `vw_most_changed_pages` | Pages ranked by total change events |

---

## Pipeline stages

### Stage 1 — Ingestion

**Files:** `src/pipeline/fetch_pages.py`, `src/pipeline/run_ingestion.py`

1. Opens an `ingestion_runs` row with `status = 'running'`.
2. Loads active sources from `sources`, ordered deterministically by `source_id`.
   - If `MAX_SOURCES` is set in the environment, fetches at most that many sources.
   - If `MAX_SOURCES` is unset (default), fetches **all active sources**.
3. For each source: GETs the URL with `requests`, parses visible text with `BeautifulSoup`, computes a SHA-256 content hash, and inserts one `raw_snapshots` row.
4. Closes the `ingestion_runs` row with final status (`success` / `partial_success` / `failed`).

Network errors and HTTP ≥ 400 are recorded as failures in `raw_text` and counted separately — the run does not abort.

### Stage 2 — Extraction

**Files:** `src/pipeline/extract_fields.py`, `src/pipeline/run_extraction.py`

1. Queries the latest unprocessed snapshot per source (no matching row in `extracted_fields`).
2. Runs five deterministic regex extractors: `email`, `phone`, `opening_hours` (keyword snippet), `fee_text` (keyword snippet), `pdf_links` (URL list).
3. Inserts one `extracted_fields` row per snapshot. Idempotent — skips already-processed snapshots.

No external APIs. All extraction is pure Python regex.

### Stage 3 — Change detection

**Files:** `src/pipeline/detect_changes.py`, `src/pipeline/run_change_detection.py`

1. Finds sources with ≥ 2 snapshots whose latest snapshot has not yet been used as `current_snapshot_id` in `change_events`.
2. For each eligible source, fetches the two most recent snapshots (joined with their `extracted_fields`).
3. Compares six fields: `content_hash`, `page_title`, `email`, `phone`, `opening_hours`, `fee_text`.
4. Inserts one `change_events` row per differing field.

**Severity rules:**

| Severity | Fields |
|---|---|
| `high` | `phone`, `opening_hours`, `fee_text` |
| `medium` | `email` |
| `low` | `page_title`, `content_hash` |

**Change types:** `value_changed` · `value_added` · `value_removed`

---

## How to run

All commands assume `freshness-tracker/` as the working directory.

### 1 — Bootstrap the database

Applies schema, creates views, and upserts 32 seed sources. Safe to re-run.

```bash
python3 scripts/bootstrap_db.py
```

### 2 — Ingestion

Fetch all active sources and store snapshots (default — no limit):

```bash
python3 src/pipeline/run_ingestion.py
```

To cap the batch size, set `MAX_SOURCES` before running:

```bash
MAX_SOURCES=5 python3 src/pipeline/run_ingestion.py
```

Run ingestion at least **twice** for the same set of sources before running change detection — the detector requires ≥ 2 snapshots per source to compare.

### 3 — Extraction

Extract structured fields from all unprocessed snapshots:

```bash
python3 src/pipeline/run_extraction.py
```

### 4 — Change detection

Compare latest vs previous snapshot for all eligible sources:

```bash
python3 src/pipeline/run_change_detection.py
```

### 5 — Dashboard

```bash
streamlit run dashboard/app.py
```

The dashboard reads exclusively from PostgreSQL views — no hardcoded data.

---

## Streamlit + Replit preview — `.streamlit/config.toml`

When running inside Replit's proxy/iframe, Streamlit's default settings reject WebSocket connections as cross-origin requests. This produces a blank loading screen in the preview pane.

The file `freshness-tracker/.streamlit/config.toml` fixes this:

```toml
[server]
headless = true
address = "0.0.0.0"
port = 8501
enableCORS = false
enableXsrfProtection = false
```

`enableCORS = false` and `enableXsrfProtection = false` are the critical settings. Without them, the browser console shows persistent `WebSocket onerror` events and the app never renders.

---

## Dashboard overview

The dashboard has seven sections:

| Section | Data source |
|---|---|
| Overview KPIs | `vw_dashboard_kpis` |
| Recent Ingestion Runs | `vw_ingestion_run_summary` |
| Source Coverage | `vw_source_snapshot_summary` |
| Recent Extracted Snapshots | inline join: `extracted_fields → raw_snapshots → sources` |
| Change Detection Summary | `vw_changes_over_time`, `vw_changes_by_type` |
| Latest Freshness Alerts | `vw_latest_alerts` |
| Most Frequently Changing Pages | `vw_most_changed_pages` |

### Dashboard screenshots

**Overview and KPIs**

![Dashboard overview](docs/screenshots/01_overview.png)

**Ingestion runs and source coverage**

![Ingestion and coverage](docs/screenshots/02_ingestion_coverage.png)

**Extracted snapshots and change detection**

![Extraction and changes](docs/screenshots/03_extraction_changes.png)

---

## Current status

Database state as of final demo run (2026-04-15):

| Table | Rows | Notes |
|---|---|---|
| `sources` | **32** | All 32 seed sources are active |
| `ingestion_runs` | **4** | All 4 runs completed with `status = success`; run 4 processed all 32 sources in 26 s |
| `raw_snapshots` | **41** | 32 sources × 1 full run + 3 sources × 3 earlier runs |
| `extracted_fields` | **41** | All 41 snapshots fully extracted; 0 errors |
| `change_events` | **0** | See note below |

### Why `change_events = 0`

The change detector ran successfully and compared **6 eligible sources** (the sources that had ≥ 2 snapshots at the time of the demo run). No field-level differences were detected.

This is the correct and expected result: all snapshots for the same source were captured within the same session (within minutes of each other). The monitored pages genuinely did not change during that window.

Change events will appear naturally once ingestion is run again after a meaningful time gap (days to weeks), followed by extraction and change detection. The pipeline is fully operational — it is waiting for real-world content to change.

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | *(required)* | PostgreSQL connection string |
| `MAX_SOURCES` | *(unset = all)* | Cap the number of sources per ingestion run |
| `FETCH_TIMEOUT` | `15` | HTTP request timeout in seconds |
| `USER_AGENT` | `FreshnessTracker/0.1 ...` | User-Agent header sent with requests |

On Replit, `DATABASE_URL` is injected automatically.

---

## Project structure

```
freshness-tracker/
├── .streamlit/
│   └── config.toml             # Replit-compatible Streamlit server settings
├── dashboard/
│   └── app.py                  # Streamlit dashboard (7 sections, 7 views)
├── data/
│   └── seed_sources.csv        # 32 monitored Belgian public-service pages
├── scripts/
│   └── bootstrap_db.py         # Apply schema + views + upsert seed data
├── sql/
│   ├── 00_schema.sql           # Tables, constraints, indexes
│   └── 01_views.sql            # Analytical views for dashboard
├── src/
│   ├── config.py               # Environment config (DATABASE_URL, MAX_SOURCES, …)
│   ├── db.py                   # SQLAlchemy engine + query_df helper
│   └── pipeline/
│       ├── fetch_pages.py          # Fetch one URL → raw snapshot dict
│       ├── run_ingestion.py        # Orchestrate a batch ingestion run
│       ├── extract_fields.py       # Regex field extractors
│       ├── run_extraction.py       # Orchestrate extraction pass
│       ├── detect_changes.py       # Compare two snapshot dicts → change event list
│       └── run_change_detection.py # Orchestrate change detection pass
├── .env.example                # Environment variable template
├── .gitignore
├── requirements.txt
└── README.md
```
