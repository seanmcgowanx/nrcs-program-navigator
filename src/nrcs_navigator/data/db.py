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
