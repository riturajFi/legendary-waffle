from contextlib import contextmanager
from typing import Iterator

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


@contextmanager
def postgres_checkpointer(database_url: str) -> Iterator[PostgresSaver]:
    pool = ConnectionPool(
        conninfo=database_url,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
        open=True,
    )
    try:
        checkpointer = PostgresSaver(pool)
        checkpointer.setup()
        yield checkpointer
    finally:
        pool.close()
