# Belgian Public Service Freshness Tracker

A batch data pipeline that monitors Belgian public-service web pages, stores page snapshots, detects field-level changes, and displays freshness alerts in a Streamlit dashboard.

## Stack

- Python 3.10+
- PostgreSQL
- SQLAlchemy (connection helpers only — no ORM models yet)
- Streamlit (dashboard)

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
│   ├── config.py           # Reads DATABASE_URL from environment
│   └── db.py               # SQLAlchemy connection helpers
├── .env.example            # Environment variable template
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

### 3. Bootstrap the database

Applies the schema, creates all analytical views, and loads the seed source list:

```bash
python scripts/bootstrap_db.py
```

The script is safe to re-run — it uses `CREATE TABLE IF NOT EXISTS` and upserts on `source_id`.

## Running the dashboard

```bash
streamlit run dashboard/app.py
```

The dashboard reads from these PostgreSQL views:

| View | Purpose |
|---|---|
| `vw_dashboard_kpis` | Top-level KPI summary row |
| `vw_changes_over_time` | Daily change event counts |
| `vw_changes_by_type` | Change distribution by type |
| `vw_latest_alerts` | Most recent detected changes |
| `vw_most_changed_pages` | Pages with the most changes |

## Next steps (not implemented yet)

- **Ingestion** — fetch pages and store raw snapshots (`raw_snapshots` table)
- **Extraction** — parse structured fields from snapshots (`extracted_fields` table)
- **Change detection** — compare successive snapshots and write `change_events`
- **Scheduling** — batch execution
