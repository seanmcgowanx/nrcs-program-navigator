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

import os
from pathlib import Path

from dotenv import load_dotenv

# Project root resolved from this file's location, so paths work no matter
# what the current working directory is when a module imports config.
# config.py lives at <root>/src/nrcs_navigator/config.py, so the root is
# three parents up.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load .env once, on import. Point at the project root explicitly rather than
# relying on the current working directory: notebooks run from notebooks/, so a
# bare load_dotenv() could miss the .env that lives at the repo root.
load_dotenv(PROJECT_ROOT / ".env")

# Downloaded source artifacts (CSV + eCFR PDFs). Git ignored; the pipeline
# reads from here and lands cleaned data in Postgres, not back on disk.
DATA_RAW = PROJECT_ROOT / "data" / "raw"

# The NRCS Practice FIPS payment export (FY2023 to FY2025). UTF-16,
# tab-delimited, with a title row above the real header.
FIPS_PAYMENTS_CSV = DATA_RAW / "Practice_FIPS_23-25.csv"


def _require(name: str) -> str:
    """Read a required environment variable or fail loudly.

    A missing DATABASE_URL should stop the program with a clear message, not
    surface later as a confusing connection error against the wrong host. Every
    setting the code cannot run without goes through here.
    """
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and fill it in."
        )
    return value


# The single PostgreSQL + pgvector connection string. Backs the payment_rates
# table, the eCFR embeddings, and the LangGraph checkpointer. Required.
DATABASE_URL = _require("DATABASE_URL")

# Data source URLs for the two live-scrape tools. Read from the environment so
# they are easy to update when NRCS reshuffles its site, and surfaced here so
# the tools import them from config rather than reading os.environ directly.
# Unlike the eCFR snapshot below, nothing is persisted from these, so changing
# a URL invalidates no stored data.
NRCS_PRACTICE_STANDARDS_URL = _require("NRCS_PRACTICE_STANDARDS_URL")
NRCS_RANKING_DATES_URL = _require("NRCS_RANKING_DATES_URL")

# The two model legs of the evaluation comparison. Read from the environment so
# evaluation can swap models without touching agent code; defaults match the
# .env.example so the data pipeline imports cleanly before any key is set.
PREMIER_MODEL = os.environ.get("PREMIER_MODEL", "gpt-4o")
CHEAP_MODEL = os.environ.get("CHEAP_MODEL", "gpt-4o-mini")

# Model the LLM judge uses to score eval runs. Kept off the premier model on
# purpose: the premier agent leg and the judge would otherwise share gpt-4o's
# per-minute token budget and rate limit each other. gpt-4o-mini has a separate,
# higher budget, and the judge is validated against human annotation regardless.
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gpt-4o-mini")

# Sampling temperature for the agent LLM. 0 keeps tool use and answers as
# deterministic as the model allows, which matters for reproducible evaluation
# traces and consistent tool calling.
AGENT_TEMPERATURE = 0.0

# Embedding model for the eCFR vector store (the eligibility_screener's RAG).
# Decided: OpenAI text-embedding-3-small. A fixed constant, not an env var --
# the stored vectors are this model's 1536-wide output and the query text must
# be embedded by the same model, so changing it means re-embedding everything.
# The model and its dimension travel together so they cannot drift apart.
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536

# Chunking is section-aware: one chunk per eCFR section. These bound the
# fallback for a section too long to embed as a single chunk -- it is sub-split
# to CHUNK_SIZE tokens with CHUNK_OVERLAP carried across the boundary so a
# provision spanning a split still appears whole in at least one piece.
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64

# --- eCFR regulations (source for the eligibility_screener) ---
# Pulled from the eCFR API as structured XML, not PDFs: the section hierarchy is
# explicit in the markup, so chunks align to whole sections and carry their
# citation (e.g. "7 CFR 1466.6"). The version date pins one regulation snapshot
# for reproducible embeddings.
ECFR_API_BASE = "https://www.ecfr.gov/api/versioner/v1"
ECFR_TITLE = 7
ECFR_VERSION_DATE = "2025-01-01"

# The four in-scope NRCS parts in Title 7 and the program each governs. CRP
# (part 1410) is FSA-administered and intentionally excluded.
ECFR_PARTS = {
    "1466": "EQIP",
    "1468": "ACEP",
    "1470": "CSP",
    "1464": "RCPP",
}

# --- NRCS programs (the agent's vocabulary) ---
# The four high-level programs are the lingua franca between tools: the agent
# reasons and the tools communicate in these names. This is the single source
# of truth -- tools reference it rather than re-listing the programs.
PROGRAMS = ("EQIP", "ACEP", "CSP", "RCPP")

# The FIPS payment export labels rows by funding pool, not by high-level
# program: one program spans several pools funded by different authorities
# (Farm Bill vs the Inflation Reduction Act, etc.). payment_estimator uses this
# map to translate a high-level program into its pools, so the granular labels
# never leak out of the data layer. ACEP is appraisal based and has no payment
# rows, so it is absent. Note CSP is stored under its older acronym "CStwP"
# plus the grassland initiative "CSP-GCI" -- a LIKE 'CSP%' would miss the CStwP
# rows, which is why an explicit map (not a prefix match) is required.
PROGRAM_FUNDING_POOLS = {
    "EQIP": ("EQIP Farm Bill", "EQIP IRA"),
    "CSP": ("CStwP Farm Bill", "CStwP IRA", "CSP-GCI"),
    "RCPP": ("RCPP-CSP", "RCPP-EQIP"),
}