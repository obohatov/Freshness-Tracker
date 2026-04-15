# Belgian Public Service Freshness Tracker

A batch data pipeline that monitors Belgian public-service web pages, stores page snapshots, detects field-level changes, and displays freshness alerts in a Streamlit dashboard.

## Stack

- Python 3.10+
- PostgreSQL
- SQLAlchemy (connection helpers — no ORM models)
- Streamlit (dashboard)
- requests + BeautifulSoup (ingestion)

## Project structure

```
freshness-tracker/
├── dashboard/
│   └── app.py              # Streamlit dashboard
├── data/
│   └── seed_sources.csv    # Seed data for monitored pages
├── scripts/
│   └── bootstrap_db.py     # Apply schema, views, and seed sources
├── sql/
│   ├── 00_schema.sql       # Authoritative table definitions
│   └── 01_views.sql        # Analytical views for dashboard
├── src/
│   ├── config.py           # Reads DATABASE_URL and other settings from environment
│   ├── db.py               # SQLAlchemy connection helpers
│   └── pipeline/
│       ├── fetch_pages.py      # Fetch one page, return snapshot fields
│       └── run_ingestion.py    # Orchestrate a full ingestion batch run
├── .env.example            # Environment variable template
├── .gitignore
├── requirements.txt        # Python dependencies
└── README.md
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure the database URL

Copy `.env.example` to `.env` and fill in your PostgreSQL connection string:

```bash
cp .env.example .env
```

Edit `.env`:

```
DATABASE_URL=postgresql://user:password@localhost:5432/freshness_tracker
```

On Replit, `DATABASE_URL` is injected automatically — no `.env` file needed.

Optional environment variables (with defaults):

```
FETCH_TIMEOUT=15        # HTTP request timeout in seconds
USER_AGENT=FreshnessTracker/0.1 (monitoring public-service pages)
```

### 3. Bootstrap the database

Applies the schema, creates all analytical views, and loads the seed source list:

```bash
python scripts/bootstrap_db.py
```

Safe to re-run — uses `CREATE TABLE IF NOT EXISTS` and upserts on `source_id`.

## Running the dashboard

```bash
streamlit run dashboard/app.py
```

Reads from these PostgreSQL views:

| View | Purpose |
|---|---|
| `vw_dashboard_kpis` | Top-level KPI summary row |
| `vw_changes_over_time` | Daily change event counts |
| `vw_changes_by_type` | Change distribution by type |
| `vw_latest_alerts` | Most recent detected changes |
| `vw_most_changed_pages` | Pages with the most changes |

## Running ingestion

Fetches the first 3 active sources (ordered by `source_id`) and stores raw snapshots:

```bash
python src/pipeline/run_ingestion.py
```

Each run creates one row in `ingestion_runs` and one row in `raw_snapshots` per page attempted.

## Current implementation status

| Component | Status |
|---|---|
| Schema + views | Done |
| Source seeding | Done |
| Batch ingestion (fetch + snapshot) | Done |
| Field extraction | Not yet implemented |
| Change detection | Not yet implemented |
| Scheduling | Not yet implemented |

## Next steps (not implemented yet)

- **Extraction** — parse structured fields from snapshots (`extracted_fields` table)
- **Change detection** — compare successive snapshots and write `change_events`
- **Scheduling** — batch execution
