# Belgian Public Service Freshness Tracker

A batch data pipeline that monitors Belgian public-service web pages, detects field-level changes between successive snapshots, and presents freshness alerts in a Streamlit dashboard.

Built as a data engineering course project. No ORM, no LLMs, no Docker.

---

## Project goal

Belgian government websites publish contact details, opening hours, fee information, and procedural documents. These fields change without notice. This project automates:

1. **Fetching** pages on a schedule and storing raw snapshots.
2. **Extracting** structured fields (phone, email, opening hours, fees, PDF links) from the raw text.
3. **Detecting** field-level differences between successive snapshots and recording them as change events.
4. **Displaying** a live dashboard showing pipeline health, extraction coverage, and freshness alerts.

---

## Architecture overview

```
             ┌──────────────────────────────────────┐
             │           PostgreSQL database         │
             │                                       │
  run_       │  sources ──► raw_snapshots            │
  ingestion  │                  │                    │
  ──────────►│                  ▼                    │
             │          extracted_fields             │
  run_       │                  │                    │
  extraction │                  ▼                    │
  ──────────►│           change_events               │
             │                  │                    │
  run_change │                  ▼                    │
  _detection │          analytical views             │
  ──────────►│                  │                    │
             └──────────────────┼───────────────────┘
                                │
                         Streamlit dashboard
                         (dashboard/app.py)
```

Each stage is a standalone Python script. They are intentionally decoupled — ingestion, extraction, and change detection can each be run independently and re-run safely.

---

## Schema overview

| Table | Purpose |
|---|---|
| `sources` | Master list of monitored pages (32 seed rows) |
| `ingestion_runs` | One row per pipeline batch run; tracks status and counts |
| `raw_snapshots` | Raw fetched page content plus HTTP metadata, one row per source per run |
| `extracted_fields` | Structured fields extracted from each snapshot (phone, email, opening hours, fee text, PDF links) |
| `change_events` | Field-level differences between successive snapshots; the primary output of the pipeline |

Authoritative DDL: `sql/00_schema.sql`

### Analytical views (used by dashboard)

| View | Purpose |
|---|---|
| `vw_dashboard_kpis` | Single-row summary of key metrics |
| `vw_ingestion_run_summary` | Recent pipeline run history |
| `vw_source_snapshot_summary` | Snapshot coverage per source |
| `vw_latest_alerts` | Most recent change events with source metadata |
| `vw_changes_over_time` | Daily change event counts by severity |
| `vw_changes_by_type` | Change event distribution by type |
| `vw_most_changed_pages` | Pages ranked by total change events |

Defined in: `sql/01_views.sql`

---

## Pipeline stages

### Stage 1 — Ingestion (`src/pipeline/fetch_pages.py`, `run_ingestion.py`)

- Opens an `ingestion_runs` row with `status = 'running'`.
- Pulls up to `MAX_SOURCES = 3` active sources, ordered by `source_id`.
- Fetches each URL with `requests` + `BeautifulSoup`, stores visible text, HTTP metadata, and a SHA-256 content hash.
- Closes the `ingestion_runs` row with final counts and status (`success` / `partial_success` / `failed`).

### Stage 2 — Extraction (`src/pipeline/extract_fields.py`, `run_extraction.py`)

- Finds the latest unprocessed snapshot per source (no matching row in `extracted_fields`).
- Runs regex-based extractors for: `email`, `phone`, `opening_hours`, `fee_text`, `pdf_links`.
- Inserts one `extracted_fields` row per snapshot. Safe to re-run — skips already-processed snapshots.

Extractors are fully deterministic. No external APIs or ML.

### Stage 3 — Change detection (`src/pipeline/detect_changes.py`, `run_change_detection.py`)

- Finds sources with ≥ 2 snapshots whose latest snapshot has not yet been used as `current_snapshot_id` in `change_events`.
- Fetches the latest two snapshots for each eligible source (joined with their `extracted_fields`).
- Compares six fields: `content_hash`, `page_title`, `email`, `phone`, `opening_hours`, `fee_text`.
- Inserts one `change_events` row per differing field.
- Severity: **high** (phone, opening_hours, fee_text) · **medium** (email) · **low** (page_title, content_hash)
- Change types: `value_changed`, `value_added`, `value_removed`

---

## Project structure

