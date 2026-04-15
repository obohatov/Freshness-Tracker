import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise EnvironmentError(
        "DATABASE_URL is not set. "
        "Copy .env.example to .env and fill in your PostgreSQL connection string, "
        "or set the DATABASE_URL environment variable directly."
    )

FETCH_TIMEOUT = int(os.environ.get("FETCH_TIMEOUT", "15"))

USER_AGENT = os.environ.get(
    "USER_AGENT",
    "FreshnessTracker/0.1 (monitoring public-service pages)",
)

# Maximum number of sources to fetch per ingestion run.
# Set to a positive integer to cap the batch size (e.g. MAX_SOURCES=5).
# Leave unset or empty to process all active sources.
_max_sources_raw = os.environ.get("MAX_SOURCES", "").strip()
MAX_SOURCES: int | None = int(_max_sources_raw) if _max_sources_raw else None
