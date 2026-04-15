import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from src.config import DATABASE_URL

_engine: Engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def get_engine() -> Engine:
    return _engine


def query_df(sql: str, params: dict = None) -> pd.DataFrame:
    with _engine.connect() as conn:
        return pd.read_sql_query(text(sql), conn, params=params)


def execute(sql: str, params: dict = None) -> None:
    with _engine.begin() as conn:
        conn.execute(text(sql), params or {})
