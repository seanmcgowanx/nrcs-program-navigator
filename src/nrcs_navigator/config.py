"""Central configuration for the project.

Single source of truth for settings that the pipeline, agent, tools, and
evaluation all need. Loads values from the .env file (via python-dotenv) so
that secrets and tunable choices never get hard coded into modules.

What belongs here:
    - Loading the .env file once on import.
    - Model identifiers: PREMIER_MODEL and CHEAP_MODEL, read from the
      environment so evaluation can swap models without touching agent code.
    - DATABASE_URL: the single PostgreSQL + pgvector connection string used by
      the payment_rates table, the embeddings store, and the agent checkpointer.
    - Filesystem path: location of data/raw (downloaded CSV and eCFR PDFs),
      resolved relative to the project root. Persistence otherwise lives in
      Postgres, not on disk.
    - Data source URLs for the two live scrape tools (practice standards,
      ranking dates).
    - Embedding model name and chunking parameters used by the vector store.
    - Helper accessors so other modules import settings from here instead of
      reading os.environ directly.

No business logic. Configuration only.
"""
