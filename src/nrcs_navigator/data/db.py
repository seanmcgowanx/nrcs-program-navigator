"""PostgreSQL + pgvector connection and schema.

Single entry point for the database that backs the whole system. Per the
architecture spec, one Postgres instance with the pgvector extension holds
three things:
    1. the payment_rates table (structured FIPS payment data),
    2. the eCFR embeddings (vector store for eligibility_screener),
    3. the LangGraph checkpointer tables (agent conversation state).

fips_payments.py, vectorstore.py, and agent/graph.py all connect through here
so there is exactly one DATABASE_URL and one engine to configure.

Intended responsibilities:
    - get_engine(): build and cache a SQLAlchemy engine from config.DATABASE_URL.
    - init_db(): create the pgvector extension (CREATE EXTENSION IF NOT EXISTS
      vector) and the payment_rates table DDL. The PGVector store and the
      LangGraph checkpointer create their own tables on first use.
    - A small connection helper / context manager for raw psycopg access where
      SQLAlchemy is not convenient.

Connection details only. No business logic.
"""

from functools import lru_cache

from sqlalchemy import Engine, create_engine, text

from nrcs_navigator import config

# Schema for the structured payment data. One row is a state-level total for a
# program / practice / fiscal year, matching the columns fips_payments.clean()
# produces. IF NOT EXISTS makes init_db() safe to run repeatedly.
PAYMENT_RATES_DDL = """
CREATE TABLE IF NOT EXISTS payment_rates (
    id                       SERIAL PRIMARY KEY,
    state                    TEXT          NOT NULL,
    program                  TEXT          NOT NULL,
    practice_code            TEXT          NOT NULL,
    practice_name            TEXT          NOT NULL,
    fiscal_year              SMALLINT      NOT NULL,
    instance_count           INTEGER       NOT NULL,
    dollars_obligated        BIGINT        NOT NULL,
    avg_payment_per_instance NUMERIC(12, 2) NOT NULL
);
"""


@lru_cache(maxsize=None)
def get_engine() -> Engine:
    """Build and cache the one SQLAlchemy engine for the whole process.

    The engine owns a connection pool, so we want exactly one, created lazily on
    first use and reused everywhere (fips_payments, vectorstore, the agent
    checkpointer). lru_cache makes every call after the first return the same
    instance. Reads the connection string from config, never os.environ.
    """
    return create_engine(config.DATABASE_URL)


def psycopg_url() -> str:
    """DATABASE_URL in plain libpq form, dropping SQLAlchemy's +psycopg dialect
    tag (postgresql+psycopg://... -> postgresql://...).

    For libraries that take a raw connection string rather than a SQLAlchemy
    engine -- notably the LangGraph PostgresSaver checkpointer, which manages
    its own psycopg connection and tables.
    """
    return config.DATABASE_URL.replace("+psycopg", "", 1)


def init_db() -> None:
    """Prepare the database: enable pgvector and create payment_rates.

    Runs once at pipeline build time. CREATE EXTENSION needs a role with
    sufficient privileges (the compose superuser has it). engine.begin() opens a
    transaction and commits on success, so either both statements land or
    neither does. Idempotent: safe to run on every pipeline pass.
    """
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.execute(text(PAYMENT_RATES_DDL))
