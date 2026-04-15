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