```
freshness-tracker/
├── .streamlit/
│   └── config.toml             # Streamlit server config (Replit-compatible)
├── dashboard/
│   └── app.py                  # Streamlit dashboard (7 sections)
├── data/
│   └── seed_sources.csv        # 32 monitored Belgian public-service pages
├── scripts/
│   └── bootstrap_db.py         # Apply schema + views + upsert seed sources
├── sql/
│   ├── 00_schema.sql           # Tables, constraints, indexes
│   └── 01_views.sql            # Analytical views for dashboard
├── src/
│   ├── config.py               # DATABASE_URL + optional settings from env
│   ├── db.py                   # SQLAlchemy engine + query_df helper
│   └── pipeline/
│       ├── fetch_pages.py          # Fetch one URL → raw snapshot dict
│       ├── run_ingestion.py        # Orchestrate a batch ingestion run
│       ├── extract_fields.py       # Regex field extractors
│       ├── run_extraction.py       # Orchestrate extraction pass
│       ├── detect_changes.py       # Compare two snapshot dicts → change events
│       └── run_change_detection.py # Orchestrate change detection pass
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure the database

Copy `.env.example` to `.env` and set your PostgreSQL connection string:

```bash
cp .env.example .env
# then edit .env:
# DATABASE_URL=postgresql://user:password@localhost:5432/freshness_tracker
```

On Replit, `DATABASE_URL` is injected automatically — no `.env` file needed.

Optional environment variables (defaults shown):

```
FETCH_TIMEOUT=15
USER_AGENT=FreshnessTracker/0.1 (monitoring public-service pages)
```

### 3. Bootstrap the database

Applies schema, creates all views, and upserts the 32 seed sources:

```bash
cd freshness-tracker
python3 scripts/bootstrap_db.py
```

Safe to re-run — uses `CREATE TABLE IF NOT EXISTS` and upserts on `source_id`.

---

## Running the pipeline

All commands assume `freshness-tracker/` as the working directory.

### Ingestion

Fetches the next batch of pages and stores raw snapshots:

```bash
python3 src/pipeline/run_ingestion.py
```

Currently fetches 3 sources per run (ordered by `source_id`). Each run creates one `ingestion_runs` row and one `raw_snapshots` row per source.

### Extraction

Extracts structured fields from all snapshots not yet processed:

```bash
python3 src/pipeline/run_extraction.py
```

Skips any snapshot that already has a row in `extracted_fields`.

### Change detection

Compares the latest vs previous snapshot for each eligible source:

```bash
python3 src/pipeline/run_change_detection.py
```

A source is eligible if it has ≥ 2 snapshots and its latest snapshot has not already been compared. Run ingestion at least twice for the same sources before running detection.

---

## Running the dashboard

```bash
streamlit run dashboard/app.py
```

The dashboard reads exclusively from PostgreSQL views — no hardcoded values.

### Dashboard sections

1. **Overview** — 5 KPI metrics (active sources, snapshots, change events, severity breakdown, last run time)
2. **Recent Ingestion Runs** — last 10 runs with status, counts, and duration
3. **Source Coverage** — snapshot coverage across all 32 configured sources
4. **Recent Extracted Snapshots** — last 15 snapshots with extracted field presence
5. **Change Detection** — empty-state guidance or charts when data is available
6. **Latest Freshness Alerts** — change events table with severity and field detail
7. **Most Frequently Changing Pages** — pages ranked by total change count

### Replit preview — `.streamlit/config.toml`

Streamlit's default configuration blocks WebSocket connections when served behind Replit's proxy/iframe. The `freshness-tracker/.streamlit/config.toml` file fixes this:

```toml
[server]
headless = true
address = "0.0.0.0"
port = 8501
enableCORS = false
enableXsrfProtection = false
```

Without `enableCORS = false` and `enableXsrfProtection = false`, the preview pane shows a blank loading screen with persistent WebSocket errors in the browser console.

---

## Current status

Snapshot of the live database as of project submission:

| Table | Rows | Notes |
|---|---|---|
| `sources` | **32** | All seed sources active; 6 unique sources have been fetched at least once |
| `ingestion_runs` | **3** | All 3 runs completed with `status = success` |
| `raw_snapshots` | **9** | 3 sources × 3 runs (and_001, and_002, and_003 fetched twice; bxl_001–003 once) |
| `extracted_fields` | **9** | All 9 snapshots fully extracted; 0 errors |
| `change_events` | **0** | Detector ran on 3 eligible sources; no field-level differences found (both snapshots captured within the same session — expected result) |

To generate real change events: run ingestion again after a gap of several days, re-run extraction, then re-run change detection.
