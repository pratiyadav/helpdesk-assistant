from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import DATABASE_URL


def _configure(conn):
    register_vector(conn)
    conn.commit()


pool = ConnectionPool(
    DATABASE_URL, min_size=1, max_size=10, open=False,
    configure=_configure, kwargs={"row_factory": dict_row},
)


def init_db():
    """Run schema before the pool opens (the vector type must exist before register_vector)."""
    sql = (Path(__file__).parent / "schema.sql").read_text()
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        conn.execute(sql)
