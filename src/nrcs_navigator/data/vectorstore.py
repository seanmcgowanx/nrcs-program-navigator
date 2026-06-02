"""Build and query the pgvector store over eCFR regulations.

Bridges ecfr_loader (which produces chunks) and eligibility_screener (which
queries the store). Embeddings live in PostgreSQL via the pgvector extension,
using the langchain-postgres PGVector integration. Connection comes from
data/db.py, so the embeddings share one database with the payment_rates table
and the LangGraph checkpointer.

Intended responsibilities:
    - build_index(): embed the chunks from ecfr_loader with the configured
      embedding model and upsert them into a PGVector collection (table) in
      Postgres. Run once at pipeline build time.
    - get_store(): return the PGVector store bound to the shared engine for use
      at agent query time.
    - similarity_search(): thin retrieval helper returning the top matching
      regulation chunks with their metadata, used by eligibility_screener.

Swapping back to a local store later means changing only this module.
"""
