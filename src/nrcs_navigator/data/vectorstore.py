"""Build and query the pgvector store over eCFR regulations.

Bridges ecfr_loader (which produces section chunks as langchain Documents) and
eligibility_screener (which queries the store). Embeddings live in PostgreSQL
via the pgvector extension, using the langchain-postgres PGVector integration.
The connection comes from data/db.py, so the embeddings share one database with
the payment_rates table and the LangGraph checkpointer.

Intended responsibilities:
    - build_index(): embed the chunks from ecfr_loader with the configured
      embedding model and load them into a PGVector collection. Run once at
      pipeline build time; rebuilds cleanly (pre_delete) so re-running does not
      duplicate vectors.
    - get_store(): return the PGVector store bound to the shared engine for use
      at agent query time.
    - similarity_search(): thin retrieval helper returning the top matching
      regulation chunks with their metadata, used by eligibility_screener.

Swapping back to a local store later means changing only this module.
"""

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector

from nrcs_navigator import config
from nrcs_navigator.data import db

# All eCFR section chunks live in one named PGVector collection. The name is the
# handle build_index writes to and get_store reads from; keep them in sync.
COLLECTION_NAME = "ecfr_regulations"


def _embeddings() -> OpenAIEmbeddings:
    """The configured embedding model. Reads OPENAI_API_KEY from the environment
    (loaded by config). Fixed to config.EMBEDDING_MODEL so the same model embeds
    both the stored chunks and, later, the query text."""
    return OpenAIEmbeddings(model=config.EMBEDDING_MODEL)


def get_store(pre_delete: bool = False) -> PGVector:
    """Return the PGVector store for the eCFR collection, on the shared engine.

    embedding_length pins the column to the model's 1536 dimensions. pre_delete
    drops the collection's existing rows first; build_index sets it for a clean
    rebuild, while query-time callers leave it False to attach to what is there.
    """
    return PGVector(
        embeddings=_embeddings(),
        connection=db.get_engine(),
        collection_name=COLLECTION_NAME,
        embedding_length=config.EMBEDDING_DIMENSIONS,
        use_jsonb=True,
        pre_delete_collection=pre_delete,
    )


def build_index(chunks: list[Document]) -> int:
    """Embed the chunks and load them into the pgvector collection.

    Rebuilds from scratch (pre_delete) so re-running the pipeline replaces the
    collection instead of stacking duplicates -- the same idempotent reload
    pattern as fips_payments.write. Returns the number of chunks embedded.
    """
    store = get_store(pre_delete=True)
    store.add_documents(chunks)
    return len(chunks)


def similarity_search(
    query: str, k: int = 4, program: str | None = None
) -> list[Document]:
    """Return the k regulation chunks most similar to the query.

    Embeds the query with the same model, then asks pgvector for the nearest
    stored vectors. Each result is a Document carrying the section's text and its
    citation metadata, so eligibility_screener can quote and cite the source.

    program scopes the search to one NRCS program (EQIP/ACEP/CSP/RCPP) by
    filtering on the chunk metadata; None searches across all four.
    """
    metadata_filter = {"program": program} if program else None
    return get_store().similarity_search(query, k=k, filter=metadata_filter)
