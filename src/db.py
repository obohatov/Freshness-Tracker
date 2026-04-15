from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from src.config import DATABASE_URL


def get_engine() -> Engine:
    return create_engine(DATABASE_URL)


def query_df(sql: str, params: dict = None):
    import pandas as pd
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(text(sql), conn, params=params)


def execute(sql: str, params: dict = None) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(sql), params or {})
