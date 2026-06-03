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
      The embedding model is an open decision (for example OpenAI
      text-embedding-3 vs. an open source model such as BGE); whichever is
      chosen sets the pgvector column dimension in data/db.py, so it is
      configured here in one place.
    - Helper accessors so other modules import settings from here instead of
      reading os.environ directly.

No business logic. Configuration only.
"""

from pathlib import Path

# Project root resolved from this file's location, so paths work no matter
# what the current working directory is when a module imports config.
# config.py lives at <root>/src/nrcs_navigator/config.py, so the root is
# three parents up.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Downloaded source artifacts (CSV + eCFR PDFs). Git ignored; the pipeline
# reads from here and lands cleaned data in Postgres, not back on disk.
DATA_RAW = PROJECT_ROOT / "data" / "raw"

# The NRCS Practice FIPS payment export (FY2023 to FY2025). UTF-16,
# tab-delimited, with a title row above the real header.
FIPS_PAYMENTS_CSV = DATA_RAW / "Practice_FIPS_23-25.csv"
